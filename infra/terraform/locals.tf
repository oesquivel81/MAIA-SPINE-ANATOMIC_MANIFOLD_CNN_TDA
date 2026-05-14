locals {
  name_prefix = "${var.project_name}-${var.environment}"
  app_name    = local.name_prefix
  use_ecs     = var.deployment_target == "ecs"
  use_eks     = var.deployment_target == "eks"

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
