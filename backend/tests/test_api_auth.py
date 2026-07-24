"""
Tests for API auth dependency, rate-limit middleware, and security headers.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


# ─── require_api_key dependency ───────────────────────────────────────────────

class TestRequireApiKey:
    @pytest.mark.asyncio
    async def test_no_key_configured_dev_passes(self):
        """Dev without API_KEY set should pass through."""
        from fastapi.security import HTTPAuthorizationCredentials
        from backend.src.api.deps import require_api_key

        with patch("backend.src.api.deps.settings") as ms:
            ms.api_key = None
            ms.environment = "development"
            # Should not raise
            await require_api_key(credentials=None)

    @pytest.mark.asyncio
    async def test_no_key_configured_production_raises_500(self):
        """Production without API_KEY set is a misconfiguration."""
        from fastapi import HTTPException
        from backend.src.api.deps import require_api_key

        with patch("backend.src.api.deps.settings") as ms:
            ms.api_key = None
            ms.environment = "production"
            with pytest.raises(HTTPException) as exc:
                await require_api_key(credentials=None)
        assert exc.value.status_code == 500

    @pytest.mark.asyncio
    async def test_valid_key_passes(self):
        """Correct Bearer token must pass."""
        from fastapi.security import HTTPAuthorizationCredentials
        from backend.src.api.deps import require_api_key

        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="secret-key-123")
        with patch("backend.src.api.deps.settings") as ms:
            ms.api_key = "secret-key-123"
            ms.environment = "production"
            await require_api_key(credentials=creds)  # no raise

    @pytest.mark.asyncio
    async def test_wrong_key_raises_401(self):
        """Wrong Bearer token must raise 401."""
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials
        from backend.src.api.deps import require_api_key

        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="wrong-key")
        with patch("backend.src.api.deps.settings") as ms:
            ms.api_key = "correct-key"
            ms.environment = "production"
            with pytest.raises(HTTPException) as exc:
                await require_api_key(credentials=creds)
        assert exc.value.status_code == 401
        assert "WWW-Authenticate" in exc.value.headers

    @pytest.mark.asyncio
    async def test_missing_credentials_raises_401(self):
        """No Authorization header must raise 401 when key is configured."""
        from fastapi import HTTPException
        from backend.src.api.deps import require_api_key

        with patch("backend.src.api.deps.settings") as ms:
            ms.api_key = "some-key"
            ms.environment = "production"
            with pytest.raises(HTTPException) as exc:
                await require_api_key(credentials=None)
        assert exc.value.status_code == 401


# ─── _RateLimitStore ──────────────────────────────────────────────────────────

class TestRateLimitStore:
    def test_allows_requests_within_limit(self):
        from backend.src.api.deps import _RateLimitStore
        store = _RateLimitStore()
        for _ in range(5):
            assert store.is_allowed("1.2.3.4", limit=5, period=60) is True

    def test_blocks_when_limit_reached(self):
        from backend.src.api.deps import _RateLimitStore
        store = _RateLimitStore()
        for _ in range(3):
            store.is_allowed("1.2.3.4", limit=3, period=60)
        assert store.is_allowed("1.2.3.4", limit=3, period=60) is False

    def test_different_ips_have_separate_counters(self):
        from backend.src.api.deps import _RateLimitStore
        store = _RateLimitStore()
        for _ in range(3):
            store.is_allowed("1.1.1.1", limit=3, period=60)
        # 1.1.1.1 is now blocked; 2.2.2.2 should still pass
        assert store.is_allowed("1.1.1.1", limit=3, period=60) is False
        assert store.is_allowed("2.2.2.2", limit=3, period=60) is True

    def test_window_expires(self):
        """After the period elapses, the counter resets."""
        import time
        from unittest.mock import patch
        from backend.src.api.deps import _RateLimitStore

        store = _RateLimitStore()
        # Simulate 3 requests at t=0
        fake_time = 0.0
        with patch("backend.src.api.deps.time") as mock_time:
            mock_time.monotonic.return_value = fake_time
            for _ in range(3):
                store.is_allowed("1.2.3.4", limit=3, period=60)
            # 4th request at t=0 is blocked
            assert store.is_allowed("1.2.3.4", limit=3, period=60) is False
            # Advance past the period
            mock_time.monotonic.return_value = 61.0
            assert store.is_allowed("1.2.3.4", limit=3, period=60) is True


# ─── Security headers middleware ──────────────────────────────────────────────

class TestSecurityHeadersMiddleware:
    @pytest.mark.asyncio
    async def test_security_headers_present(self):
        from unittest.mock import AsyncMock
        from starlette.requests import Request
        from starlette.responses import Response
        from starlette.testclient import TestClient
        from fastapi import FastAPI
        from backend.src.api.deps import SecurityHeadersMiddleware

        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test")
        def ping():
            return {"ok": True}

        client = TestClient(app)
        with patch("backend.src.api.deps.settings") as ms:
            ms.environment = "development"
            resp = client.get("/test")

        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert "Referrer-Policy" in resp.headers

    @pytest.mark.asyncio
    async def test_hsts_only_in_production(self):
        from starlette.testclient import TestClient
        from fastapi import FastAPI
        from backend.src.api.deps import SecurityHeadersMiddleware

        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test")
        def ping():
            return {"ok": True}

        client = TestClient(app)

        with patch("backend.src.api.deps.settings") as ms:
            ms.environment = "development"
            resp = client.get("/test")
        assert "Strict-Transport-Security" not in resp.headers

        with patch("backend.src.api.deps.settings") as ms:
            ms.environment = "production"
            resp = client.get("/test")
        assert "Strict-Transport-Security" in resp.headers
        assert "max-age=63072000" in resp.headers["Strict-Transport-Security"]


# ─── CORS origins from settings ───────────────────────────────────────────────

class TestCorsFromSettings:
    def test_allowed_origins_parsed_from_comma_string(self):
        """Settings.allowed_origins should split correctly."""
        from backend.src.config import Settings
        s = Settings(
            allowed_origins="https://app.nexusflow.ai,https://www.nexusflow.ai, https://staging.nexusflow.ai "
        )
        origins = [o.strip() for o in s.allowed_origins.split(",") if o.strip()]
        assert "https://app.nexusflow.ai" in origins
        assert "https://staging.nexusflow.ai" in origins
        assert len(origins) == 3

    def test_default_origins_are_localhost(self):
        from backend.src.config import Settings
        s = Settings()
        assert "http://localhost:3000" in s.allowed_origins
