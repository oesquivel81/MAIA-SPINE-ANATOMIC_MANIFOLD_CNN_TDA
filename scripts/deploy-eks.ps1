param(
    [string]$ImageTag = "latest",
    [string]$Region = "us-east-1"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$tfDir = Join-Path $repoRoot "infra/terraform"
$k8sDir = Join-Path $repoRoot "k8s/eks"

Write-Host "[1/7] Reading Terraform outputs..."
Push-Location $tfDir
$target = terraform output -raw deployment_target
if ($target -ne "eks") {
    throw "Terraform deployment_target is '$target'. Set deployment_target = \"eks\" in infra/terraform/terraform.tfvars and apply first."
}
$ecrRepo = terraform output -raw ecr_repository_url
$eksCluster = terraform output -raw eks_cluster_name
Pop-Location

if ([string]::IsNullOrWhiteSpace($ecrRepo)) {
    throw "ecr_repository_url output is empty. Run terraform apply first."
}
if ([string]::IsNullOrWhiteSpace($eksCluster)) {
    throw "eks_cluster_name output is empty. Run terraform apply in EKS mode first."
}

$registry = $ecrRepo.Split('/')[0]
$imageLocal = "maia-back:$ImageTag"
$imageRemote = "$ecrRepo`:$ImageTag"

Write-Host "[2/7] Building backend image $imageLocal ..."
docker build -t $imageLocal -f "$repoRoot/back/Dockerfile" "$repoRoot/back"

Write-Host "[3/7] Logging in to ECR ($registry)..."
aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin $registry

Write-Host "[4/7] Tagging and pushing image $imageRemote ..."
docker tag $imageLocal $imageRemote
docker push $imageRemote

Write-Host "[5/7] Updating kubeconfig for EKS cluster $eksCluster ..."
aws eks update-kubeconfig --region $Region --name $eksCluster

Write-Host "[6/7] Applying Kubernetes manifests..."
kubectl apply -k $k8sDir
kubectl -n maia set image deployment/backend backend=$imageRemote

Write-Host "[7/7] Waiting for rollout..."
kubectl rollout status deployment/backend -n maia --timeout=240s
kubectl get pods -n maia

Write-Host "Done. Backend image promoted to EKS: $imageRemote"
