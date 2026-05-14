# Application Load Balancer para EKS
# Solo se crea si estamos usando EKS

resource "aws_security_group" "alb" {
  count = local.use_eks ? 1 : 0

  name        = "${local.app_name}-alb-sg"
  description = "Security group para ALB de MAIA"
  vpc_id      = data.aws_vpc.main.id

  tags = local.common_tags
}

# Ingress HTTP
resource "aws_security_group_rule" "alb_ingress_http" {
  count = local.use_eks ? 1 : 0

  type              = "ingress"
  from_port         = 80
  to_port           = 80
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.alb[0].id
}

# Ingress HTTPS (para futura expansión)
resource "aws_security_group_rule" "alb_ingress_https" {
  count = local.use_eks ? 1 : 0

  type              = "ingress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.alb[0].id
}

# Egress (permitir todo hacia adentro de la VPC)
resource "aws_security_group_rule" "alb_egress" {
  count = local.use_eks ? 1 : 0

  type              = "egress"
  from_port         = 0
  to_port           = 65535
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.alb[0].id
}

# Application Load Balancer
resource "aws_lb" "maia" {
  count = local.use_eks ? 1 : 0

  name               = "${local.app_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb[0].id]
  subnets            = data.aws_subnets.eks_supported.ids

  enable_deletion_protection = false

  tags = merge(
    local.common_tags,
    {
      Name = "${local.app_name}-alb"
    }
  )
}

# Target Group para Backend (port 8000)
resource "aws_lb_target_group" "backend" {
  count = local.use_eks ? 1 : 0

  name        = "${local.app_name}-backend-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = data.aws_vpc.main.id
  target_type = "ip"

  health_check {
    healthy_threshold   = 2
    unhealthy_threshold = 2
    timeout             = 5
    interval            = 30
    path                = "/api/v1/health"
    matcher             = "200"
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${local.app_name}-backend-tg"
    }
  )
}

# Target Group para Frontend (port 3000)
resource "aws_lb_target_group" "frontend" {
  count = local.use_eks ? 1 : 0

  name        = "${local.app_name}-frontend-tg"
  port        = 3000
  protocol    = "HTTP"
  vpc_id      = data.aws_vpc.main.id
  target_type = "ip"

  health_check {
    healthy_threshold   = 2
    unhealthy_threshold = 2
    timeout             = 5
    interval            = 30
    path                = "/"
    matcher             = "200-499"
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${local.app_name}-frontend-tg"
    }
  )
}

# Listener para HTTP (default al frontend)
resource "aws_lb_listener" "http" {
  count = local.use_eks ? 1 : 0

  load_balancer_arn = aws_lb.maia[0].arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend[0].arn
  }

  tags = local.common_tags
}

# Regla para rutear /api/* al backend
resource "aws_lb_listener_rule" "api_backend" {
  count = local.use_eks ? 1 : 0

  listener_arn = aws_lb_listener.http[0].arn
  priority     = 1

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend[0].arn
  }

  condition {
    path_pattern {
      values = ["/api/*"]
    }
  }
}

# Data source para obtener VPC principal
data "aws_vpc" "main" {
  default = true
}

# Outputs
output "alb_dns_name" {
  description = "DNS del Application Load Balancer"
  value       = try(aws_lb.maia[0].dns_name, "")
}

output "alb_arn" {
  description = "ARN del Application Load Balancer"
  value       = try(aws_lb.maia[0].arn, "")
}

output "alb_url" {
  description = "URL del ALB para acceder a la aplicación"
  value       = try("http://${aws_lb.maia[0].dns_name}", "")
}

output "backend_target_group_arn" {
  description = "ARN del Target Group del backend"
  value       = try(aws_lb_target_group.backend[0].arn, "")
}

output "frontend_target_group_arn" {
  description = "ARN del Target Group del frontend"
  value       = try(aws_lb_target_group.frontend[0].arn, "")
}
