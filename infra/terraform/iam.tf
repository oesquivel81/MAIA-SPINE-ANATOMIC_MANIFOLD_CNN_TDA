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
        aws_eks_cluster.maia[0].arn
      ]
    }

    condition {
      test     = "StringEquals"
      variable = "${replace(aws_eks_cluster.maia[0].endpoint, "https://", "")}:sub"
      values   = ["system:serviceaccount:${var.k8s_namespace}:${var.k8s_service_account_name}"]
    }

    condition {
      test     = "StringEquals"
      variable = "${replace(aws_eks_cluster.maia[0].endpoint, "https://", "")}:aud"
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
