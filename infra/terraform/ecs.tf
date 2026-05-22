# ECS Cluster
resource "aws_ecs_cluster" "maia" {
  count = local.use_ecs ? 1 : 0

  name = "${local.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-cluster"
    }
  )
}

# CloudWatch Log Group for ECS
resource "aws_cloudwatch_log_group" "ecs" {
  count = local.use_ecs ? 1 : 0

  name              = "/ecs/${local.name_prefix}"
  retention_in_days = 7

  tags = merge(
    local.common_tags,
    {
      Name = "/ecs/${local.name_prefix}"
    }
  )
}

# ECS Task Definition
resource "aws_ecs_task_definition" "maia" {
  count = local.use_ecs ? 1 : 0

  family                   = local.name_prefix
  network_mode             = "awsvpc"
  requires_compatibilities = ["EC2"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = var.lab_role_arn
  task_role_arn            = var.lab_role_arn

  container_definitions = jsonencode([
    {
      name      = "maia-backend"
      image     = "${aws_ecr_repository.maia_app.repository_url}:latest"
      essential = true
      portMappings = [
        {
          containerPort = 8000
          hostPort      = 8000
          protocol      = "tcp"
        }
      ]
      environment = [
        {
          name  = "APP_ENV"
          value = var.environment
        },
        {
          name  = "AWS_REGION"
          value = var.aws_region
        },
        {
          name  = "MONGO_URI"
          value = "mongodb://localhost:27017"
        },
        {
          name  = "REDIS_URI"
          value = "redis://localhost:6379/0"
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs[0].name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-task-def"
    }
  )
}
