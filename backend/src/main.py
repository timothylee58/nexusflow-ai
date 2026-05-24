from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.orchestration import agent_router, audit_router, sse_router
from src.config import settings
from src.services.llm_provider import is_llm_enabled, resolve_llm_provider
from src.db.session import init_db
from src.services.redis_service import redis_service

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    await redis_service.connect()
    yield
    await redis_service.close()


app = FastAPI(
    title="NexusFlow API",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agent_router)
app.include_router(sse_router)
app.include_router(audit_router)


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
    }


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "nexusflow-backend"}
