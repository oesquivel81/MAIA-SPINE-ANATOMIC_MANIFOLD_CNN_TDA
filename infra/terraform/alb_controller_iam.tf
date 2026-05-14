# IAM Role and Policy for AWS Load Balancer Controller
# This role is used by the ALB Controller to manage load balancers

# Read the ALB Controller policy from AWS
data "http" "alb_controller_policy" {
  url = "https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.7.0/docs/install/iam_policy.json"
}

# Create IAM Policy for ALB Controller
resource "aws_iam_policy" "alb_controller" {
  count = local.use_eks ? 1 : 0

  name        = "${local.name_prefix}-alb-controller-policy"
  description = "Policy for AWS Load Balancer Controller"
  policy      = data.http.alb_controller_policy.response_body

  tags = local.common_tags
}

# Create IAM Role for ALB Controller
resource "aws_iam_role" "alb_controller" {
  count = local.use_eks ? 1 : 0

  name               = "${local.name_prefix}-alb-controller-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.eks[0].arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${replace(aws_iam_openid_connect_provider.eks[0].url, "https://", "")}:sub" = "system:serviceaccount:kube-system:aws-load-balancer-controller"
            "${replace(aws_iam_openid_connect_provider.eks[0].url, "https://", "")}:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  })

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-alb-controller-role"
    }
  )
}

# Attach policy to role
resource "aws_iam_role_policy_attachment" "alb_controller" {
  count = local.use_eks ? 1 : 0

  role       = aws_iam_role.alb_controller[0].name
  policy_arn = aws_iam_policy.alb_controller[0].arn
}

# Output the role ARN for reference
output "alb_controller_role_arn" {
  description = "ARN of the IAM role for ALB Controller"
  value       = try(aws_iam_role.alb_controller[0].arn, "")
}
