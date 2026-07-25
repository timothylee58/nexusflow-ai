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

# ── ECS / compute ──────────────────────────────────────────────────────────────

variable "ecs_cluster_arn" {
  description = "ARN of the existing ECS cluster to deploy the service into"
  type        = string
}

variable "container_image" {
  description = "Docker image URI for the backend container (ECR or DockerHub)"
  type        = string
}

variable "ecs_task_execution_role_arn" {
  description = "ARN of the ECS task execution role (pulls image, writes logs)"
  type        = string
}

variable "ecs_task_role_arn" {
  description = "ARN of the ECS task role (app-level AWS calls: SSM, S3, …)"
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnet IDs the ECS tasks run in (typically 2-AZ)"
  type        = list(string)
}

variable "backend_security_group_id" {
  description = "Security group allowing ALB → ECS on port 8000"
  type        = string
}

variable "desired_count" {
  description = "Number of ECS task replicas to run"
  type        = number
  default     = 2
}

variable "container_cpu" {
  description = "CPU units per ECS task (1024 = 1 vCPU)"
  type        = number
  default     = 512
}

variable "container_memory" {
  description = "Memory (MiB) per ECS task"
  type        = number
  default     = 1024
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days (0 = never expire)"
  type        = number
  default     = 30
}

variable "otel_exporter_otlp_endpoint" {
  description = "OTLP HTTP endpoint for distributed tracing (ADOT / Grafana Tempo). Leave empty to disable."
  type        = string
  default     = ""
}

# ── Auto Scaling ──────────────────────────────────────────────────────────────

variable "autoscaling_min_capacity" {
  description = "Minimum number of ECS tasks; must be ≥ 1"
  type        = number
  default     = 1
}

variable "autoscaling_max_capacity" {
  description = "Maximum number of ECS tasks the auto-scaler may launch"
  type        = number
  default     = 10
}

variable "autoscaling_cpu_target" {
  description = "Target average CPU utilisation (%) that triggers scale-out"
  type        = number
  default     = 60
}

variable "autoscaling_requests_per_target" {
  description = "Target ALB requests-per-minute per ECS task; drives the second scaling policy"
  type        = number
  default     = 1000
}

variable "target_group_arn_suffix" {
  description = "ARN suffix of the ALB target group (the short form used in CloudWatch metrics, e.g. targetgroup/nexusflow-prod/abc123)"
  type        = string
}
