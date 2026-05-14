provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}

# Kubernetes provider for EKS
provider "kubernetes" {
  host                   = try(aws_eks_cluster.maia[0].endpoint, "")
  cluster_ca_certificate = try(base64decode(aws_eks_cluster.maia[0].certificate_authority[0].data), "")
  token                  = try(data.aws_eks_cluster_auth.maia[0].token, "")

  skip_credentials_validation = false
  skip_metadata_api_check     = false
}

# Helm provider for EKS
provider "helm" {
  kubernetes {
    host                   = try(aws_eks_cluster.maia[0].endpoint, "")
    cluster_ca_certificate = try(base64decode(aws_eks_cluster.maia[0].certificate_authority[0].data), "")
    token                  = try(data.aws_eks_cluster_auth.maia[0].token, "")
  }
}

# Data source to authenticate with EKS cluster
data "aws_eks_cluster_auth" "maia" {
  count = local.use_eks ? 1 : 0
  name  = aws_eks_cluster.maia[0].name
}
