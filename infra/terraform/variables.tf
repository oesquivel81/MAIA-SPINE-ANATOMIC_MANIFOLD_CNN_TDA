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

variable "s3_bucket_enabled" {
  type        = bool
  description = "Enable S3 bucket creation"
  default     = false
}

variable "s3_bucket_name" {
  type        = string
  description = "S3 bucket name (if empty, will generate a random name)"
  default     = ""
}

variable "s3_bucket_force_destroy" {
  type        = bool
  description = "Force destroy S3 bucket even if it contains objects"
  default     = false
}

variable "k8s_namespace" {
  type        = string
  description = "Kubernetes namespace for the application"
  default     = "default"
}

variable "k8s_service_account_name" {
  type        = string
  description = "Kubernetes service account name"
  default     = "maia-app"
}

variable "hf_target_s3_bucket" {
  type        = string
  description = "HuggingFace target S3 bucket"
  default     = ""
}

variable "existing_vpc_id" {
  type        = string
  description = "Existing VPC ID"
  default     = ""
}

variable "existing_subnet_ids" {
  type        = list(string)
  description = "Existing subnet IDs"
  default     = []
}

variable "lab_role_arn" {
  type        = string
  description = "Lab Role ARN"
  default     = ""
}

variable "hf_sync_enabled" {
  type        = bool
  description = "Enable HuggingFace to S3 sync"
  default     = false
}

variable "hf_token" {
  type        = string
  description = "HuggingFace token"
  default     = ""
  sensitive   = true
}

variable "hf_repo_id" {
  type        = string
  description = "HuggingFace repository ID"
  default     = ""
}

variable "hf_repo_type" {
  type        = string
  description = "HuggingFace repository type (dataset or model)"
  default     = "dataset"
}

variable "hf_revision" {
  type        = string
  description = "HuggingFace repository revision"
  default     = "main"
}

variable "hf_allow_patterns" {
  type        = string
  description = "HuggingFace allow patterns"
  default     = ""
}

variable "hf_ignore_patterns" {
  type        = string
  description = "HuggingFace ignore patterns"
  default     = ""
}

variable "hf_target_s3_prefix" {
  type        = string
  description = "HuggingFace target S3 prefix"
  default     = ""
}

variable "hf_python_executable" {
  type        = string
  description = "Python executable path"
  default     = "python"
}

variable "pipeline_binary_curve_model_key" {
  type        = string
  description = "Pipeline binary curve model S3 key"
  default     = ""
}

variable "pipeline_student_patch_model_key" {
  type        = string
  description = "Pipeline student patch model S3 key"
  default     = ""
}

variable "pipeline_clustering_model_key" {
  type        = string
  description = "Pipeline clustering model S3 key"
  default     = ""
}

variable "pipeline_normalization_profile_jsonl_key" {
  type        = string
  description = "Pipeline normalization profile JSONL S3 key"
  default     = ""
}

variable "pipeline_resources_prefix_key" {
  type        = string
  description = "Pipeline resources prefix S3 key"
  default     = ""
}
