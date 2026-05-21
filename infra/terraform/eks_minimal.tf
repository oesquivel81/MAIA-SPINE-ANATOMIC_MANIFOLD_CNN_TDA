# Minimal EKS cluster using existing LabRole (no IAM creation).
# This is intended for restricted lab accounts.
resource "aws_eks_cluster" "maia" {
  count = local.use_eks ? 1 : 0

  name     = "${local.name_prefix}-eks"
  role_arn = var.lab_role_arn
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
}

resource "aws_eks_node_group" "maia" {
  count = local.use_eks ? 1 : 0

  cluster_name    = aws_eks_cluster.maia[0].name
  node_group_name = "${local.name_prefix}-ng"
  node_role_arn   = var.lab_role_arn
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

  depends_on = [aws_eks_cluster.maia]
}
