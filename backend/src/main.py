from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.deps import RateLimitMiddleware, SecurityHeadersMiddleware
from src.api.routes.orchestration import agent_router, audit_router, sse_router
from src.api.routes.slack_interactions import slack_router
from src.api.routes.slack_users import slack_users_router
from src.config import settings
from src.db.session import init_db
from src.logging_config import setup_logging
from src.services.llm_provider import is_llm_enabled, resolve_llm_provider
from src.services.redis_service import redis_service
from src.telemetry import setup_telemetry

# Structured JSON logging for CloudWatch; human-readable text for dev
setup_logging(log_level=settings.log_level, log_format=settings.log_format)

# OTEL tracing — no-op when OTEL_EXPORTER_OTLP_ENDPOINT is not set
setup_telemetry(
    service_name=settings.otel_service_name,
    otlp_endpoint=settings.otel_exporter_otlp_endpoint,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    await redis_service.connect()

    # Start HITL expiry sweep in the background
    from src.services.hitl_timeout import run_hitl_timeout_loop
    timeout_task = asyncio.create_task(run_hitl_timeout_loop())

    yield

    timeout_task.cancel()
    try:
        await timeout_task
    except asyncio.CancelledError:
        pass
    await redis_service.close()


app = FastAPI(
    title="NexusFlow API",
    version="0.4.0",
    lifespan=lifespan,
)

# FastAPI OTEL auto-instrumentation (only when tracing is enabled)
if settings.otel_exporter_otlp_endpoint:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    FastAPIInstrumentor.instrument_app(app)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.allowed_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agent_router)
app.include_router(sse_router)
app.include_router(audit_router)
app.include_router(slack_router)
app.include_router(slack_users_router)


@app.get("/health")
async def health() -> dict:
    redis_ok = await redis_service.is_healthy()
    return {
        "status": "ok",
        "redis": "connected" if redis_ok else "unavailable",
    }


@app.get("/status")
def status() -> dict:
    return {
        "environment": settings.environment,
        "debug": settings.debug,
        "log_level": settings.log_level,
        "log_format": settings.log_format,
        "redis_configured": bool(settings.redis_url or settings.upstash_redis_rest_url),
        "otel_enabled": bool(settings.otel_exporter_otlp_endpoint),
        "llm_provider": resolve_llm_provider(),
        "llm_configured": is_llm_enabled(),
        "database_url": settings.database_url or "sqlite (local default)",
        "slack_configured": bool(settings.slack_bot_token and settings.slack_channel_id),
        "hitl_timeout_minutes": settings.hitl_timeout_minutes,
    }


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "nexusflow-backend"}
