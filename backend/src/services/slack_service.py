import logging
from datetime import datetime

from src.config import settings

logger = logging.getLogger(__name__)


async def post_hitl_alert(
    *,
    user_input: str,
    severity: str,
    summary: str,
    target_action: str,
    estimated_impact: float,
) -> str:
    """Post HITL alert to Slack or return a mock timestamp for local dev."""
    message_ts = f"msg_{datetime.utcnow().timestamp()}"

    if not settings.slack_bot_token or not settings.slack_channel_id:
        logger.info(
            "[Slack stub] HITL alert: severity=%s action=%s impact=%.0f",
            severity,
            target_action,
            estimated_impact,
        )
        return message_ts

    try:
        from slack_sdk.web.async_client import AsyncWebClient

        client = AsyncWebClient(token=settings.slack_bot_token)
        response = await client.chat_postMessage(
            channel=settings.slack_channel_id,
            text=(
                f"*HITL Required* — {severity.upper()}\n"
                f"Query: {user_input}\n"
                f"Summary: {summary}\n"
                f"Proposed action: {target_action}\n"
                f"Est. impact: RM{estimated_impact:,.0f}"
            ),
        )
        return response["ts"]
    except Exception as exc:
        logger.error("Slack post failed: %s", exc)
        return message_ts
