# EKS deployment flow for MAIA

This folder contains Kubernetes manifests to deploy backend, frontend, redis, and mongo on EKS with AWS Application Load Balancer (ALB).

## Architecture

```
Internet → ALB (DNS: <name>.elb.amazonaws.com)
           ├── / (Frontend, port 3000)
           └── /api/* (Backend, port 8000)
                 ├── Redis (cache)
                 ├── MongoDB (profiles)
                 └── S3 (external storage)
```

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

## 3b) Install AWS Load Balancer Controller

The ALB requires AWS Load Balancer Controller to work with Kubernetes Ingress.

**Quick install (PowerShell - Windows):**

```powershell
.\scripts\install-alb-controller.ps1 -ClusterName "maia-eks" -Region "us-east-1"
```

**Quick install (Bash - Linux/Mac):**

```bash
bash scripts/install-alb-controller.sh maia-eks us-east-1
```

This will:
1. Create OIDC Provider for IAM authentication
2. Create IAM Role for the controller
3. Install AWS Load Balancer Controller via Helm

For manual setup, see [ALB_SETUP.md](ALB_SETUP.md).

## 4) Deploy manifests

```bash
# Apply baseline resources
kubectl apply -k ../../k8s/eks

# Inject real backend image from ECR
kubectl -n maia set image deployment/backend backend=${ECR_REPO}:latest

# Verify
kubectl get pods -n maia
```

## 4b) Create ALB Ingress

Apply the Ingress to create the ALB:

```bash
kubectl apply -f k8s/eks/ingress.yaml
```

Wait for the ALB to be created (1-2 minutes):

```bash
kubectl get ingress -n maia -w
```

Once `ADDRESS` appears, that's your ALB DNS name. Example:

```
NAME                 CLASS   HOSTS   ADDRESS                              PORTS
maia-alb-ingress     alb     *       k8s-maia-xxxxxx-xxxx.elb.us-east-1.amazonaws.com  80
```

Get the ALB URL from Terraform outputs:

```bash
terraform -chdir=infra/terraform output alb_url
```

## 5) Access the application

**Frontend (React UI):**
```bash
curl http://<ALB-DNS>/
```

**Backend API:**
```bash
curl http://<ALB-DNS>/api/v1/health
```

**Normalization profiles:**
```bash
curl http://<ALB-DNS>/api/v1/normalization/profiles/status
```

## 6) Debug traffic locally

```bash
kubectl -n maia port-forward svc/backend 8000:8000
kubectl -n maia port-forward svc/frontend 8080:80
```

Health check:

```bash
curl http://localhost:8000/api/v1/health
```

## Verify ALB health

Check if targets are healthy:

```bash
# Get target group ARN from outputs
TARGET_GROUP_ARN=$(terraform -chdir=infra/terraform output -raw backend_target_group_arn)

# Check target health
aws elbv2 describe-target-health --target-group-arn $TARGET_GROUP_ARN
```

View ALB logs:

```bash
kubectl logs -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller -f
```

## Troubleshooting

### ALB not appearing in Ingress

```bash
# Check Load Balancer Controller status
kubectl get deployment -n kube-system aws-load-balancer-controller
kubectl describe ingress -n maia maia-alb-ingress
```

### Targets are unhealthy

```bash
# Verify backend pod is running and healthy
kubectl get pods -n maia
kubectl logs -n maia -l app=backend

# Test backend directly
kubectl exec -it -n maia <backend-pod> -- curl localhost:8000/api/v1/health
```

### Can't access application

```bash
# Get ALB details
aws elbv2 describe-load-balancers --region us-east-1

# Check security groups
aws ec2 describe-security-groups --filters "Name=group-name,Values=*maia-alb*"

# Test connection to ALB
curl -v http://<ALB-DNS>/
```

## One-command promotion (Windows PowerShell)

From repo root:

```powershell
./scripts/deploy-eks.ps1 -ImageTag latest -Region us-east-1
```

This script builds locally, pushes to ECR, updates kubeconfig, applies manifests, and updates backend image in EKS.

## Notes

- This setup does not create IAM roles in Terraform; it reuses LabRole.
- **ALB is fully automated**: Created by Terraform, controller installed by script, Ingress via kubectl
- ALB DNS is auto-registered and internet-facing
- Health check: `/api/v1/health` on backend (port 8000)
- Routing rules: `/api/*` → backend, `/` → frontend
- If EKS creation fails with IAM permission denied, keep using Minikube for local debug and ECS for AWS runtime until permissions are expanded.
- Frontend is a placeholder NGINX deployment until a real frontend image is available.

## Related files

- `infra/terraform/alb.tf` - ALB Terraform configuration
- `infra/terraform/eks_minimal.tf` - EKS cluster definition
- `k8s/eks/ingress.yaml` - Ingress for ALB
- `k8s/eks/ALB_SETUP.md` - Detailed ALB setup guide
- `scripts/install-alb-controller.ps1` - PowerShell installer
- `scripts/install-alb-controller.sh` - Bash installer
