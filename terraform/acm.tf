# ----------------------------------
# app Certificate
# ----------------------------------
resource "aws_acm_certificate" "app" {
  domain_name       = "${var.environment}.app.${var.domain}"
  validation_method = "DNS"

  tags = {
    Name    = "${var.project}-${var.environment}-app"
    Project = var.project
    Env     = var.environment
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "app_dns" {
  for_each = {
    for dvo in aws_acm_certificate.app.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      type   = dvo.resource_record_type
      record = dvo.resource_record_value
    }
  }

  allow_overwrite = true
  zone_id = var.host_zone
  name    = each.value.name
  type    = each.value.type
  ttl     = 600
  records = [each.value.record]
}

resource "aws_acm_certificate_validation" "app_valid" {
  certificate_arn         = aws_acm_certificate.app.arn
  validation_record_fqdns = [for record in aws_route53_record.app_dns : record.fqdn]
}

# ----------------------------------
# auth Certificate
# ----------------------------------
resource "aws_acm_certificate" "auth" {
  domain_name       = "${var.environment}.auth.${var.domain}"
  validation_method = "DNS"

  tags = {
    Name    = "${var.project}-${var.environment}-auth"
    Project = var.project
    Env     = var.environment
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "auth_dns" {
  for_each = {
    for dvo in aws_acm_certificate.auth.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      type   = dvo.resource_record_type
      record = dvo.resource_record_value
    }
  }

  allow_overwrite = true
  zone_id = var.host_zone
  name    = each.value.name
  type    = each.value.type
  ttl     = 600
  records = [each.value.record]
}

resource "aws_acm_certificate_validation" "auth_valid" {
  certificate_arn         = aws_acm_certificate.auth.arn
  validation_record_fqdns = [for record in aws_route53_record.auth_dns : record.fqdn]
}