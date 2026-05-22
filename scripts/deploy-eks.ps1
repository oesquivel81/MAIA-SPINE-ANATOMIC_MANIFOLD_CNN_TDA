param(
    [string]$Region = "us-east-1",
    # -SkipBackend : omite build/push del backend
    [switch]$SkipBackend,
    # -SkipFrontend : omite build/push del frontend
    [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"

$repoRoot  = Split-Path -Parent $PSScriptRoot
$tfDir     = Join-Path $repoRoot "infra/terraform"
$k8sDir    = Join-Path $repoRoot "k8s/eks"

# -- 1. Leer outputs de Terraform
Write-Host "[1] Reading Terraform outputs..."
Push-Location $tfDir
$target = terraform output -raw deployment_target
if ($target -ne "eks") {
    throw "Terraform deployment_target is '$target'. Set deployment_target = ""eks"" in terraform.tfvars and apply first."
}
$ecrRepo    = terraform output -raw ecr_repository_url
$eksCluster = terraform output -raw eks_cluster_name
Pop-Location

if ([string]::IsNullOrWhiteSpace($ecrRepo))    { throw "ecr_repository_url empty. Run terraform apply first." }
if ([string]::IsNullOrWhiteSpace($eksCluster)) { throw "eks_cluster_name empty. Run terraform apply first." }

$registry      = $ecrRepo.Split('/')[0]
$backendImage  = "$ecrRepo`:backend-dev"
$frontendImage = "$ecrRepo`:frontend-dev"

# -- 2. Login ECR
Write-Host "[2] Logging in to ECR ($registry)..."
aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin $registry

# -- 3. Build & push Backend
if (-not $SkipBackend) {
    Write-Host "[3] Building and pushing BACKEND image -> $backendImage ..."
    docker buildx build `
        --builder ecr-builder `
        --platform linux/amd64 `
        --push `
        --tag $backendImage `
        --file "$repoRoot\back\Dockerfile" `
        "$repoRoot\back"
} else {
    Write-Host "[3] Skipping backend build (-SkipBackend)."
}

# -- 4. Build & push Frontend
if (-not $SkipFrontend) {
    Write-Host "[4] Building and pushing FRONTEND image -> $frontendImage ..."
    docker buildx build `
        --builder ecr-builder `
        --platform linux/amd64 `
        --push `
        --tag $frontendImage `
        --file "$repoRoot\front\Dockerfile" `
        "$repoRoot\front"
} else {
    Write-Host "[4] Skipping frontend build (-SkipFrontend)."
}

# -- 5. Kubeconfig
Write-Host "[5] Updating kubeconfig for EKS cluster $eksCluster ..."
aws eks update-kubeconfig --region $Region --name $eksCluster

# -- 6. Aplicar manifests
Write-Host "[6] Applying Kubernetes manifests..."
kubectl apply -k $k8sDir
kubectl apply -f "$k8sDir\ingress.yaml"

if (-not $SkipBackend) {
    kubectl -n maia set image deployment/backend  backend=$backendImage
}
if (-not $SkipFrontend) {
    kubectl -n maia set image deployment/frontend frontend=$frontendImage
}

# -- 7. Rollouts
Write-Host "[7] Waiting for rollouts..."
if (-not $SkipBackend)  { kubectl rollout status deployment/backend  -n maia --timeout=240s }
if (-not $SkipFrontend) { kubectl rollout status deployment/frontend -n maia --timeout=240s }

kubectl get pods -n maia

$albHost = kubectl get ingress maia-alb-ingress-frontend -n maia -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>$null

Write-Host ""
Write-Host "Done."
Write-Host "  Backend  -> $backendImage"
Write-Host "  Frontend -> $frontendImage"
if ($albHost) { Write-Host "  ALB      -> http://$albHost" }
