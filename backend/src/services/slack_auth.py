"""Slack user registry and fine-grained RBAC.

Role hierarchy (highest to lowest):
  admin    — full access: user management, orchestration, HITL, audit
  operator — orchestration + HITL approve/reject + audit read
  analyst  — orchestration trigger + audit read (cannot approve HITL)
  viewer   — read-only: audit logs and /status

Pass a list of roles that satisfy the requirement to check_permission():
  ["admin"]                         — admin only
  ["admin", "operator"]             — admin or operator
  ROLE_ANY                          — any registered user (including viewer)
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.models import SlackUser

# Ordered most-to-least privileged — useful for UI display / sorting.
ROLE_HIERARCHY: list[str] = ["admin", "operator", "analyst", "viewer"]

# Convenience constant: accepts any registered user.
ROLE_ANY: list[str] = ROLE_HIERARCHY


def _bootstrap_admin_ids() -> set[str]:
    raw = settings.slack_admin_user_ids or ""
    return {uid.strip() for uid in raw.split(",") if uid.strip()}


async def get_user(session: AsyncSession, slack_user_id: str) -> SlackUser | None:
    result = await session.execute(
        select(SlackUser).where(SlackUser.slack_user_id == slack_user_id)
    )
    return result.scalar_one_or_none()


async def check_permission(
    session: AsyncSession,
    slack_user_id: str,
    required_roles: list[str],
) -> bool:
    """Return True if the user holds one of the required roles.

    Bootstrap admins (env var SLACK_ADMIN_USER_IDS) always pass.
    """
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
    added_by: str | None,
    org_id: str = "default",
) -> SlackUser:
    """Upsert a Slack user record. Returns the saved record."""
    existing = await get_user(session, slack_user_id)
    if existing:
        existing.role = role
        existing.slack_username = slack_username
        existing.org_id = org_id
        await session.commit()
        await session.refresh(existing)
        return existing
    user = SlackUser(
        slack_user_id=slack_user_id,
        slack_username=slack_username,
        role=role,
        added_by=added_by,
        org_id=org_id,
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


async def list_users(
    session: AsyncSession, org_id: str = "default"
) -> list[SlackUser]:
    result = await session.execute(
        select(SlackUser)
        .where(SlackUser.org_id == org_id)
        .order_by(SlackUser.created_at)
    )
    return list(result.scalars().all())
