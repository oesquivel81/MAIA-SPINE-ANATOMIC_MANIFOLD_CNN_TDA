# MAIA Terraform Infrastructure - ECS or EKS (Lab Friendly)

## Overview

This Terraform configuration deploys a lab-friendly infrastructure for MAIA without creating new IAM roles or VPC resources. It uses:

- **Default VPC** (data source)
- **Existing LabRole** (data source) 
- **ECR** (Elastic Container Registry) - for Docker image storage
- **ECS** or **EKS** (selectable via `deployment_target`)
- **CloudWatch Logs** - for application logging
- **Security Groups** - for network access control

## Deployment modes

- `deployment_target = "ecs"`: Creates ECR + ECS resources
- `deployment_target = "eks"`: Creates ECR + EKS cluster + managed node group

Both modes reuse the existing `LabRole` via data source and do not create IAM roles.

## Architecture (ECS mode)

```
Default VPC (existing)
  └── Default Subnets (existing)
      └── ECS Cluster (maia-dev-cluster)
          └── Task Definition (maia-dev)
              └── Container using ECR image
                  └── LabRole (existing IAM role)
```

## Resources Created

| Resource | Name | Purpose |
|----------|------|---------|
| ECR Repository | `maia-dev-ecr` | Docker image storage |
| ECS Cluster | `maia-dev-cluster` | Container orchestration |
| ECS Task Definition | `maia-dev` | Container configuration |
| CloudWatch Log Group | `/ecs/maia-dev` | Application logs |
| Security Group | `maia-dev-app-sg` | Network access control |
| Ingress Rules | HTTP, HTTPS, 8000 | Allow external traffic |
| Egress Rules | All | Allow outbound traffic |

## Prerequisites

```bash
# AWS CLI configured with credentials
aws configure

# Terraform installed
terraform --version

# AWS account with EC2, ECR, ECS permissions (no IAM creation required)
```

## Deployment

### 1. Initialize Terraform

```bash
cd infra/terraform
terraform init
```

### 2. Validate Configuration

```bash
terraform validate
```

### 3. Review Plan

```bash
terraform plan
```

If you want EKS mode, set this first in `terraform.tfvars`:

```hcl
deployment_target       = "eks"
eks_cluster_version     = "1.30"
eks_node_instance_types = ["t3.medium"]
eks_node_desired_size   = 1
eks_node_min_size       = 1
eks_node_max_size       = 2
```

### 4. Apply Configuration

```bash
terraform apply
```

## Outputs

After successful apply, you'll get:

```
ecr_repository_name        = "maia-dev-ecr"
ecr_repository_url         = "847964925141.dkr.ecr.us-east-1.amazonaws.com/maia-dev-ecr"
ecs_cluster_name           = "maia-dev-cluster"
ecs_cluster_arn            = "arn:aws:ecs:us-east-1:847964925141:cluster/maia-dev-cluster"
ecs_task_definition_arn    = "arn:aws:ecs:us-east-1:847964925141:task-definition/maia-dev:1"
lab_role_arn               = "arn:aws:iam::847964925141:role/LabRole"
log_group_name             = "/ecs/maia-dev"
security_group_id          = "sg-048dddab4a7cf5244"
vpc_id                     = "vpc-09eacda65f1228cbc"
```

## Push Docker Image to ECR

```bash
# 1. Get ECR login
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  847964925141.dkr.ecr.us-east-1.amazonaws.com

# 2. Build Docker image
docker build -t maia-backend:latest -f back/Dockerfile back/

# 3. Tag for ECR
docker tag maia-backend:latest \
  847964925141.dkr.ecr.us-east-1.amazonaws.com/maia-dev-ecr:latest

# 4. Push to ECR
docker push 847964925141.dkr.ecr.us-east-1.amazonaws.com/maia-dev-ecr:latest
```

## Files

| File | Purpose |
|------|---------|
| `providers.tf` | AWS provider configuration |
| `versions.tf` | Terraform and provider versions |
| `variables.tf` | Input variables |
| `locals.tf` | Local values (name prefix, tags) |
| `data_sources.tf` | Data sources (VPC, subnets, LabRole) |
| `ecr.tf` | ECR repository and lifecycle policy |
| `ecs.tf` | ECS cluster, task definition, log group |
| `eks_minimal.tf` | Minimal EKS cluster and managed node group |
| `security_groups.tf` | Security groups and ingress/egress rules |
| `outputs.tf` | Output values |

## Important Notes

1. **No IAM Creation**: This configuration uses the existing `LabRole` and does NOT create new IAM roles
2. **No VPC Creation**: Uses AWS default VPC and subnets
3. **Lab-Friendly**: Designed for AWS lab environments with permission restrictions
4. **Task Role**: ECS tasks execute with `LabRole` permissions
5. **Execution Role**: Same as task role for simplicity

## Disabled Files

The following files from the original configuration have been disabled:

- `eks.tf.disabled` - EKS cluster (Kubernetes) not used
- `network.tf.disabled` - VPC/subnet creation (using default VPC)
- `iam.tf.disabled` - IAM role creation (using existing LabRole)
- `s3.tf.disabled` - S3 bucket (can be added separately if needed)

## Next Steps

1. Push Docker image to ECR (see instructions above)
2. For EKS mode, follow `k8s/eks/README.md` to apply manifests and set backend image
3. Add Application Load Balancer (ALB) for traffic distribution if permissions allow
4. Configure CloudWatch alarms and monitoring
5. Set up CI/CD pipeline for automated deployments

## Cleanup

To destroy all resources created by Terraform:

```bash
terraform destroy
```

## Troubleshooting

**Error: unable to get role (LabRole)**
- Verify AWS credentials are configured
- Ensure LabRole exists in your AWS account
- Check IAM permissions for the current user

**Error: Could not create ECR repository**
- Verify ECR permissions (ecr:CreateRepository)
- Check if repository already exists

**Error: Could not create ECS cluster**
- Verify ECS permissions (ecs:CreateCluster)
- Check AWS service quotas for ECS

## References

- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [AWS ECR Documentation](https://docs.aws.amazon.com/ecr/)
- [AWS ECS Documentation](https://docs.aws.amazon.com/ecs/)
- [AWS Default VPC](https://docs.aws.amazon.com/vpc/latest/userguide/default-vpc.html)

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: maia-app
  namespace: default
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::<account-id>:role/<role-name>
```

## Security notes

- Replace `cluster_endpoint_public_access_cidrs = ["0.0.0.0/0"]` by your real CIDRs.
- Keep `terraform.tfvars` private. It is excluded by `.gitignore`.
- For production, move state to a remote backend (S3 + DynamoDB lock).

## Destroy

```bash
terraform destroy
```
