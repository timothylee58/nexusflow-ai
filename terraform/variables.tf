variable "aws_region" {
  description = "AWS region — must match where the ALB lives"
  type        = string
  default     = "ap-southeast-1"
}

variable "app_name" {
  description = "Application name prefix used in resource names"
  type        = string
  default     = "nexusflow"
}

variable "environment" {
  description = "Deployment environment: production | staging"
  type        = string
  default     = "production"
}

variable "domain_name" {
  description = "Primary domain served by the ALB, e.g. app.nexusflow.ai"
  type        = string
}

variable "alb_arn" {
  description = "ARN of the existing Application Load Balancer"
  type        = string
  # nexuspay-alb-665535199 — get from AWS console or `aws elbv2 describe-load-balancers`
}

variable "target_group_arn" {
  description = "ARN of the existing ALB target group (HTTP:8000 → backend tasks)"
  type        = string
}

# ── Secrets (passed via terraform.tfvars or CI env vars, never committed) ──

variable "api_key" {
  description = "Bearer token that gates /agent/* and /audit/* endpoints"
  type        = string
  sensitive   = true
}

variable "anthropic_api_key" {
  description = "Anthropic API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "openai_api_key" {
  description = "OpenAI API key (optional)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "slack_bot_token" {
  description = "Slack bot OAuth token"
  type        = string
  sensitive   = true
  default     = ""
}

variable "slack_signing_secret" {
  description = "Slack signing secret for HMAC verification"
  type        = string
  sensitive   = true
  default     = ""
}

variable "database_url" {
  description = "PostgreSQL connection string (asyncpg dialect)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "redis_url" {
  description = "Redis connection URL"
  type        = string
  sensitive   = true
  default     = ""
}
