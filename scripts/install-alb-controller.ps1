#!/usr/bin/env pwsh

# Script para instalar AWS Load Balancer Controller en EKS (Windows PowerShell)
# Uso: .\install-alb-controller.ps1 -ClusterName "maia-eks" -Region "us-east-1"

param(
    [Parameter(Mandatory=$true)]
    [string]$ClusterName = "maia-eks",
    
    [Parameter(Mandatory=$false)]
    [string]$Region = "us-east-1"
)

$ErrorActionPreference = "Stop"

Write-Host "🔧 Instalando AWS Load Balancer Controller" -ForegroundColor Cyan
Write-Host "   Cluster: $ClusterName" -ForegroundColor Gray
Write-Host "   Region: $Region" -ForegroundColor Gray
Write-Host ""

# Obtener Account ID
$ACCOUNT_ID = (aws sts get-caller-identity --query "Account" --output text)
Write-Host "   Account: $ACCOUNT_ID" -ForegroundColor Gray
Write-Host ""

try {
    # Paso 1: OIDC Provider
    Write-Host "📝 Paso 1: Creando OIDC Provider..." -ForegroundColor Yellow
    $OIDC_ISSUE = aws eks describe-cluster --name $ClusterName --region $Region --query "cluster.identity.oidc.issuer" --output text
    $OIDC_ID = $OIDC_ISSUE.Split('/')[-1]
    $OIDC_PROVIDER = "oidc.eks.${Region}.amazonaws.com/id/${OIDC_ID}"

    aws iam create-open-id-connect-provider `
        --url "https://oidc.eks.${Region}.amazonaws.com/id/${OIDC_ID}" `
        --client-id-list sts.amazonaws.com `
        --thumbprint-list 1b511abead59c6ce207077c0ef0285eea7d6491fa6 `
        --region $Region 2>$null
    Write-Host "✓ OIDC Provider listo" -ForegroundColor Green
}
catch {
    Write-Host "✓ OIDC Provider ya existe" -ForegroundColor Green
}

try {
    # Paso 2: Descargar política
    Write-Host ""
    Write-Host "📝 Paso 2: Descargando política IAM..." -ForegroundColor Yellow
    $policyUrl = "https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.6.0/docs/install/iam_policy.json"
    Invoke-WebRequest -Uri $policyUrl -OutFile "/tmp/iam-policy.json" -ErrorAction SilentlyContinue
    Write-Host "✓ Política descargada" -ForegroundColor Green

    # Paso 3: Crear IAM Policy
    Write-Host ""
    Write-Host "📝 Paso 3: Creando IAM Policy..." -ForegroundColor Yellow
    aws iam create-policy `
        --policy-name AWSLoadBalancerControllerIAMPolicy `
        --policy-document file:///tmp/iam-policy.json `
        --region $Region 2>$null
    Write-Host "✓ IAM Policy creada" -ForegroundColor Green
}
catch {
    Write-Host "✓ IAM Policy ya existe" -ForegroundColor Green
}

try {
    # Paso 4: Crear IAM Role
    Write-Host ""
    Write-Host "📝 Paso 4: Creando IAM Role..." -ForegroundColor Yellow
    
    $trustPolicy = @"
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::${ACCOUNT_ID}:oidc-provider/${OIDC_PROVIDER}"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "${OIDC_PROVIDER}:sub": "system:serviceaccount:kube-system:aws-load-balancer-controller"
        }
      }
    }
  ]
}
"@

    aws iam create-role `
        --role-name AmazonEKSLoadBalancerControllerRole `
        --assume-role-policy-document $trustPolicy `
        --region $Region 2>$null
    Write-Host "✓ IAM Role creado" -ForegroundColor Green
}
catch {
    Write-Host "✓ IAM Role ya existe" -ForegroundColor Green
}

try {
    # Paso 5: Adjuntar política
    Write-Host ""
    Write-Host "📝 Paso 5: Adjuntando política IAM..." -ForegroundColor Yellow
    aws iam attach-role-policy `
        --role-name AmazonEKSLoadBalancerControllerRole `
        --policy-arn "arn:aws:iam::${ACCOUNT_ID}:policy/AWSLoadBalancerControllerIAMPolicy" `
        --region $Region 2>$null
    Write-Host "✓ Política adjunta" -ForegroundColor Green
}
catch {
    Write-Host "✓ Política ya adjunta" -ForegroundColor Green
}

# Paso 6: Helm setup
Write-Host ""
Write-Host "📝 Paso 6: Preparando Helm..." -ForegroundColor Yellow
helm repo add eks https://aws.github.io/eks-charts
helm repo update

# Paso 7: Actualizar kubeconfig
Write-Host ""
Write-Host "📝 Paso 7: Actualizando kubeconfig..." -ForegroundColor Yellow
aws eks update-kubeconfig --name $ClusterName --region $Region

# Paso 8: Instalar con Helm
Write-Host ""
Write-Host "📝 Paso 8: Instalando AWS Load Balancer Controller..." -ForegroundColor Yellow
helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller `
    -n kube-system `
    --set clusterName=$ClusterName `
    --set serviceAccount.annotations."eks\.amazonaws\.com/role-arn"="arn:aws:iam::${ACCOUNT_ID}:role/AmazonEKSLoadBalancerControllerRole" `
    --wait

Write-Host "✓ Helm chart instalado" -ForegroundColor Green

# Verificación final
Write-Host ""
Write-Host "📝 Verificando instalación..." -ForegroundColor Yellow
kubectl rollout status deployment/aws-load-balancer-controller -n kube-system --timeout=180s
Write-Host ""
Write-Host "✅ AWS Load Balancer Controller instalado exitosamente" -ForegroundColor Green
Write-Host ""
Write-Host "🚀 Próximos pasos:" -ForegroundColor Cyan
Write-Host "   1. Aplicar el Ingress: kubectl apply -f k8s/eks/ingress.yaml"
Write-Host "   2. Verificar: kubectl get ingress -n maia -w"
Write-Host "   3. Esperar a que obtenga ADDRESS (DNS del ALB)"
