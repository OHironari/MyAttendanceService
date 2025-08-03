# ----------------------------------
# IAM Role
# ----------------------------------

# ECS Task Execution Role
resource "aws_iam_role" "ecs_task_execution_role" {
  name = "ecsTaskExecutionRole"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      },
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_role_policy" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}


# Attendance Recordへのアクセス用ロール定義
resource "aws_iam_role" "Access_To_AttendanceRecode_Role" {
  name = "AccessToAttendanceTable"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      },
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "Access_To_AttendanceRecode_Role_Policy_Attatchment" {
  role       = aws_iam_role.Access_To_AttendanceRecode_Role.name
  policy_arn = aws_iam_policy.Access_To_AttendanceRecode_Role_Policy.arn
}

resource "aws_iam_policy" "Access_To_AttendanceRecode_Role_Policy" {
  name        = "Access_To_AttendanceRecode_Role_Policy"
  description = "AccessToAttendanceRecodeRolePolicy"
  policy      = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect: "Allow",
      Action: [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:Query"
      ],
      Resource: "${aws_dynamodb_table.AttendanceTable.arn}"
      }]
  })
}