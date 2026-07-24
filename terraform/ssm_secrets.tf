/*
  AWS SSM Parameter Store — secrets injected into ECS tasks at startup.

  All parameters use SecureString (encrypted with the account default KMS key).
  The ECS task role needs ssm:GetParameters on these ARNs.

  After `terraform apply`, update your ECS task definition to reference these
  parameters in the `secrets` array (see ecs_task_secrets output below).
*/

locals {
  ssm_prefix = "/${var.app_name}/${var.environment}"
}

# ── Secret parameters ──────────────────────────────────────────────────────────

resource "aws_ssm_parameter" "api_key" {
  name        = "${local.ssm_prefix}/api_key"
  description = "NexusFlow Bearer API key — gates /agent/* and /audit/* routes"
  type        = "SecureString"
  value       = var.api_key
  tags        = { Environment = var.environment }
}

resource "aws_ssm_parameter" "anthropic_api_key" {
  count       = var.anthropic_api_key != "" ? 1 : 0
  name        = "${local.ssm_prefix}/anthropic_api_key"
  description = "Anthropic API key"
  type        = "SecureString"
  value       = var.anthropic_api_key
  tags        = { Environment = var.environment }
}

resource "aws_ssm_parameter" "openai_api_key" {
  count       = var.openai_api_key != "" ? 1 : 0
  name        = "${local.ssm_prefix}/openai_api_key"
  description = "OpenAI API key"
  type        = "SecureString"
  value       = var.openai_api_key
  tags        = { Environment = var.environment }
}

resource "aws_ssm_parameter" "slack_bot_token" {
  count       = var.slack_bot_token != "" ? 1 : 0
  name        = "${local.ssm_prefix}/slack_bot_token"
  description = "Slack bot OAuth token"
  type        = "SecureString"
  value       = var.slack_bot_token
  tags        = { Environment = var.environment }
}

resource "aws_ssm_parameter" "slack_signing_secret" {
  count       = var.slack_signing_secret != "" ? 1 : 0
  name        = "${local.ssm_prefix}/slack_signing_secret"
  description = "Slack signing secret for HMAC verification"
  type        = "SecureString"
  value       = var.slack_signing_secret
  tags        = { Environment = var.environment }
}

resource "aws_ssm_parameter" "database_url" {
  count       = var.database_url != "" ? 1 : 0
  name        = "${local.ssm_prefix}/database_url"
  description = "PostgreSQL connection string (asyncpg)"
  type        = "SecureString"
  value       = var.database_url
  tags        = { Environment = var.environment }
}

resource "aws_ssm_parameter" "redis_url" {
  count       = var.redis_url != "" ? 1 : 0
  name        = "${local.ssm_prefix}/redis_url"
  description = "Redis connection URL"
  type        = "SecureString"
  value       = var.redis_url
  tags        = { Environment = var.environment }
}

# ── ECS task role policy ───────────────────────────────────────────────────────

data "aws_iam_policy_document" "ssm_read" {
  statement {
    sid    = "ReadNexusFlowSecrets"
    effect = "Allow"
    actions = [
      "ssm:GetParameter",
      "ssm:GetParameters",
      "ssm:GetParametersByPath",
    ]
    resources = ["arn:aws:ssm:${var.aws_region}:*:parameter${local.ssm_prefix}/*"]
  }
  statement {
    sid       = "DecryptWithDefaultKey"
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = ["arn:aws:kms:${var.aws_region}:*:alias/aws/ssm"]
  }
}

resource "aws_iam_policy" "ssm_read" {
  name        = "${var.app_name}-${var.environment}-ssm-read"
  description = "Allows ECS tasks to read NexusFlow SSM parameters"
  policy      = data.aws_iam_policy_document.ssm_read.json
}

# ── Helper output: paste this into the ECS task definition `secrets` block ────

output "ecs_task_secrets" {
  description = "Paste into the secrets[] array of your ECS task definition JSON"
  value = jsonencode([
    {
      name      = "API_KEY"
      valueFrom = aws_ssm_parameter.api_key.arn
    },
    {
      name      = "ANTHROPIC_API_KEY"
      valueFrom = try(aws_ssm_parameter.anthropic_api_key[0].arn, "")
    },
    {
      name      = "SLACK_BOT_TOKEN"
      valueFrom = try(aws_ssm_parameter.slack_bot_token[0].arn, "")
    },
    {
      name      = "SLACK_SIGNING_SECRET"
      valueFrom = try(aws_ssm_parameter.slack_signing_secret[0].arn, "")
    },
    {
      name      = "DATABASE_URL"
      valueFrom = try(aws_ssm_parameter.database_url[0].arn, "")
    },
    {
      name      = "REDIS_URL"
      valueFrom = try(aws_ssm_parameter.redis_url[0].arn, "")
    },
  ])
}
