"""Tests for database URL normalization and session setup."""
from __future__ import annotations

import pytest


class TestNormalizeDatabaseUrl:
    def _normalize(self, url: str) -> str:
        from backend.src.db.session import normalize_database_url
        return normalize_database_url(url)

    def test_postgres_scheme_rewritten(self):
        result = self._normalize("postgres://user:pass@host:5432/db")
        assert result == "postgresql+asyncpg://user:pass@host:5432/db"

    def test_postgresql_scheme_rewritten(self):
        result = self._normalize("postgresql://user:pass@host/db")
        assert result == "postgresql+asyncpg://user:pass@host/db"

    def test_already_asyncpg_unchanged(self):
        url = "postgresql+asyncpg://user:pass@host/db"
        assert self._normalize(url) == url

    def test_neon_postgres_url_rewritten(self):
        url = "postgresql://neondb_owner:secret@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require"
        result = self._normalize(url)
        assert result.startswith("postgresql+asyncpg://")
        assert "neon.tech" in result

    def test_bare_sqlite_rewritten(self):
        result = self._normalize("sqlite:///./data/nexusflow.db")
        assert result == "sqlite+aiosqlite:///./data/nexusflow.db"

    def test_aiosqlite_unchanged(self):
        url = "sqlite+aiosqlite:///./data/nexusflow.db"
        assert self._normalize(url) == url

    def test_empty_string_unchanged(self):
        assert self._normalize("") == ""


class TestIsPostgresFlag:
    def test_sqlite_not_postgres(self):
        from unittest.mock import patch
        # Ensure the default build path produces non-postgres
        from backend.src.db.session import normalize_database_url
        url = normalize_database_url("sqlite:///./data/test.db")
        assert not url.startswith("postgresql")

    def test_postgres_url_is_postgres(self):
        from backend.src.db.session import normalize_database_url
        url = normalize_database_url("postgres://user:pass@host/db")
        assert url.startswith("postgresql")


class TestInitDbSkipsPostgres:
    @pytest.mark.asyncio
    async def test_init_db_noop_for_postgres(self):
        """init_db must not call create_all when _is_postgres is True."""
        from unittest.mock import AsyncMock, patch, MagicMock

        mock_conn = AsyncMock()
        mock_begin = MagicMock()
        mock_begin.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_begin.__aexit__ = AsyncMock(return_value=False)

        with patch("backend.src.db.session._is_postgres", True), \
             patch("backend.src.db.session.engine") as mock_engine:
            mock_engine.begin.return_value = mock_begin
            from backend.src.db.session import init_db
            await init_db()
            mock_engine.begin.assert_not_called()

    @pytest.mark.asyncio
    async def test_init_db_runs_create_all_for_sqlite(self):
        """init_db must call create_all when _is_postgres is False."""
        from unittest.mock import AsyncMock, patch, MagicMock, call

        mock_conn = AsyncMock()
        mock_begin = MagicMock()
        mock_begin.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_begin.__aexit__ = AsyncMock(return_value=False)

        with patch("backend.src.db.session._is_postgres", False), \
             patch("backend.src.db.session.engine") as mock_engine:
            mock_engine.begin.return_value = mock_begin
            from backend.src.db.session import init_db
            await init_db()
            mock_engine.begin.assert_called_once()
            mock_conn.run_sync.assert_called_once()
