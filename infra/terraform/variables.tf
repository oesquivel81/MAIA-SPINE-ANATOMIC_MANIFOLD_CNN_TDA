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
