"""Slack service — Block Kit HITL alerts, message updates, and timeout notices."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from src.config import settings

logger = logging.getLogger(__name__)

# ─── Block Kit builders ───────────────────────────────────────────────────────

_SEVERITY_EMOJI = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}


def _hitl_blocks(
    *,
    action_id: str,
    user_input: str,
    severity: str,
    summary: str,
    target_action: str,
    estimated_impact: float,
    expires_at: datetime,
) -> list[dict]:
    emoji = _SEVERITY_EMOJI.get(severity, "⚪")
    expires_str = expires_at.strftime("%H:%M UTC")
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} NexusOps HITL — {severity.upper()} approval required",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Severity:*\n{severity.upper()}"},
                {"type": "mrkdwn", "text": f"*Proposed Action:*\n`{target_action}`"},
                {
                    "type": "mrkdwn",
                    "text": f"*Estimated Impact:*\nRM {estimated_impact:,.0f}",
                },
                {"type": "mrkdwn", "text": f"*Expires:*\n{expires_str}"},
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Query:*\n_{user_input}_\n\n*Analysis:*\n{summary}",
            },
        },
        {"type": "divider"},
        {
            "type": "actions",
            "block_id": "hitl_actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅  Approve"},
                    "style": "primary",
                    "action_id": "hitl_approve",
                    "value": action_id,
                    "confirm": {
                        "title": {"type": "plain_text", "text": "Confirm approval"},
                        "text": {
                            "type": "mrkdwn",
                            "text": f"Execute *{target_action}* (RM {estimated_impact:,.0f} impact)?",
                        },
                        "confirm": {"type": "plain_text", "text": "Approve"},
                        "deny": {"type": "plain_text", "text": "Cancel"},
                    },
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "❌  Reject"},
                    "style": "danger",
                    "action_id": "hitl_reject",
                    "value": action_id,
                },
            ],
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"⏱ Auto-expires at {expires_str} · Action ID: `{action_id}`",
                }
            ],
        },
    ]


def _resolved_blocks(
    *,
    choice: str,
    decided_by: str,
    target_action: str,
    notes: str = "",
) -> list[dict]:
    if choice == "approve":
        icon, label, color_word = "✅", "Approved", "approved"
    elif choice == "timeout":
        icon, label, color_word = "⏰", "Timed out — auto-rejected", "expired"
    else:
        icon, label, color_word = "❌", "Rejected", "rejected"

    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    blocks: list[dict] = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"{icon} *HITL decision {color_word}*\n"
                    f"Action *{target_action}* was *{label.lower()}* by *{decided_by}* at {ts}."
                ),
            },
        },
    ]
    if notes:
        blocks.append(
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"Notes: _{notes}_"}],
            }
        )
    return blocks


# ─── Public API ──────────────────────────────────────────────────────────────


def _make_client():
    from slack_sdk.web.async_client import AsyncWebClient

    return AsyncWebClient(token=settings.slack_bot_token)


async def post_hitl_alert(
    *,
    action_id: str,
    user_input: str,
    severity: str,
    summary: str,
    target_action: str,
    estimated_impact: float,
) -> tuple[str, datetime]:
    """
    Post a Block Kit HITL alert to Slack.

    Returns (slack_message_ts, hitl_expires_at).
    Falls back to a stub ts when Slack is not configured.
    """
    expires_at = datetime.utcnow() + timedelta(minutes=settings.hitl_timeout_minutes)
    stub_ts = f"msg_{datetime.utcnow().timestamp()}"

    if not settings.slack_bot_token or not settings.slack_channel_id:
        logger.info(
            "[Slack stub] HITL alert — severity=%s action=%s impact=%.0f",
            severity,
            target_action,
            estimated_impact,
        )
        return stub_ts, expires_at

    try:
        client = _make_client()
        blocks = _hitl_blocks(
            action_id=action_id,
            user_input=user_input,
            severity=severity,
            summary=summary,
            target_action=target_action,
            estimated_impact=estimated_impact,
            expires_at=expires_at,
        )
        resp = await client.chat_postMessage(
            channel=settings.slack_channel_id,
            text=f"HITL required — {severity.upper()} | {target_action} | RM {estimated_impact:,.0f}",
            blocks=blocks,
        )
        ts: str = resp["ts"]
        logger.info("[Slack] HITL message posted ts=%s", ts)
        return ts, expires_at
    except Exception as exc:
        logger.error("[Slack] post_hitl_alert failed: %s", exc)
        return stub_ts, expires_at


async def update_hitl_message(
    *,
    message_ts: str,
    choice: str,
    decided_by: str,
    target_action: str,
    notes: str = "",
) -> None:
    """Replace the HITL Block Kit message with the resolution state."""
    if not settings.slack_bot_token or not settings.slack_channel_id:
        logger.info("[Slack stub] HITL resolved: choice=%s by=%s", choice, decided_by)
        return

    try:
        client = _make_client()
        blocks = _resolved_blocks(
            choice=choice,
            decided_by=decided_by,
            target_action=target_action,
            notes=notes,
        )
        label_map = {"approve": "Approved", "reject": "Rejected", "timeout": "Timed out"}
        await client.chat_update(
            channel=settings.slack_channel_id,
            ts=message_ts,
            text=f"HITL {label_map.get(choice, choice)} — {target_action} | {decided_by}",
            blocks=blocks,
        )
        logger.info("[Slack] HITL message updated ts=%s choice=%s", message_ts, choice)
    except Exception as exc:
        logger.error("[Slack] update_hitl_message failed: %s", exc)


async def post_timeout_notice(*, message_ts: str, action_id: str, target_action: str) -> None:
    """Post a thread reply notifying that the HITL window expired."""
    if not settings.slack_bot_token or not settings.slack_channel_id:
        logger.info("[Slack stub] HITL timeout: action_id=%s", action_id)
        return

    try:
        client = _make_client()
        await client.chat_postMessage(
            channel=settings.slack_channel_id,
            thread_ts=message_ts,
            text=f"⏰ HITL window expired — `{target_action}` was auto-rejected after {settings.hitl_timeout_minutes} minutes.",
        )
    except Exception as exc:
        logger.error("[Slack] post_timeout_notice failed: %s", exc)
