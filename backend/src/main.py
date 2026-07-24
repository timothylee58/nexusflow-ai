from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.deps import RateLimitMiddleware, SecurityHeadersMiddleware
from src.api.routes.orchestration import agent_router, audit_router, sse_router
from src.api.routes.slack_interactions import slack_router
from src.api.routes.slack_users import slack_users_router
from src.config import settings
from src.services.llm_provider import is_llm_enabled, resolve_llm_provider
from src.db.session import init_db
from src.services.redis_service import redis_service

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))


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
    version="0.3.0",
    lifespan=lifespan,
)

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
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/status")
def status() -> dict[str, str | bool | None]:
    return {
        "environment": settings.environment,
        "debug": settings.debug,
        "log_level": settings.log_level,
        "redis_configured": bool(settings.redis_url or settings.upstash_redis_rest_url),
        "llm_provider": resolve_llm_provider(),
        "llm_configured": is_llm_enabled(),
        "database_url": settings.database_url or "sqlite (local default)",
        "slack_configured": bool(settings.slack_bot_token and settings.slack_channel_id),
        "hitl_timeout_minutes": settings.hitl_timeout_minutes,
    }


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "nexusflow-backend"}
