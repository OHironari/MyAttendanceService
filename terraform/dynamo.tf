resource "aws_dynamodb_table" "AttendanceTable" {
  name           = "${var.environment}AttendanceRecords"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "user_id"
  range_key      = "work_date"

  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "work_date"
    type = "S"
  }

  tags = {
    Name    = "${var.project}-${var.environment}-AttendanceTable"
    Project = var.project
    Env     = var.environment
  }
}