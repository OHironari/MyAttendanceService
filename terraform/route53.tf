# ===========
# Define Route53
# ===========

# dev.app.itononari.xyzとALBの紐付け
resource "aws_route53_record" "app" {
  zone_id = var.host_zone
  name    = "${var.environment}.app.${var.domain}"
  type    = "A"
  ttl     = 300
  # dummy
  records = ["192.9.212.200"]
}

# resource "aws_route53_record" "auth" {
#   zone_id = var.host_zone
#   name    = "${var.environment}.auth.${var.domain}"
#   type    = "A"
#   ttl     = 300
#   records = [aws_eip.lb.public_ip]
# }
