# EKS cluster using IAM roles created in iam.tf
resource "aws_eks_cluster" "maia" {
  count = local.use_eks ? 1 : 0

  name     = "${local.name_prefix}-eks"
  role_arn = aws_iam_role.eks_cluster[0].arn
  version  = var.eks_cluster_version

  vpc_config {
    subnet_ids              = data.aws_subnets.eks_supported.ids
    endpoint_public_access  = true
    endpoint_private_access = false
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-eks"
    }
  )

  depends_on = [aws_iam_role_policy_attachment.eks_cluster_policy]
}

resource "aws_eks_node_group" "maia" {
  count = local.use_eks ? 1 : 0

  cluster_name    = aws_eks_cluster.maia[0].name
  node_group_name = "${local.name_prefix}-ng"
  node_role_arn   = aws_iam_role.eks_node[0].arn
  subnet_ids      = data.aws_subnets.eks_supported.ids
  instance_types  = var.eks_node_instance_types

  scaling_config {
    desired_size = var.eks_node_desired_size
    min_size     = var.eks_node_min_size
    max_size     = var.eks_node_max_size
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-ng"
    }
  )

  depends_on = [
    aws_eks_cluster.maia,
    aws_iam_role_policy_attachment.eks_node_worker_policy,
    aws_iam_role_policy_attachment.eks_node_cni_policy,
    aws_iam_role_policy_attachment.eks_node_ecr_policy,
  ]
}

# OIDC Provider for IRSA
data "tls_certificate" "eks_oidc" {
  count = local.use_eks ? 1 : 0
  url   = aws_eks_cluster.maia[0].identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "eks" {
  count           = local.use_eks ? 1 : 0
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.eks_oidc[0].certificates[0].sha1_fingerprint]
  url             = aws_eks_cluster.maia[0].identity[0].oidc[0].issuer

  tags = local.common_tags
}
