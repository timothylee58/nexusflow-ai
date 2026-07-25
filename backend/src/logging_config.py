"""Structured logging for NexusFlow.

In production set LOG_FORMAT=json — logs emit as JSON to stdout and the ECS
awslogs driver ships them to CloudWatch Logs, where they are queryable with
CloudWatch Logs Insights.  In development LOG_FORMAT=text (the default) uses
the standard human-readable format.

When an OpenTelemetry span is active, trace_id and span_id are injected into
every JSON log record so logs and traces can be correlated in Grafana / X-Ray.
"""
from __future__ import annotations

import logging
import sys


class _OtelTraceFilter(logging.Filter):
    """Injects trace_id/span_id from the active OTEL span, if any."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            from opentelemetry import trace

            ctx = trace.get_current_span().get_span_context()
            record.trace_id = format(ctx.trace_id, "032x") if ctx.is_valid else ""
            record.span_id = format(ctx.span_id, "016x") if ctx.is_valid else ""
        except Exception:
            record.trace_id = ""
            record.span_id = ""
        return True


def setup_logging(log_level: str = "INFO", log_format: str = "text") -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)

    if log_format == "json":
        from pythonjsonlogger import jsonlogger

        handler = logging.StreamHandler(sys.stdout)
        formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s %(trace_id)s %(span_id)s",
            rename_fields={
                "asctime": "timestamp",
                "levelname": "level",
                "name": "logger",
            },
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        handler.setFormatter(formatter)
        handler.addFilter(_OtelTraceFilter())

        root = logging.root
        root.handlers.clear()
        root.addHandler(handler)
        root.setLevel(level)

        # Quiet noisy third-party loggers in production
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    else:
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            stream=sys.stdout,
        )
        logging.root.setLevel(level)
