# ----------------------------------
# Secrets Manager Value Definition
# ----------------------------------

resource "aws_secretsmanager_secret" "dynamoaccess" {
  name = "dynamo_db_access_role_arn"
}

resource "aws_secretsmanager_secret_version" "dynamoaccess_version" {
  secret_id     = aws_secretsmanager_secret.dynamoaccess.id
  secret_string = jsonencode({
    dynamo_db_access_role_arn = aws_iam_role.Access_To_AttendanceRecode_Role.arn
  })
}
