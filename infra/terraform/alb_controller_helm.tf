# Install AWS Load Balancer Controller via Helm
# This controller watches Ingress resources and creates ALBs automatically

# Add the EKS Helm repository
resource "helm_repository" "eks" {
  count = local.use_eks ? 1 : 0

  name   = "eks"
  url    = "https://aws.github.io/eks-charts"
  repository_ca_file = ""
}

# Create namespace for ALB Controller (kube-system already exists, but we ensure it's there)
resource "kubernetes_namespace" "kube_system" {
  count = local.use_eks ? 1 : 0

  metadata {
    name = "kube-system"
  }

  depends_on = [aws_eks_cluster.maia]
}

# Create service account for ALB Controller
resource "kubernetes_service_account" "aws_load_balancer_controller" {
  count = local.use_eks ? 1 : 0

  metadata {
    name      = "aws-load-balancer-controller"
    namespace = "kube-system"
    annotations = {
      "eks.amazonaws.com/role-arn" = aws_iam_role.alb_controller[0].arn
    }
  }

  depends_on = [kubernetes_namespace.kube_system]
}

# Install ALB Controller using Helm
resource "helm_release" "aws_load_balancer_controller" {
  count = local.use_eks ? 1 : 0

  name             = "aws-load-balancer-controller"
  repository       = helm_repository.eks[0].name
  chart            = "aws-load-balancer-controller"
  namespace        = "kube-system"
  version          = "2.7.0"
  create_namespace = false

  values = [
    jsonencode({
      cluster = {
        name = aws_eks_cluster.maia[0].name
      }
      
      replicaCount = 2
      
      serviceAccount = {
        create = false
        name   = kubernetes_service_account.aws_load_balancer_controller[0].metadata[0].name
      }

      enableShield = false
      enableWaf    = false
      enableWafv2  = false

      logLevel = "info"

      resources = {
        limits = {
          cpu    = "200m"
          memory = "500Mi"
        }
        requests = {
          cpu    = "100m"
          memory = "200Mi"
        }
      }
    })
  ]

  depends_on = [
    kubernetes_service_account.aws_load_balancer_controller,
    aws_eks_node_group.maia,
    aws_iam_role_policy_attachment.alb_controller
  ]
}

# Output ALB Controller deployment status
output "alb_controller_helm_status" {
  description = "Status of the ALB Controller Helm release"
  value       = try(helm_release.aws_load_balancer_controller[0].status, "")
}
