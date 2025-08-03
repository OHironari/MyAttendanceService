# ----------------------------------
# ECS Cluster
# ----------------------------------
resource "aws_ecs_cluster" "attendance_cluster" {
    name = "${var.project}-${var.environment}-cluster"
    service_connect_defaults {
    namespace = aws_service_discovery_private_dns_namespace.cluster_dns.arn
    }
}

# ----------------------------------
# ECS Service
# ----------------------------------

#ECS Service for Attendance
resource "aws_ecs_service" "attendance_service" {
  name            = "${var.project}-${var.environment}-attendance-service"
  cluster         = aws_ecs_cluster.attendance_cluster.id
  task_definition = aws_ecs_task_definition.attendance.arn
  desired_count = 1
  launch_type     = "FARGATE"
  network_configuration {
    subnets=[aws_subnet.private_subnet_a.id,aws_subnet.private_subnet_c.id]
    security_groups = [aws_security_group.attendance-service-sg.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn=aws_lb_target_group.alb_target_group_for_attendance.arn
    container_name = "attendance"
    container_port = 80
  }

  service_connect_configuration {
    enabled = true
    namespace = aws_service_discovery_private_dns_namespace.cluster_dns.arn
    log_configuration {
      log_driver = "awslogs"
      options = {
          awslogs-group         = "/ecs/attendance-service"
          awslogs-region        = "ap-northeast-1"
          awslogs-stream-prefix = "ecs"
        }
    }
  }
  depends_on = [ aws_ecs_task_definition.attendance,aws_lb.alb,aws_lb_listener.alb_listener80,aws_lb_listener.alb_listener443]
}



# ----------------------------------
# ECS Task Definition
# ----------------------------------

# ECS Task Definition for attendance
resource "aws_ecs_task_definition" "attendance" {
  family = "attendance"
  requires_compatibilities = ["FARGATE"]
  network_mode = "awsvpc"
  #実行ロールは埋め込み
  execution_role_arn    = aws_iam_role.ecs_task_execution_role.arn
  cpu=512
  memory=1024
  container_definitions = jsonencode([
    {
      name       = "attendance"
      image      = "324037284373.dkr.ecr.ap-northeast-1.amazonaws.com/attendance-servicedevecr:latest"
      essential = true
      cpu=256
      memory=512
      #command=["java","-jar","product.jar","--inventory.client.url=http://inventory-8080-tcp.my-app-cluster-ononari:8080/api/inventories"]
      portMappings = [{
        name          = "attendance-80-tcp"
        containerPort = 80
        protocol      = "tcp"
        appProtocol   = "http"
      }]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = "/ecs/attendance-service"
          awslogs-region        = var.region
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])
}
