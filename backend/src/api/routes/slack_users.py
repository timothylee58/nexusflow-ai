"""
Slack user registry REST API.

All write operations require the caller to hold admin role.
The GET /slack/users/check endpoint is open so the Slack bot can
gate commands without a separate credential.

Roles: admin | operator | analyst | viewer  (see slack_auth.py for hierarchy)
"""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from src.api.deps import get_org_id
from src.db.session import AsyncSessionLocal
from src.services.slack_auth import (
    ROLE_HIERARCHY,
    _bootstrap_admin_ids,
    check_permission,
    get_user,
    list_users,
    register_user,
    remove_user,
)

logger = logging.getLogger(__name__)

slack_users_router = APIRouter(prefix="/slack/users", tags=["slack-users"])

_ROLE_PATTERN = "^(" + "|".join(ROLE_HIERARCHY) + ")$"


class SlackUserOut(BaseModel):
    id: str
    slack_user_id: str
    slack_username: str | None
    role: str
    added_by: str | None
    org_id: str
    created_at: datetime


class RegisterRequest(BaseModel):
    slack_user_id: str = Field(..., min_length=1)
    slack_username: str | None = None
    role: str = Field(..., pattern=_ROLE_PATTERN)
    caller_id: str = Field(..., description="Slack user ID of the admin issuing the request")


class RemoveRequest(BaseModel):
    caller_id: str = Field(..., description="Slack user ID of the admin issuing the request")


@slack_users_router.get("/check")
async def check_user_role(slack_user_id: str = Query(...)):
    """Return role info for a given Slack user ID (used by the bot for auth gating)."""
    if slack_user_id in _bootstrap_admin_ids():
        return {"slack_user_id": slack_user_id, "role": "admin", "source": "bootstrap"}
    async with AsyncSessionLocal() as session:
        user = await get_user(session, slack_user_id)
    if not user:
        return {"slack_user_id": slack_user_id, "role": None, "source": None}
    return {
        "slack_user_id": user.slack_user_id,
        "slack_username": user.slack_username,
        "role": user.role,
        "org_id": user.org_id,
        "source": "db",
    }


@slack_users_router.get("", response_model=list[SlackUserOut])
async def get_users(
    caller_id: str = Query(...),
    org_id: str = Depends(get_org_id),
):
    """List all registered users in the org. Requires admin role."""
    async with AsyncSessionLocal() as session:
        if not await check_permission(session, caller_id, ["admin"]):
            raise HTTPException(status_code=403, detail="Admin access required")
        users = await list_users(session, org_id=org_id)
    return [
        SlackUserOut(
            id=u.id,
            slack_user_id=u.slack_user_id,
            slack_username=u.slack_username,
            role=u.role,
            added_by=u.added_by,
            org_id=u.org_id,
            created_at=u.created_at,
        )
        for u in users
    ]


@slack_users_router.post("", response_model=SlackUserOut, status_code=201)
async def add_user(
    body: RegisterRequest,
    org_id: str = Depends(get_org_id),
):
    """Register or update a Slack user in the org. Requires admin role."""
    async with AsyncSessionLocal() as session:
        if not await check_permission(session, body.caller_id, ["admin"]):
            raise HTTPException(status_code=403, detail="Admin access required")
        user = await register_user(
            session,
            slack_user_id=body.slack_user_id,
            slack_username=body.slack_username,
            role=body.role,
            added_by=body.caller_id,
            org_id=org_id,
        )
    return SlackUserOut(
        id=user.id,
        slack_user_id=user.slack_user_id,
        slack_username=user.slack_username,
        role=user.role,
        added_by=user.added_by,
        org_id=user.org_id,
        created_at=user.created_at,
    )


@slack_users_router.delete("/{slack_user_id}", status_code=200)
async def delete_user(slack_user_id: str, body: RemoveRequest):
    """Remove a registered user. Requires admin role."""
    async with AsyncSessionLocal() as session:
        if not await check_permission(session, body.caller_id, ["admin"]):
            raise HTTPException(status_code=403, detail="Admin access required")
        removed = await remove_user(session, slack_user_id)
    if not removed:
        raise HTTPException(status_code=404, detail="User not found")
    return {"removed": slack_user_id}
