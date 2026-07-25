/*
  ECS Fargate service — zero-downtime rolling deploys.

  Rolling-deploy settings:
    minimum_healthy_percent = 100  → never drop below full capacity
    maximum_percent         = 200  → spin up new tasks before stopping old ones
  Circuit breaker with auto-rollback ensures a bad deploy reverts automatically.

  Log driver:
    awslogs → CloudWatch Logs group /nexusflow/<environment>
    LOG_FORMAT=json  → structured JSON picked up by the app's setup_logging()
*/

# ── CloudWatch log group ───────────────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "backend" {
  name              = "/${var.app_name}/${var.environment}"
  retention_in_days = var.log_retention_days
  tags              = { Environment = var.environment }
}

# ── ECS task definition ────────────────────────────────────────────────────────

resource "aws_ecs_task_definition" "backend" {
  family                   = "${var.app_name}-${var.environment}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.container_cpu
  memory                   = var.container_memory
  execution_role_arn       = var.ecs_task_execution_role_arn
  task_role_arn            = var.ecs_task_role_arn

  container_definitions = jsonencode([
    {
      name      = "backend"
      image     = var.container_image
      essential = true

      portMappings = [
        { containerPort = 8000, protocol = "tcp" }
      ]

      environment = [
        { name = "ENVIRONMENT", value = var.environment },
        { name = "LOG_FORMAT",  value = "json" },
        { name = "LOG_LEVEL",   value = "INFO" },
        { name = "ALLOWED_ORIGINS", value = "https://${var.domain_name}" },
        { name = "OTEL_EXPORTER_OTLP_ENDPOINT", value = var.otel_exporter_otlp_endpoint },
      ]

      secrets = jsondecode(local.ecs_task_secrets)

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.backend.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "backend"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "curl -sf http://localhost:8000/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])

  tags = { Environment = var.environment }
}

# ── ECS service (rolling deploy, circuit breaker) ─────────────────────────────

resource "aws_ecs_service" "backend" {
  name            = "${var.app_name}-${var.environment}"
  cluster         = var.ecs_cluster_arn
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  # Zero-downtime rolling deploy
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.backend_security_group_id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = var.target_group_arn
    container_name   = "backend"
    container_port   = 8000
  }

  # Propagate tags to tasks for cost allocation
  propagate_tags = "TASK_DEFINITION"

  # Let Terraform replace the service when the task definition family changes
  lifecycle {
    ignore_changes = [task_definition]
  }

  tags = { Environment = var.environment }
}

# ── Attach SSM read policy to the task role ───────────────────────────────────

resource "aws_iam_role_policy_attachment" "task_ssm_read" {
  role       = split("/", var.ecs_task_role_arn)[1]
  policy_arn = aws_iam_policy.ssm_read.arn
}

# ── Outputs ───────────────────────────────────────────────────────────────────

output "ecs_service_name" {
  description = "Name of the ECS service (useful for `aws ecs describe-services`)"
  value       = aws_ecs_service.backend.name
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group that receives container stdout/stderr"
  value       = aws_cloudwatch_log_group.backend.name
}

output "task_definition_arn" {
  description = "Latest ECS task definition ARN"
  value       = aws_ecs_task_definition.backend.arn
}
