/*
  ALB HTTPS listener + HTTP→HTTPS redirect

  Prerequisites:
  1. You own `var.domain_name` and can add a CNAME record to validate the ACM cert.
  2. The ALB (var.alb_arn) already exists — this file only adds listeners to it.
  3. Run:
       terraform init
       terraform plan -var="alb_arn=arn:aws:..." -var="target_group_arn=arn:aws:..." \
                      -var="domain_name=app.nexusflow.ai" -var="api_key=..."
       terraform apply
*/

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ── ACM certificate ────────────────────────────────────────────────────────────

resource "aws_acm_certificate" "app" {
  domain_name               = var.domain_name
  subject_alternative_names = ["*.${var.domain_name}"]
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name        = "${var.app_name}-${var.environment}"
    Environment = var.environment
  }
}

# Output the DNS validation records — add these to your registrar/Route 53
output "acm_validation_cname_records" {
  description = "Add these DNS CNAME records to validate the ACM certificate"
  value = {
    for dvo in aws_acm_certificate.app.domain_validation_options : dvo.domain_name => {
      name  = dvo.resource_record_name
      type  = dvo.resource_record_type
      value = dvo.resource_record_value
    }
  }
}

# ── HTTPS listener (443) ───────────────────────────────────────────────────────

resource "aws_lb_listener" "https" {
  load_balancer_arn = var.alb_arn
  port              = 443
  protocol          = "HTTPS"

  # TLS 1.2+ only — blocks TLS 1.0/1.1
  ssl_policy      = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn = aws_acm_certificate.app.arn

  default_action {
    type             = "forward"
    target_group_arn = var.target_group_arn
  }

  depends_on = [aws_acm_certificate.app]
}

# ── HTTP → HTTPS redirect (80) ─────────────────────────────────────────────────

resource "aws_lb_listener" "http_redirect" {
  load_balancer_arn = var.alb_arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      host        = "#{host}"
      path        = "/#{path}"
      query       = "#{query}"
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

# ── ALB security group: allow inbound 443, drop plain 80 after redirect ────────

data "aws_lb" "app" {
  arn = var.alb_arn
}

# NOTE: if you have an existing SG on the ALB, add these ingress rules to it
# rather than creating a new SG. Shown here for reference.
output "alb_dns_name" {
  description = "Point your domain CNAME at this ALB DNS name"
  value       = data.aws_lb.app.dns_name
}
