# EKS deployment flow for MAIA

This folder contains Kubernetes manifests to deploy backend, frontend, redis, and mongo on EKS.

## 1) Switch Terraform to EKS mode

In infra/terraform/terraform.tfvars set:

```hcl
deployment_target       = "eks"
eks_cluster_version     = "1.30"
eks_node_instance_types = ["t3.medium"]
eks_node_desired_size   = 1
eks_node_min_size       = 1
eks_node_max_size       = 2
```

Then run:

```bash
cd infra/terraform
terraform init
terraform plan
terraform apply
```

## 2) Build image locally and push to ECR

```bash
# Get repository URL from terraform output
ECR_REPO=$(terraform output -raw ecr_repository_url)

# Build local image
docker build -t maia-back:dev -f ../../back/Dockerfile ../../back

# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ${ECR_REPO%/*}

# Tag and push
docker tag maia-back:dev ${ECR_REPO}:latest
docker push ${ECR_REPO}:latest
```

## 3) Configure kubectl for EKS

```bash
EKS_CLUSTER=$(terraform output -raw eks_cluster_name)
aws eks update-kubeconfig --region us-east-1 --name ${EKS_CLUSTER}
kubectl get nodes
```

## 4) Deploy manifests

```bash
# Apply baseline resources
kubectl apply -k ../../k8s/eks

# Inject real backend image from ECR
kubectl -n maia set image deployment/backend backend=${ECR_REPO}:latest

# Verify
kubectl get pods -n maia
```

## 5) Debug traffic locally

```bash
kubectl -n maia port-forward svc/backend 8000:8000
kubectl -n maia port-forward svc/frontend 8080:80
```

Health check:

```bash
curl http://localhost:8000/api/v1/health
```

## One-command promotion (Windows PowerShell)

From repo root:

```powershell
./scripts/deploy-eks.ps1 -ImageTag latest -Region us-east-1
```

This script builds locally, pushes to ECR, updates kubeconfig, applies manifests, and updates backend image in EKS.

## Notes

- This setup does not create IAM roles in Terraform; it reuses LabRole.
- If EKS creation fails with IAM permission denied, keep using Minikube for local debug and ECS for AWS runtime until permissions are expanded.
- Frontend is a placeholder NGINX deployment until a real frontend image is available.
