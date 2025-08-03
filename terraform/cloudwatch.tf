resource "aws_cloudwatch_log_group" "ecs_attendance" {
  name              = "/ecs/attendance-service"
  retention_in_days = 30
}