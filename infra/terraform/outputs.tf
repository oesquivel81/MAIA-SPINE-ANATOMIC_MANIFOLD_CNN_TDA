output "region" {
  description = "AWS region"
  value       = var.aws_region
}

output "vpc_id" {
  description = "Default VPC ID"
  value       = data.aws_vpc.default.id
}

output "ecr_repository_url" {
  description = "ECR repository URL"
  value       = aws_ecr_repository.maia_app.repository_url
}

output "ecr_repository_name" {
  description = "ECR repository name"
  value       = aws_ecr_repository.maia_app.name
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = try(aws_ecs_cluster.maia[0].name, null)
}

output "ecs_cluster_arn" {
  description = "ECS cluster ARN"
  value       = try(aws_ecs_cluster.maia[0].arn, null)
}

output "ecs_task_definition_arn" {
  description = "ECS task definition ARN"
  value       = try(aws_ecs_task_definition.maia[0].arn, null)
}

output "security_group_id" {
  description = "Security group ID for app"
  value       = aws_security_group.maia_app.id
}

output "lab_role_arn" {
  description = "LabRole ARN"
  value       = var.lab_role_arn
}

output "log_group_name" {
  description = "CloudWatch Log Group name"
  value       = try(aws_cloudwatch_log_group.ecs[0].name, null)
}

output "deployment_target" {
  description = "Selected deployment target"
  value       = var.deployment_target
}

output "eks_cluster_name" {
  description = "EKS cluster name"
  value       = try(aws_eks_cluster.maia[0].name, null)
}

output "eks_cluster_arn" {
  description = "EKS cluster ARN"
  value       = try(aws_eks_cluster.maia[0].arn, null)
}

output "eks_cluster_endpoint" {
  description = "EKS cluster API endpoint"
  value       = try(aws_eks_cluster.maia[0].endpoint, null)
}

output "eks_node_group_name" {
  description = "EKS managed node group name"
  value       = try(aws_eks_node_group.maia[0].node_group_name, null)
}
