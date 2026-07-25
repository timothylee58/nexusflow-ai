from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings
from src.db.models import Base

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def normalize_database_url(url: str) -> str:
    """Rewrite URL schemes so SQLAlchemy uses the correct async driver.

    postgres:// and postgresql:// become postgresql+asyncpg://;
    bare sqlite:// becomes sqlite+aiosqlite://.
    Already-correct schemes pass through unchanged.
    """
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("sqlite:///") and "+aiosqlite" not in url:
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    return url


def _build_database_url() -> str:
    raw = (settings.database_url or settings.neon_database_url or "").strip()
    if raw:
        return normalize_database_url(raw)
    return f"sqlite+aiosqlite:///{DATA_DIR / 'nexusflow.db'}"


database_url = _build_database_url()
_is_postgres = database_url.startswith("postgresql")

_engine_kwargs: dict = {"echo": False}
if _is_postgres:
    _engine_kwargs.update({"pool_size": 5, "max_overflow": 10, "pool_pre_ping": True})

engine = create_async_engine(database_url, **_engine_kwargs)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
# Alias used by background tasks (e.g. HITL timeout sweeper) that need their own sessions
AsyncSessionLocal = SessionLocal


async def init_db() -> None:
    """Create tables for SQLite (dev convenience).

    For PostgreSQL, schema is managed by Alembic — run `alembic upgrade head`
    at container startup instead of calling this.
    """
    if not _is_postgres:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
