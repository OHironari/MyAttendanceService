
# ECS web用
resource "aws_cloudwatch_log_group" "ecs_web" {
  name              = "/ecs/web-service"
  retention_in_days = 30
}

# ECS attendance用
resource "aws_cloudwatch_log_group" "ecs_attendance" {
  name              = "/ecs/attendance-service"
  retention_in_days = 30
}

