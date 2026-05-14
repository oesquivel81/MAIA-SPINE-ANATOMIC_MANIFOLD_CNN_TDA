variable "project_name" {
  type        = string
  description = "Project name"
  default     = "maia"
}

variable "environment" {
  type        = string
  description = "Environment (dev, staging, prod)"
  default     = "dev"
}

variable "aws_region" {
  type        = string
  description = "AWS region"
  default     = "us-east-1"
}

variable "app_port" {
  type        = number
  description = "Application port"
  default     = 8000
}

variable "deployment_target" {
  type        = string
  description = "Deployment target: ecs or eks"
  default     = "ecs"

  validation {
    condition     = contains(["ecs", "eks"], var.deployment_target)
    error_message = "deployment_target must be one of: ecs, eks"
  }
}

variable "eks_cluster_version" {
  type        = string
  description = "EKS cluster Kubernetes version"
  default     = "1.30"
}

variable "eks_node_instance_types" {
  type        = list(string)
  description = "EKS managed node group instance types"
  default     = ["t3.medium"]
}

variable "eks_node_desired_size" {
  type        = number
  description = "Desired number of nodes for EKS managed node group"
  default     = 1
}

variable "eks_node_min_size" {
  type        = number
  description = "Minimum number of nodes for EKS managed node group"
  default     = 1
}

variable "eks_node_max_size" {
  type        = number
  description = "Maximum number of nodes for EKS managed node group"
  default     = 2
}
