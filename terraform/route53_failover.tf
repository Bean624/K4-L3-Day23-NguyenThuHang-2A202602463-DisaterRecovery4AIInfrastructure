# ==============================================================================
# Route53 Health-Check-Based Failover Routing Policy
# Ánh xạ từ edge/proxy.py đọc edge/active_region & dr/health_checker.py
# ==============================================================================

# 1. Health check kiem tra endpoint /readyz cua Region A
resource "aws_route53_health_check" "region_a_readyz" {
  fqdn              = "serving-a.${var.domain_name}"
  port              = 8000
  type              = "HTTP"
  resource_path     = "/readyz"
  failure_threshold = 3      # Ánh xạ threshold=3 chống flapping
  request_interval  = 10     # Chu kỳ kiểm tra định kỳ
  measure_latency   = true

  tags = {
    Name = "${var.project_name}-region-a-health-check"
  }
}

# 2. Hosted Zone
resource "aws_route53_zone" "primary" {
  name = var.domain_name
}

# 3. DNS Record voi Failover Routing Policy
# Primary Record (Region A)
resource "aws_route53_record" "primary" {
  zone_id = aws_route53_zone.primary.zone_id
  name    = "api.${var.domain_name}"
  type    = "A"
  ttl     = 5 # Ánh xạ EDGE_TTL_SECONDS = 5s

  failover_routing_policy {
    type = "PRIMARY"
  }

  set_identifier  = "primary-region-a"
  health_check_id = aws_route53_health_check.region_a_readyz.id
  records         = ["10.0.1.10"] # IP dai dien Region A
}

# Secondary Record (Region B - Failover Target)
resource "aws_route53_record" "secondary" {
  zone_id = aws_route53_zone.primary.zone_id
  name    = "api.${var.domain_name}"
  type    = "A"
  ttl     = 5

  failover_routing_policy {
    type = "SECONDARY"
  }

  set_identifier = "secondary-region-b"
  records        = ["10.0.2.10"] # IP dai dien Region B
}
