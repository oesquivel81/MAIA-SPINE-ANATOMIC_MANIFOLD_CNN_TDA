data "aws_iam_policy_document" "s3_rw_for_app" {
  count = var.s3_bucket_enabled ? 1 : 0

  statement {
    sid = "ListBucket"

    actions = [
      "s3:ListBucket",
      "s3:GetBucketLocation"
    ]

    resources = [
      aws_s3_bucket.artifacts[0].arn
    ]
  }

  statement {
    sid = "ObjectRW"

    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject"
    ]

    resources = [
      "${aws_s3_bucket.artifacts[0].arn}/*"
    ]
  }
}

resource "aws_iam_policy" "s3_rw_for_app" {
  count       = var.s3_bucket_enabled ? 1 : 0
  name        = "${local.name_prefix}-s3-rw"
  description = "RW access to MAIA artifacts bucket"
  policy      = data.aws_iam_policy_document.s3_rw_for_app[0].json
}

data "aws_iam_policy_document" "irsa_assume_role" {
  count = local.use_eks ? 1 : 0

  statement {
    effect = "Allow"

    actions = [
      "sts:AssumeRoleWithWebIdentity"
    ]

    principals {
      type = "Federated"

      identifiers = [
        aws_iam_openid_connect_provider.eks[0].arn
      ]
    }

    condition {
      test     = "StringEquals"
      variable = "${replace(aws_eks_cluster.maia[0].identity[0].oidc[0].issuer, "https://", "")}:sub"
      values   = ["system:serviceaccount:${var.k8s_namespace}:${var.k8s_service_account_name}"]
    }

    condition {
      test     = "StringEquals"
      variable = "${replace(aws_eks_cluster.maia[0].identity[0].oidc[0].issuer, "https://", "")}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "app_irsa_role" {
  count              = local.use_eks ? 1 : 0
  name               = "${local.name_prefix}-app-irsa-role"
  assume_role_policy = data.aws_iam_policy_document.irsa_assume_role[0].json

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "app_s3_rw" {
  count      = var.s3_bucket_enabled && local.use_eks ? 1 : 0
  role       = aws_iam_role.app_irsa_role[0].name
  policy_arn = aws_iam_policy.s3_rw_for_app[0].arn
}

# IAM Role for EKS Cluster Control Plane
resource "aws_iam_role" "eks_cluster" {
  count = local.use_eks ? 1 : 0
  name  = "${local.name_prefix}-eks-cluster-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "eks.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "eks_cluster_policy" {
  count      = local.use_eks ? 1 : 0
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.eks_cluster[0].name
}

# IAM Role for EKS Node Group (worker nodes)
resource "aws_iam_role" "eks_node" {
  count = local.use_eks ? 1 : 0
  name  = "${local.name_prefix}-eks-node-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "eks_node_worker_policy" {
  count      = local.use_eks ? 1 : 0
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
  role       = aws_iam_role.eks_node[0].name
}

resource "aws_iam_role_policy_attachment" "eks_node_cni_policy" {
  count      = local.use_eks ? 1 : 0
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
  role       = aws_iam_role.eks_node[0].name
}

resource "aws_iam_role_policy_attachment" "eks_node_ecr_policy" {
  count      = local.use_eks ? 1 : 0
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
  role       = aws_iam_role.eks_node[0].name
}
