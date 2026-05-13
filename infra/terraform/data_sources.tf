# Default VPC
data "aws_vpc" "default" {
  default = true
}

# Default subnets
data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# LabRole existente
data "aws_iam_role" "lab_role" {
  name = "LabRole"
}

# Availability zones
data "aws_availability_zones" "available" {
  state = "available"
}
