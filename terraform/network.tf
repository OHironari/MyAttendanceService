# ----------------------------------
# VPC
# ----------------------------------

resource "aws_vpc" "vpc" {
  cidr_block                       = "10.0.0.0/20"
  instance_tenancy                 = "default"
  enable_dns_hostnames             = true
  enable_dns_support               = true
  assign_generated_ipv6_cidr_block = false

  tags = {
    Name    = "${var.project}-${var.environment}-vpc"
    Project = var.project
    Env     = var.environment
  }
}


# ----------------------------------
# subnet
# ----------------------------------

resource "aws_subnet" "public_subnet_a" {
  vpc_id                  = aws_vpc.vpc.id
  availability_zone       = var.az_no1a
  cidr_block              = "10.0.0.0/24"
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.project}-${var.environment}-${var.az_no1a}-public"
  }
}
resource "aws_subnet" "public_subnet_c" {
  vpc_id                  = aws_vpc.vpc.id
  availability_zone       = var.az_no1c
  cidr_block              = "10.0.1.0/24"
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.project}-${var.environment}-${var.az_no1c}-public"
  }
}
resource "aws_subnet" "private_subnet_a" {
  vpc_id                  = aws_vpc.vpc.id
  availability_zone       = var.az_no1a
  cidr_block              = "10.0.2.0/24"
  map_public_ip_on_launch = false

  tags = {
    Name = "${var.project}-${var.environment}-${var.az_no1a}-private"
  }
}

resource "aws_subnet" "private_subnet_c" {
  vpc_id                  = aws_vpc.vpc.id
  availability_zone       = var.az_no1c
  cidr_block              = "10.0.3.0/24"
  map_public_ip_on_launch = false

  tags = {
    Name = "${var.project}-${var.environment}-${var.az_no1c}-private"
  }
}


# ----------------------------------
# route table
# ----------------------------------

resource "aws_route_table" "public_rt" {
  vpc_id = aws_vpc.vpc.id

  tags = {
    Name    = "${var.project}-${var.environment}-public-rt"
    Project = var.project
    Env     = var.environment
    Type    = "Public"
  }
}

resource "aws_route_table" "private_rt" {
  vpc_id = aws_vpc.vpc.id

  tags = {
    Name    = "${var.project}-${var.environment}-private-rt"
    Project = var.project
    Env     = var.environment
    Type    = "Private"
  }
}

resource "aws_route_table_association" "public_rt_a" {
  route_table_id = aws_route_table.public_rt.id
  subnet_id      = aws_subnet.public_subnet_a.id
}

resource "aws_route_table_association" "public_rt_c" {
  route_table_id = aws_route_table.public_rt.id
  subnet_id      = aws_subnet.public_subnet_c.id
}
resource "aws_route_table_association" "private_rt_a" {
  route_table_id = aws_route_table.private_rt.id
  subnet_id      = aws_subnet.private_subnet_a.id
}

resource "aws_route_table_association" "private_rt_c" {
  route_table_id = aws_route_table.private_rt.id
  subnet_id      = aws_subnet.private_subnet_c.id
}

# ----------------------------------
# internet gateway
# ----------------------------------

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.vpc.id

  tags = {
    Name    = "${var.project}-${var.environment}-igw"
    Project = var.project
    Env     = var.environment
  }
}

resource "aws_route" "public_rt_igw_r" {
  route_table_id         = aws_route_table.public_rt.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.igw.id
}

# ----------------------------------
# API Security Group 
# ----------------------------------
#Security Group for Application LoadBalancer
resource "aws_security_group" "my-app-ms-lb-sg" {
  name        = "${var.project}-${var.environment}-lb-sg"
  description = "${var.project}-${var.environment}-lb-sg"
  vpc_id      = aws_vpc.vpc.id
  tags = {
    Name    = "${var.project}-${var.environment}-lb-sg"
    Project = var.project
    Env     = var.environment
  }
}

resource "aws_security_group_rule" "anywhere_in_80_lb" {
  security_group_id = aws_security_group.my-app-ms-lb-sg.id
  type              = "ingress"
  protocol          = "tcp"
  from_port         = 80
  to_port           = 80
  cidr_blocks       = ["0.0.0.0/0"]
}

resource "aws_security_group_rule" "anywhere_eg_lb" {
  security_group_id = aws_security_group.my-app-ms-lb-sg.id
  type              = "egress"
  protocol          = "-1"
  from_port         = 0
  to_port           = 0
  cidr_blocks       = ["0.0.0.0/0"]
}

#Security Group for VPC Endpoint
resource "aws_security_group" "my-app-ms-endpoint-sg" {
  name        = "${var.project}-${var.environment}-endpoint-sg"
  description = "${var.project}-${var.environment}-endpoint-sg"
  vpc_id      = aws_vpc.vpc.id
  tags = {
    Name    = "${var.project}-${var.environment}-endpoint-sg"
    Project = var.project
    Env     = var.environment
  }
}

resource "aws_security_group_rule" "anywhere_in_endpoint" {
  security_group_id = aws_security_group.my-app-ms-endpoint-sg.id
  description = "Allow https from my-vpc"
  type              = "ingress"
  protocol          = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_blocks       = [aws_vpc.vpc.cidr_block]
}

resource "aws_security_group_rule" "anywhere_eg_endpoint" {
  security_group_id = aws_security_group.my-app-ms-endpoint-sg.id
  type              = "egress"
  protocol          = "-1"
  from_port         = 0
  to_port           = 0
  cidr_blocks       = ["0.0.0.0/0"]
}


# ----------------------------------
# Application Load Balancer
# ----------------------------------
resource "aws_lb" "alb" {
  name               = "${var.project}-${var.environment}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups = [
    aws_security_group.my-app-ms-lb-sg.id,
  ]
  subnets = [
    aws_subnet.public_subnet_a.id,
    aws_subnet.public_subnet_c.id
  ]
  depends_on = [ aws_lb_target_group.alb_target_group_for_attendance]
}

resource "aws_lb_listener" "alb_listener" {
  load_balancer_arn = aws_lb.alb.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type="forward"
    forward{
      # target_group {
      #   arn=aws_lb_target_group.alb_target_group_for_order.arn
      #   weight = 50
      # }
      target_group {
        arn=aws_lb_target_group.alb_target_group_for_attendance.arn
        weight = 50
      }
    }
  }
  depends_on = [ aws_lb_target_group.alb_target_group_for_attendance ]
}

resource "aws_lb_listener_rule" "attendance_rule" {
  listener_arn = aws_lb_listener.alb_listener.arn
  priority     = 2

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.alb_target_group_for_attendance.arn
  }

  condition {
    path_pattern {
      values = ["/api/attendance/*"]
    }
  }
}


# ----------------------------------
# target group
# ----------------------------------

#target group for product
resource "aws_lb_target_group" "alb_target_group_for_attendance" {
  name     = "${var.project}-${environment}-attendance-tg"
  port     = 8080
  protocol = "HTTP"
  vpc_id   = aws_vpc.vpc.id
  target_type = "ip"

  health_check {
    protocol = "HTTP"
    path="/api/attendance/monitor/health"
  }

  tags = {
    Name    = "${var.project}-${var.environment}-app-attendance-tg"
    Project = var.project
    Env     = var.environment
  }
}

# ----------------------------------
# VPC Endpoint
# ----------------------------------

#VPC Endpoint for ECR
resource "aws_vpc_endpoint" "my-ms-ecr-api" {
  vpc_id       = aws_vpc.vpc.id
  service_name = "com.amazonaws.${var.region}.ecr.api"
  vpc_endpoint_type = "Interface"
  private_dns_enabled = true

  subnet_ids = [aws_subnet.private_subnet_a.id,aws_subnet.private_subnet_c.id]
  security_group_ids = [aws_security_group.my-app-ms-endpoint-sg.id,]
  depends_on = [  ]
}

resource "aws_vpc_endpoint" "my-ms-ecr-dkr" {
  vpc_id       = aws_vpc.vpc.id
  service_name = "com.amazonaws.${var.region}.ecr.dkr"
  vpc_endpoint_type = "Interface"
  private_dns_enabled = true

  subnet_ids = [aws_subnet.private_subnet_a.id,aws_subnet.private_subnet_c.id]
  security_group_ids = [aws_security_group.my-app-ms-endpoint-sg.id,]
}

#VPC Endpoint for S3
resource "aws_vpc_endpoint" "my-ms-s3" {
  vpc_id       = aws_vpc.vpc.id
  service_name = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"

  route_table_ids = [aws_route_table.private_rt.id,]
}

#VPC Endpoint for CloudWatch
resource "aws_vpc_endpoint" "my-ms-logs" {
  vpc_id       = aws_vpc.vpc.id
  service_name = "com.amazonaws.${var.region}.logs"
  vpc_endpoint_type = "Interface"
  private_dns_enabled = true

  subnet_ids = [aws_subnet.private_subnet_a.id,aws_subnet.private_subnet_.id]
  security_group_ids = [aws_security_group.my-app-ms-endpoint-sg.id,]
}


