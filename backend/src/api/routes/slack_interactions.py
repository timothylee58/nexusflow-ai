"""
Slack interactive component handler.

Slack sends a POST to /slack/interactions with:
  Content-Type: application/x-www-form-urlencoded
  Body: payload=<url_encoded_json>

Security: requests are verified via HMAC-SHA256 of the signing secret.
Slack requires a 200 response within 3 s — heavy work is dispatched to
a background task.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
import urllib.parse
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.models import AgentAction
from src.db.session import AsyncSessionLocal
from src.services.audit_service import write_audit_log
from src.services.redis_service import AGENT_LOG_CHANNEL, redis_service

logger = logging.getLogger(__name__)

slack_router = APIRouter(prefix="/slack", tags=["slack"])

_MAX_TIMESTAMP_SKEW = 300  # seconds


# ─── Signature verification ───────────────────────────────────────────────────


def _verify_slack_signature(raw_body: bytes, timestamp: str, signature: str) -> bool:
    """Verify a Slack request signature per the official spec."""
    if not settings.slack_signing_secret:
        # No secret configured — allow in dev, reject in production
        if settings.environment == "production":
            return False
        logger.warning("[Slack] Signature verification skipped — no SLACK_SIGNING_SECRET configured")
        return True

    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        return False

    if abs(time.time() - ts) > _MAX_TIMESTAMP_SKEW:
        logger.warning("[Slack] Request timestamp too old: %s", timestamp)
        return False

    basestring = f"v0:{timestamp}:{raw_body.decode()}"
    expected = (
        "v0="
        + hmac.new(
            settings.slack_signing_secret.encode(),
            basestring.encode(),
            hashlib.sha256,
        ).hexdigest()
    )
    return hmac.compare_digest(expected, signature)


# ─── Action handler (runs in background) ─────────────────────────────────────


async def _handle_hitl_action(
    *,
    action_id: str,
    slack_action: str,
    user_id: str,
    user_name: str,
    response_url: str,
) -> None:
    """Resolve the HITL action, update DB, Slack message, and broadcast via SSE."""
    from src.services.slack_service import update_hitl_message

    choice = "approve" if slack_action == "hitl_approve" else "reject"

    async with AsyncSessionLocal() as session:
        # Look up by AgentAction.id (button value) or slack_message_ts (legacy)
        result = await session.execute(
            select(AgentAction).where(AgentAction.id == action_id)
        )
        action = result.scalar_one_or_none()

        if not action:
            # Fallback: look up by slack_message_ts for older records
            result = await session.execute(
                select(AgentAction).where(AgentAction.slack_message_ts == action_id)
            )
            action = result.scalar_one_or_none()

        if not action:
            logger.error("[Slack HITL] Action not found: %s", action_id)
            return

        if action.execution_status not in ("escalated", "pending"):
            logger.info("[Slack HITL] Action %s already resolved: %s", action_id, action.execution_status)
            return

        # Resolve the action
        if choice == "approve":
            action.execution_status = "executing"
            await asyncio.sleep(0.05)
            action.execution_status = "completed"
        else:
            action.execution_status = "rejected"

        await session.commit()

        await write_audit_log(
            session,
            event_type=f"hitl_{choice}",
            user_id=user_name,
            user_input=action.user_input,
            approval_choice=choice,
            notes=f"Approved via Slack by {user_name}",
            payload={
                "action_id": action.id,
                "slack_message_ts": action.slack_message_ts,
                "slack_user": user_id,
            },
        )

    # Determine target_action for the Slack message update
    target_action = "action"
    try:
        if action.decision:
            target_action = json.loads(action.decision).get("target_action", "action")
    except (json.JSONDecodeError, AttributeError):
        pass

    if action.slack_message_ts:
        await update_hitl_message(
            message_ts=action.slack_message_ts,
            choice=choice,
            decided_by=user_name,
            target_action=target_action,
        )

    await redis_service.publish(
        AGENT_LOG_CHANNEL,
        {
            "node": "hitl",
            "message": f"Slack HITL {choice}d by {user_name} — {target_action}",
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_name,
        },
    )

    logger.info("[Slack HITL] %s — action=%s by=%s", choice, action_id, user_name)


# ─── Route ────────────────────────────────────────────────────────────────────


@slack_router.post("/interactions")
async def slack_interactions(
    request: Request,
    background_tasks: BackgroundTasks,
) -> Response:
    """
    Slack sends interactive component payloads here.
    Must return 200 within ~3 seconds; real work runs in a background task.
    """
    raw_body = await request.body()

    # Signature verification
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    if not _verify_slack_signature(raw_body, timestamp, signature):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")

    # Parse payload (application/x-www-form-urlencoded → JSON)
    try:
        form_data = urllib.parse.parse_qs(raw_body.decode())
        payload_raw = form_data.get("payload", [""])[0]
        payload = json.loads(payload_raw)
    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        raise HTTPException(status_code=400, detail=f"Malformed payload: {exc}") from exc

    payload_type = payload.get("type")

    # Handle Block Kit button actions
    if payload_type == "block_actions":
        actions: list[dict] = payload.get("actions", [])
        user = payload.get("user", {})
        user_id = user.get("id", "unknown")
        user_name = user.get("username") or user.get("name") or user_id
        response_url = payload.get("response_url", "")

        for action in actions:
            action_id_val = action.get("action_id", "")
            if action_id_val in ("hitl_approve", "hitl_reject"):
                button_value = action.get("value", "")
                background_tasks.add_task(
                    _handle_hitl_action,
                    action_id=button_value,
                    slack_action=action_id_val,
                    user_id=user_id,
                    user_name=user_name,
                    response_url=response_url,
                )
                # Immediate acknowledgement to Slack
                return Response(
                    content=json.dumps({"response_action": "clear"}),
                    media_type="application/json",
                    status_code=200,
                )

    # Acknowledge unhandled payloads
    return Response(status_code=200)
