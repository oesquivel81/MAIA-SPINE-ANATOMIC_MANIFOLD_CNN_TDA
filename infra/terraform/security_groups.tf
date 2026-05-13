# Security Group for MAIA App
resource "aws_security_group" "maia_app" {
  name        = "${local.name_prefix}-app-sg"
  description = "Security group for MAIA backend app"
  vpc_id      = data.aws_vpc.default.id

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-app-sg"
    }
  )
}

# Ingress - HTTP
resource "aws_vpc_security_group_ingress_rule" "app_http" {
  security_group_id = aws_security_group.maia_app.id

  description = "Allow HTTP from anywhere"
  from_port   = 80
  to_port     = 80
  ip_protocol = "tcp"
  cidr_ipv4   = "0.0.0.0/0"

  tags = {
    Name = "${local.name_prefix}-http"
  }
}

# Ingress - HTTPS
resource "aws_vpc_security_group_ingress_rule" "app_https" {
  security_group_id = aws_security_group.maia_app.id

  description = "Allow HTTPS from anywhere"
  from_port   = 443
  to_port     = 443
  ip_protocol = "tcp"
  cidr_ipv4   = "0.0.0.0/0"

  tags = {
    Name = "${local.name_prefix}-https"
  }
}

# Ingress - App port (8000)
resource "aws_vpc_security_group_ingress_rule" "app_port" {
  security_group_id = aws_security_group.maia_app.id

  description = "Allow app port 8000"
  from_port   = 8000
  to_port     = 8000
  ip_protocol = "tcp"
  cidr_ipv4   = "0.0.0.0/0"

  tags = {
    Name = "${local.name_prefix}-app-port"
  }
}

# Egress - Allow all traffic
resource "aws_vpc_security_group_egress_rule" "app_all" {
  security_group_id = aws_security_group.maia_app.id

  description = "Allow all outbound traffic"
  ip_protocol = "-1"
  cidr_ipv4   = "0.0.0.0/0"

  tags = {
    Name = "${local.name_prefix}-egress-all"
  }
}
