# ECR Repository for MAIA backend
resource "aws_ecr_repository" "maia_app" {
  name                 = "${local.name_prefix}-ecr"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-ecr"
    }
  )
}

# Lifecycle policy to keep only last 5 images
resource "aws_ecr_lifecycle_policy" "maia_app_lifecycle" {
  repository = aws_ecr_repository.maia_app.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 5 images"
        selection = {
          tagStatus     = "any"
          countType     = "imageCountMoreThan"
          countNumber   = 5
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
