#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Despliegue completo de MAIA en EKS desde cero.

.DESCRIPTION
    Ejecuta todos los pasos documentados en DEPLOYMENT_RUNBOOK.md:
      1. Verificar AWS credentials
      2. Kubeconfig
      3. Fix IMDS hop limit (acceso S3 desde pods)
      4. IAM: S3 ReadOnly al node role
      5. IAM + Helm: AWS Load Balancer Controller
      6. Build y Push de imagen backend
      7. kubectl apply (K8s manifests + Ingress)
      8. Patch aws-auth (acceso consola EKS)
      9. Verificar health del ALB

.PARAMETER SkipBuild
    Omite el docker build/push (usar si la imagen ya está en ECR).

.PARAMETER SkipALBController
    Omite la instalación del ALB Controller (usar si ya está corriendo).

.PARAMETER SkipIAM
    Omite los pasos de IAM (usar si los roles/políticas ya existen).

.EXAMPLE
    # Deploy completo desde cero
    .\scripts\full-deploy.ps1

    # Solo re-desplegar manifests y reiniciar pods
    .\scripts\full-deploy.ps1 -SkipBuild -SkipALBController -SkipIAM
#>

param(
    [switch]$SkipBuild,
    [switch]$SkipALBController,
    [switch]$SkipIAM
)

$ErrorActionPreference = "Stop"

# ── Constantes ──────────────────────────────────────────────────────────────
$ACCOUNT_ID    = "360879159958"
$REGION        = "us-east-1"
$CLUSTER       = "maia-dev-eks"
$ECR           = "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/maia-dev-ecr"
$VPC_ID        = "vpc-0bcabca7a1b69957f"
$OIDC_ID       = "54979A0F10FE2CBBAFF3C75200C89DE3"
$OIDC_PROVIDER = "oidc.eks.${REGION}.amazonaws.com/id/${OIDC_ID}"
$BACK_DIR      = (Split-Path $PSScriptRoot -Parent) + "\back"
$K8S_DIR       = (Split-Path $PSScriptRoot -Parent) + "\k8s\eks"
$ALB_DNS       = "maia-alb-1736872550.us-east-1.elb.amazonaws.com"
# ────────────────────────────────────────────────────────────────────────────

function Step { param([string]$msg) Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Ok   { param([string]$msg) Write-Host "    OK: $msg" -ForegroundColor Green }
function Warn { param([string]$msg) Write-Host "    WARN: $msg" -ForegroundColor Yellow }

# ── Paso 0: verificar herramientas y credenciales ───────────────────────────
Step "Verificando prerrequisitos..."
foreach ($tool in @("aws", "kubectl", "helm", "docker")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "Herramienta requerida no encontrada: $tool"
    }
}

$caller = aws sts get-caller-identity --output json | ConvertFrom-Json
if ($caller.Account -ne $ACCOUNT_ID) {
    throw "Cuenta AWS incorrecta: $($caller.Account) (esperado: $ACCOUNT_ID)"
}
Ok "AWS credentials OK — user: $($caller.Arn)"

# ── Paso 1: kubeconfig ────────────────────────────────────────────────────
Step "Actualizando kubeconfig para EKS ($CLUSTER)..."
aws eks update-kubeconfig --region $REGION --name $CLUSTER 2>&1 | Out-Null
$nodes = kubectl get nodes --no-headers 2>&1 | Where-Object { $_ -match "Ready" }
Ok "Nodos Ready: $($nodes.Count)"

# ── Paso 2: IMDS hop limit ────────────────────────────────────────────────
Step "Configurando IMDS hop limit = 2 en nodos EKS..."
$instanceIds = aws ec2 describe-instances `
  --filters "Name=tag:eks:cluster-name,Values=$CLUSTER" `
  --query "Reservations[*].Instances[*].InstanceId" `
  --output text

foreach ($id in ($instanceIds -split '\s+' | Where-Object { $_ })) {
    $result = aws ec2 modify-instance-metadata-options `
      --instance-id $id `
      --http-put-response-hop-limit 2 `
      --http-endpoint enabled `
      --output text 2>&1
    Ok "IMDS actualizado: $id"
}

# ── Paso 3: IAM S3 ReadOnly ───────────────────────────────────────────────
if (-not $SkipIAM) {
    Step "Adjuntando AmazonS3ReadOnlyAccess al node role..."
    $attached = aws iam list-attached-role-policies `
      --role-name maia-dev-eks-node-role `
      --query "AttachedPolicies[?PolicyName=='AmazonS3ReadOnlyAccess'].PolicyName" `
      --output text
    if ($attached -match "AmazonS3ReadOnlyAccess") {
        Warn "S3ReadOnly ya adjuntada, omitiendo."
    } else {
        aws iam attach-role-policy `
          --role-name maia-dev-eks-node-role `
          --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess
        Ok "AmazonS3ReadOnlyAccess adjuntada."
    }
}

# ── Paso 4: ALB Controller IAM + Helm ────────────────────────────────────
if (-not $SkipALBController) {
    Step "Configurando ALB Controller IAM..."

    $policyExists = aws iam get-policy `
      --policy-arn "arn:aws:iam::${ACCOUNT_ID}:policy/AWSLoadBalancerControllerIAMPolicy" `
      --output text 2>&1
    if ($LASTEXITCODE -ne 0) {
        Invoke-WebRequest `
          -Uri "https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v3.3.0/docs/install/iam_policy.json" `
          -OutFile "$env:TEMP\alb-iam-policy.json"
        aws iam create-policy `
          --policy-name AWSLoadBalancerControllerIAMPolicy `
          --policy-document "file://$env:TEMP\alb-iam-policy.json" | Out-Null
        Ok "IAM policy creada."
    } else {
        Warn "IAM policy ya existe, omitiendo creación."
    }

    $roleExists = aws iam get-role --role-name AmazonEKSLoadBalancerControllerRole 2>&1
    if ($LASTEXITCODE -ne 0) {
        $trust = '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Federated":"arn:aws:iam::' + $ACCOUNT_ID + ':oidc-provider/' + $OIDC_PROVIDER + '"},"Action":"sts:AssumeRoleWithWebIdentity","Condition":{"StringEquals":{"' + $OIDC_PROVIDER + ':sub":"system:serviceaccount:kube-system:aws-load-balancer-controller","' + $OIDC_PROVIDER + ':aud":"sts.amazonaws.com"}}}]}'
        $trust | Out-File -Encoding ascii "$env:TEMP\alb-trust.json"
        aws iam create-role `
          --role-name AmazonEKSLoadBalancerControllerRole `
          --assume-role-policy-document "file://$env:TEMP\alb-trust.json" | Out-Null
        aws iam attach-role-policy `
          --role-name AmazonEKSLoadBalancerControllerRole `
          --policy-arn "arn:aws:iam::${ACCOUNT_ID}:policy/AWSLoadBalancerControllerIAMPolicy"
        Ok "IAM role creado y política adjunta."
    } else {
        Warn "IAM role ya existe, omitiendo creación."
    }

    Step "Instalando/actualizando AWS Load Balancer Controller (Helm)..."
    helm repo add eks https://aws.github.io/eks-charts 2>&1 | Out-Null
    helm repo update eks 2>&1 | Out-Null

    helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller `
      -n kube-system `
      --set clusterName=$CLUSTER `
      "--set=serviceAccount.annotations.eks\.amazonaws\.com/role-arn=arn:aws:iam::${ACCOUNT_ID}:role/AmazonEKSLoadBalancerControllerRole" `
      --set region=$REGION `
      --set vpcId=$VPC_ID `
      --wait --timeout=180s

    Ok "ALB Controller instalado."
    kubectl get pods -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller
}

# ── Paso 5: Build y Push imagen backend ──────────────────────────────────
if (-not $SkipBuild) {
    Step "Build y Push imagen backend → ${ECR}:backend-dev ..."
    aws ecr get-login-password --region $REGION | `
      docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com" 2>&1 | Out-Null

    docker build -t "${ECR}:backend-dev" $BACK_DIR
    if ($LASTEXITCODE -ne 0) { throw "Docker build falló." }

    docker push "${ECR}:backend-dev"
    if ($LASTEXITCODE -ne 0) { throw "Docker push falló." }
    Ok "Imagen publicada en ECR."
}

# ── Paso 6: Manifests K8s ────────────────────────────────────────────────
Step "Aplicando manifests K8s..."
Set-Location (Split-Path $PSScriptRoot -Parent)
kubectl apply -k k8s/eks/
kubectl apply -f k8s/eks/ingress.yaml
Ok "Manifests aplicados."

# ── Paso 7: aws-auth patch ────────────────────────────────────────────────
Step "Parcheando aws-auth ConfigMap..."
$patchFile = "$env:TEMP\aws-auth-patch-full.yaml"
@"
data:
  mapUsers: |
    - userarn: arn:aws:iam::${ACCOUNT_ID}:user/terraform-user
      username: terraform-user
      groups:
      - system:masters
    - userarn: arn:aws:iam::${ACCOUNT_ID}:user/MAIA-scoliosis-user
      username: MAIA-scoliosis-user
      groups:
      - system:masters
"@ | Out-File -Encoding utf8 $patchFile

kubectl patch configmap aws-auth -n kube-system --type merge --patch-file $patchFile
Ok "aws-auth actualizado."

# ── Paso 8: Verificar ────────────────────────────────────────────────────
Step "Verificando despliegue..."
kubectl get pods -n maia

Write-Host "`nEsperando ALB health check..." -ForegroundColor Yellow
Start-Sleep -Seconds 15
$health = curl.exe -s "http://$ALB_DNS/api/v1/health" 2>&1
Ok "Health check: $health"

Write-Host "`n========================================" -ForegroundColor Green
Write-Host " DEPLOY COMPLETO" -ForegroundColor Green
Write-Host " ALB: http://$ALB_DNS" -ForegroundColor Green
Write-Host " Health: http://$ALB_DNS/api/v1/health" -ForegroundColor Green
Write-Host " Pipeline: POST http://$ALB_DNS/api/v1/pipeline/run" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Green
