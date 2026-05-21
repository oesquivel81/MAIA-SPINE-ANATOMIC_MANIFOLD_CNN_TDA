resource "terraform_data" "hf_to_s3_sync" {
  count = var.hf_sync_enabled ? 1 : 0

  depends_on = [aws_s3_bucket.artifacts]

  lifecycle {
    precondition {
      condition     = length(trimspace(var.hf_repo_id)) > 0
      error_message = "hf_repo_id is required when hf_sync_enabled=true"
    }
    precondition {
      condition     = length(trimspace(local.pipeline_bucket_name)) > 0
      error_message = "No S3 bucket available for sync. Define hf_target_s3_bucket or enable/create artifacts bucket"
    }
  }

  triggers_replace = [
    var.hf_repo_id,
    var.hf_repo_type,
    var.hf_revision,
    var.hf_allow_patterns,
    var.hf_ignore_patterns,
    local.pipeline_bucket_name,
    var.hf_target_s3_prefix,
  ]

  provisioner "local-exec" {
    command = "\"${var.hf_python_executable}\" \"${path.module}/scripts/hf_to_s3_sync.py\""

    environment = {
      HF_TOKEN            = var.hf_token
      HF_REPO_ID          = var.hf_repo_id
      HF_REPO_TYPE        = var.hf_repo_type
      HF_REVISION         = var.hf_revision
      HF_ALLOW_PATTERNS   = var.hf_allow_patterns
      HF_IGNORE_PATTERNS  = var.hf_ignore_patterns
      HF_LOCAL_DIR        = "${path.module}/.hf_cache"
      HF_TARGET_S3_BUCKET = local.pipeline_bucket_name
      HF_TARGET_S3_PREFIX = var.hf_target_s3_prefix
      AWS_REGION          = var.aws_region
    }
  }
}
