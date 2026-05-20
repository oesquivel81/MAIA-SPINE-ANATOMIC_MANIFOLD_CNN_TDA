# IAM Role and Policy for AWS Load Balancer Controller
# DISABLED: voclabs (AWS Academy) does not allow iam:TagPolicy or iam:CreateRole
# ALB Controller not needed for local debugging via port-forward

data "http" "alb_controller_policy" {
  url = "https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.7.0/docs/install/iam_policy.json"
}

output "alb_controller_role_arn" {
  description = "ARN of the IAM role for ALB Controller (disabled)"
  value       = ""
}
