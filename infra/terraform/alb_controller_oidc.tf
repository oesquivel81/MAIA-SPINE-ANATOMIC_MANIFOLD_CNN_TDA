# OIDC Provider for IAM authentication with EKS
# This allows IAM roles to be used by Kubernetes service accounts

# Get the thumbprint of the OIDC provider
data "tls_certificate" "eks" {
  count = local.use_eks ? 1 : 0
  url   = aws_eks_cluster.maia[0].identity[0].oidc[0].issuer
}

# Create OIDC Provider
resource "aws_iam_openid_connect_provider" "eks" {
  count = local.use_eks ? 1 : 0

  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.eks[0].certificates[0].sha1_fingerprint]
  url             = aws_eks_cluster.maia[0].identity[0].oidc[0].issuer

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-oidc"
    }
  )
}
