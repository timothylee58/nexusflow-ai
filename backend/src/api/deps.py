"""Shared FastAPI dependencies — API key auth and rate limiting."""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Callable

from fastapi import Depends, HTTPException, Request, Response, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware

from src.config import settings

logger = logging.getLogger(__name__)

# ─── API key auth ─────────────────────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=False)


async def require_api_key(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> None:
    """Validate the Bearer API key.

    Skipped entirely when API_KEY is not configured and environment is not
    production, so local development works without credentials.
    """
    if not settings.api_key:
        if settings.environment == "production":
            raise HTTPException(
                status_code=500,
                detail="Server misconfiguration: API_KEY not set in production",
            )
        return  # dev / staging: pass through
    if credentials is None or credentials.credentials != settings.api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ─── In-process rate limiter ──────────────────────────────────────────────────
# Uses a sliding-window counter per client IP. Falls back to "0.0.0.0" when
# the client address is unavailable (e.g. behind a proxy without the header).
# For production at scale, replace with Redis INCR + EXPIRE.

class _RateLimitStore:
    """Thread-safe (asyncio-safe) sliding-window counter."""

    def __init__(self) -> None:
        # ip → list[timestamp]
        self._hits: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, ip: str, limit: int, period: int) -> bool:
        now = time.monotonic()
        window = self._hits[ip]
        # Evict stale entries
        self._hits[ip] = [t for t in window if now - t < period]
        if len(self._hits[ip]) >= limit:
            return False
        self._hits[ip].append(now)
        return True


_store = _RateLimitStore()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that applies per-IP rate limits to expensive endpoints."""

    # Paths → (calls, period_seconds)
    _LIMITS: dict[str, tuple[int, int]] = {
        "/agent/orchestrate": (settings.rate_limit_orchestrate_per_minute, 60),
    }
    _DEFAULT_LIMIT = (settings.rate_limit_per_minute, 60)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        # Determine applicable limit
        limit_cfg = self._LIMITS.get(path)
        if limit_cfg is None:
            # Apply default limit only to agent/* and audit/* routes
            if path.startswith(("/agent/", "/audit/")):
                limit_cfg = self._DEFAULT_LIMIT

        if limit_cfg is not None:
            calls, period = limit_cfg
            # Prefer the forwarded IP header (set by ALB) over socket address
            ip = (
                request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                or (request.client.host if request.client else "0.0.0.0")
            )
            if not _store.is_allowed(ip, calls, period):
                logger.warning("[RateLimit] %s exceeded limit for %s", ip, path)
                return Response(
                    content='{"detail":"Rate limit exceeded. Please slow down."}',
                    status_code=429,
                    media_type="application/json",
                    headers={"Retry-After": str(period)},
                )

        return await call_next(request)


# ─── Security response headers ────────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Append security headers to every response."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        if settings.environment == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )
        return response
