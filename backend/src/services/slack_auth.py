"""Slack user registry — permission checks and CRUD helpers."""
from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.models import SlackUser


def _bootstrap_admin_ids() -> set[str]:
    raw = settings.slack_admin_user_ids.strip()
    return {uid.strip() for uid in raw.split(",") if uid.strip()}


async def get_user(session: AsyncSession, slack_user_id: str) -> SlackUser | None:
    result = await session.execute(
        select(SlackUser).where(SlackUser.slack_user_id == slack_user_id)
    )
    return result.scalar_one_or_none()


async def check_permission(
    session: AsyncSession,
    slack_user_id: str,
    required_roles: Sequence[str],
) -> bool:
    """Return True if the user has one of the required roles (or is a bootstrap admin)."""
    if slack_user_id in _bootstrap_admin_ids():
        return True
    user = await get_user(session, slack_user_id)
    return user is not None and user.role in required_roles


async def register_user(
    session: AsyncSession,
    *,
    slack_user_id: str,
    slack_username: str | None,
    role: str,
    added_by: str,
) -> SlackUser:
    """Insert or update a Slack user record. Returns the saved record."""
    existing = await get_user(session, slack_user_id)
    if existing:
        existing.role = role
        existing.slack_username = slack_username
        await session.commit()
        await session.refresh(existing)
        return existing
    user = SlackUser(
        slack_user_id=slack_user_id,
        slack_username=slack_username,
        role=role,
        added_by=added_by,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def remove_user(session: AsyncSession, slack_user_id: str) -> bool:
    """Delete the user record. Returns False if the user was not found."""
    user = await get_user(session, slack_user_id)
    if not user:
        return False
    await session.delete(user)
    await session.commit()
    return True


async def list_users(session: AsyncSession) -> list[SlackUser]:
    result = await session.execute(select(SlackUser).order_by(SlackUser.created_at))
    return list(result.scalars().all())
