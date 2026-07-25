"""Microsoft Teams HITL notifications via Incoming Webhook.

Post Adaptive Card HITL alerts to a Teams channel when a human decision is
required.  All functions are no-ops when TEAMS_HITL_WEBHOOK_URL is not set,
so this service is safe to import in environments without Teams.

Teams Incoming Webhooks accept the Office 365 Connector "MessageCard" format
(maximum compatibility across tenant configurations) or the newer Adaptive
Cards format via Workflow webhooks.  We use MessageCard here as it works with
both classic connectors and Workflow webhooks.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

_SEVERITY_COLOR = {
    "critical": "FF0000",
    "high": "FF6600",
    "medium": "FFA500",
    "low": "00AA00",
}
_SEVERITY_EMOJI = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🟢",
}


def _build_message_card(
    *,
    action_id: str,
    user_input: str,
    severity: str,
    summary: str,
    target_action: str,
    estimated_impact: float,
    expires_at: datetime,
) -> dict:
    emoji = _SEVERITY_EMOJI.get(severity, "⚠️")
    color = _SEVERITY_COLOR.get(severity, "808080")
    expires_str = expires_at.strftime("%H:%M UTC")

    return {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": color,
        "summary": f"{emoji} NexusFlow HITL — {severity.upper()} approval required",
        "sections": [
            {
                "activityTitle": f"{emoji} NexusOps HITL — {severity.upper()} approval required",
                "activitySubtitle": f"Action ID: `{action_id}`",
                "facts": [
                    {"name": "Severity", "value": severity.upper()},
                    {"name": "Proposed Action", "value": target_action},
                    {"name": "Estimated Impact", "value": f"RM {estimated_impact:,.0f}"},
                    {"name": "Expires", "value": expires_str},
                ],
                "markdown": True,
            },
            {
                "title": "Context",
                "text": f"**Query:** {user_input}\n\n**Analysis:** {summary}",
                "markdown": True,
            },
        ],
        "potentialAction": [
            {
                "@type": "OpenUri",
                "name": "Open NexusFlow Dashboard",
                "targets": [{"os": "default", "uri": "https://nexusflow.ai/hitl"}],
            }
        ],
    }


async def post_hitl_alert(
    *,
    action_id: str,
    user_input: str,
    severity: str,
    summary: str,
    target_action: str,
    estimated_impact: float,
) -> None:
    """Post a HITL approval request card to Teams.

    No-op when TEAMS_HITL_WEBHOOK_URL is not configured.
    """
    webhook_url = settings.teams_hitl_webhook_url
    if not webhook_url:
        logger.debug("[Teams] TEAMS_HITL_WEBHOOK_URL not set — skipping Teams HITL notification")
        return

    expires_at = datetime.utcnow() + timedelta(minutes=settings.hitl_timeout_minutes)
    card = _build_message_card(
        action_id=action_id,
        user_input=user_input,
        severity=severity,
        summary=summary,
        target_action=target_action,
        estimated_impact=estimated_impact,
        expires_at=expires_at,
    )

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json=card)
            resp.raise_for_status()
        logger.info("[Teams] HITL alert posted for action %s", action_id)
    except Exception as exc:
        logger.error("[Teams] Failed to post HITL alert: %s", exc)
        raise
