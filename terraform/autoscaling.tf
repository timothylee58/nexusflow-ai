/*
  ECS Application Auto Scaling — CPU-based target tracking.

  Two policies:
    scale-out  — adds tasks when average CPU ≥ autoscaling_cpu_target (default 60 %)
    scale-in   — removes tasks when CPU drops well below target (handled automatically
                 by target-tracking; separate step-scaling not needed)

  Cooldowns:
    scale-out  60 s   — react quickly to load spikes
    scale-in   300 s  — be conservative about removing capacity

  The ECS service resource in ecs_service.tf must exist before this applies.
  lifecycle { ignore_changes = [desired_count] } on the service is intentional —
  Auto Scaling manages the count at runtime; Terraform owns only the min/max bounds.
*/

# ── Scalable target ────────────────────────────────────────────────────────────

resource "aws_appautoscaling_target" "backend" {
  service_namespace  = "ecs"
  resource_id        = "service/${split("/", var.ecs_cluster_arn)[1]}/${aws_ecs_service.backend.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  min_capacity       = var.autoscaling_min_capacity
  max_capacity       = var.autoscaling_max_capacity
}

# ── CPU target-tracking policy ─────────────────────────────────────────────────

resource "aws_appautoscaling_policy" "cpu" {
  name               = "${var.app_name}-${var.environment}-cpu-tracking"
  service_namespace  = aws_appautoscaling_target.backend.service_namespace
  resource_id        = aws_appautoscaling_target.backend.resource_id
  scalable_dimension = aws_appautoscaling_target.backend.scalable_dimension
  policy_type        = "TargetTrackingScaling"

  target_tracking_scaling_policy_configuration {
    target_value       = var.autoscaling_cpu_target
    scale_in_cooldown  = 300
    scale_out_cooldown = 60

    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
  }
}

# ── ALB request-count target-tracking policy ──────────────────────────────────
# Scales on requests-per-target so throughput spikes trigger scale-out even
# when CPU hasn't caught up (e.g. network-bound or I/O-heavy requests).

resource "aws_appautoscaling_policy" "alb_requests" {
  name               = "${var.app_name}-${var.environment}-alb-req-tracking"
  service_namespace  = aws_appautoscaling_target.backend.service_namespace
  resource_id        = aws_appautoscaling_target.backend.resource_id
  scalable_dimension = aws_appautoscaling_target.backend.scalable_dimension
  policy_type        = "TargetTrackingScaling"

  target_tracking_scaling_policy_configuration {
    target_value       = var.autoscaling_requests_per_target
    scale_in_cooldown  = 300
    scale_out_cooldown = 60

    predefined_metric_specification {
      predefined_metric_type = "ALBRequestCountPerTarget"
      resource_label         = "${data.aws_lb.app.arn_suffix}/${var.target_group_arn_suffix}"
    }
  }
}

# ── Outputs ───────────────────────────────────────────────────────────────────

output "autoscaling_min_capacity" {
  description = "Minimum ECS task count managed by Auto Scaling"
  value       = aws_appautoscaling_target.backend.min_capacity
}

output "autoscaling_max_capacity" {
  description = "Maximum ECS task count managed by Auto Scaling"
  value       = aws_appautoscaling_target.backend.max_capacity
}
