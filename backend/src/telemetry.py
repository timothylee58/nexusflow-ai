"""OpenTelemetry setup for NexusFlow.

Tracing is fully optional.  When OTEL_EXPORTER_OTLP_ENDPOINT is not set,
setup_telemetry() is a no-op — spans are created but immediately discarded,
no connections are opened, and overhead is negligible.

In production on ECS, point OTEL_EXPORTER_OTLP_ENDPOINT at an ADOT sidecar
(http://localhost:4318/v1/traces) or directly at AWS X-Ray's OTLP endpoint.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def setup_telemetry(service_name: str, otlp_endpoint: str | None = None) -> None:
    """Initialise the global OTEL TracerProvider.

    Call once at application startup.  When otlp_endpoint is None the call
    returns immediately — no TracerProvider is installed and the default no-op
    provider remains in place.
    """
    if not otlp_endpoint:
        logger.debug("OTEL tracing disabled (OTEL_EXPORTER_OTLP_ENDPOINT not configured)")
        return

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
    )
    trace.set_tracer_provider(provider)
    logger.info("OTEL tracing active → %s  (service.name=%s)", otlp_endpoint, service_name)


def get_tracer(name: str):
    """Return an OTEL Tracer for the given instrumentation scope.

    Safe to call before setup_telemetry() — returns a no-op Tracer via the
    default ProxyTracerProvider.  Once setup_telemetry() installs a real
    provider, the ProxyTracer delegates to it automatically.
    """
    from opentelemetry import trace

    return trace.get_tracer(name)
