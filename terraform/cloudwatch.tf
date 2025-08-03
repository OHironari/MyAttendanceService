resource "aws_cloudwatch_log_group" "ecs_attendance" {
  name              = "/ecs/web-service"
  retention_in_days = 30
}