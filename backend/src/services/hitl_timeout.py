"""Background task that auto-rejects HITL decisions that exceed the timeout window."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AgentAction
from src.db.session import AsyncSessionLocal
from src.services.audit_service import write_audit_log
from src.services.redis_service import AGENT_LOG_CHANNEL, redis_service
from src.services.slack_service import post_timeout_notice, update_hitl_message

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 60  # seconds between sweeps


async def _expire_action(session: AsyncSession, action: AgentAction) -> None:
    """Mark a single action as timed-out, write audit log, update Slack."""
    target_action = "unknown"
    if action.decision:
        try:
            target_action = json.loads(action.decision).get("target_action", "unknown")
        except (json.JSONDecodeError, AttributeError):
            pass

    action.execution_status = "timeout"
    await session.commit()

    await write_audit_log(
        session,
        event_type="hitl_timeout",
        user_id="system",
        user_input=action.user_input,
        approval_choice="reject",
        notes=f"Auto-rejected after timeout — no decision received",
        payload={"action_id": action.id, "slack_message_ts": action.slack_message_ts},
    )

    await redis_service.publish(
        AGENT_LOG_CHANNEL,
        {
            "node": "hitl",
            "message": f"HITL timeout: action {action.id} auto-rejected",
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": "system",
        },
    )

    if action.slack_message_ts:
        await update_hitl_message(
            message_ts=action.slack_message_ts,
            choice="timeout",
            decided_by="system (timeout)",
            target_action=target_action,
        )
        await post_timeout_notice(
            message_ts=action.slack_message_ts,
            action_id=action.id,
            target_action=target_action,
        )

    logger.info("[HITL timeout] Action %s expired and auto-rejected", action.id)


async def _sweep() -> None:
    """Find and expire all HITL actions past their deadline."""
    now = datetime.utcnow()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AgentAction).where(
                AgentAction.execution_status == "escalated",
                AgentAction.hitl_expires_at.is_not(None),
                AgentAction.hitl_expires_at <= now,
            )
        )
        expired = result.scalars().all()

    for action in expired:
        try:
            async with AsyncSessionLocal() as session:
                # Re-fetch inside its own session to avoid stale state
                refreshed = await session.get(AgentAction, action.id)
                if refreshed and refreshed.execution_status == "escalated":
                    await _expire_action(session, refreshed)
        except Exception as exc:
            logger.error("[HITL timeout] Error expiring action %s: %s", action.id, exc)


async def run_hitl_timeout_loop() -> None:
    """Long-running background task; survives individual sweep errors."""
    logger.info("[HITL timeout] Sweep loop started (interval=%ds)", _POLL_INTERVAL)
    while True:
        try:
            await _sweep()
        except Exception as exc:
            logger.error("[HITL timeout] Sweep error: %s", exc)
        await asyncio.sleep(_POLL_INTERVAL)
