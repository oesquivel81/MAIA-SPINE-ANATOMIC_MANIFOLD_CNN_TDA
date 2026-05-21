resource "random_id" "bucket_suffix" {
  count       = var.s3_bucket_enabled && trimspace(var.s3_bucket_name) == "" ? 1 : 0
  byte_length = 4
}

resource "aws_s3_bucket" "artifacts" {
  count = var.s3_bucket_enabled ? 1 : 0

  bucket = trimspace(var.s3_bucket_name) != "" ? trimspace(var.s3_bucket_name) : "${local.name_prefix}-artifacts-${random_id.bucket_suffix[0].hex}"

  force_destroy = var.s3_bucket_force_destroy

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-artifacts"
  })
}

resource "aws_s3_bucket_versioning" "artifacts" {
  count  = var.s3_bucket_enabled ? 1 : 0
  bucket = aws_s3_bucket.artifacts[0].id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  count  = var.s3_bucket_enabled ? 1 : 0
  bucket = aws_s3_bucket.artifacts[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  count  = var.s3_bucket_enabled ? 1 : 0
  bucket = aws_s3_bucket.artifacts[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
