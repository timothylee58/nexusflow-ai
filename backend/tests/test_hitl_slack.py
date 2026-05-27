"""
Tests for Slack HITL integration — signature verification, interaction handling,
audit logging, and timeout logic.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─── Slack signature verification ────────────────────────────────────────────

class TestSlackSignatureVerification:
    def _make_sig(self, body: str, ts: str, secret: str = "test-secret") -> str:
        base = f"v0:{ts}:{body}"
        return "v0=" + hmac.new(secret.encode(), base.encode(), hashlib.sha256).hexdigest()

    def _verify(self, body: bytes, ts: str, sig: str, secret: str | None = "test-secret", env: str = "development") -> bool:
        from backend.src.api.routes.slack_interactions import _verify_slack_signature
        with patch("backend.src.api.routes.slack_interactions.settings") as mock_settings:
            mock_settings.slack_signing_secret = secret
            mock_settings.environment = env
            return _verify_slack_signature(body, ts, sig)

    def test_valid_signature_passes(self):
        body = "payload=%7B%22type%22%3A%22block_actions%22%7D"
        ts = str(int(time.time()))
        sig = self._make_sig(body, ts)
        assert self._verify(body.encode(), ts, sig)

    def test_tampered_body_fails(self):
        body = "payload=original"
        ts = str(int(time.time()))
        sig = self._make_sig(body, ts)
        assert not self._verify(b"payload=tampered", ts, sig)

    def test_wrong_secret_fails(self):
        body = "payload=test"
        ts = str(int(time.time()))
        sig = self._make_sig(body, ts, secret="correct-secret")
        assert not self._verify(body.encode(), ts, sig, secret="wrong-secret")

    def test_stale_timestamp_fails(self):
        body = "payload=test"
        old_ts = str(int(time.time()) - 400)  # 400s ago > 300s tolerance
        sig = self._make_sig(body, old_ts)
        assert not self._verify(body.encode(), old_ts, sig)

    def test_no_secret_dev_allows(self):
        """Dev environment without a configured secret should pass through."""
        ts = str(int(time.time()))
        assert self._verify(b"payload=x", ts, "v0=anything", secret=None, env="development")

    def test_no_secret_production_blocks(self):
        """Production must always reject when signing secret is absent."""
        ts = str(int(time.time()))
        assert not self._verify(b"payload=x", ts, "v0=anything", secret=None, env="production")

    def test_invalid_timestamp_format_fails(self):
        assert not self._verify(b"payload=x", "not-a-number", "v0=sig")


# ─── Slack service Block Kit builders ────────────────────────────────────────

class TestSlackServiceBlocks:
    def test_hitl_blocks_contain_approve_and_reject(self):
        from datetime import datetime, timedelta
        from backend.src.services.slack_service import _hitl_blocks

        blocks = _hitl_blocks(
            action_id="action-uuid-123",
            user_input="Show KL bottlenecks",
            severity="critical",
            summary="Congestion at 92%",
            target_action="reroute",
            estimated_impact=1200.0,
            expires_at=datetime.utcnow() + timedelta(minutes=30),
        )

        action_block = next(b for b in blocks if b.get("type") == "actions")
        action_ids = [e["action_id"] for e in action_block["elements"]]
        assert "hitl_approve" in action_ids
        assert "hitl_reject" in action_ids

    def test_hitl_blocks_embed_action_id_in_button_value(self):
        from datetime import datetime, timedelta
        from backend.src.services.slack_service import _hitl_blocks

        action_id = "my-unique-action-id"
        blocks = _hitl_blocks(
            action_id=action_id,
            user_input="q",
            severity="high",
            summary="s",
            target_action="scale_resources",
            estimated_impact=600.0,
            expires_at=datetime.utcnow() + timedelta(minutes=30),
        )

        action_block = next(b for b in blocks if b.get("type") == "actions")
        values = [e["value"] for e in action_block["elements"]]
        assert action_id in values

    def test_resolved_blocks_approve_message(self):
        from backend.src.services.slack_service import _resolved_blocks

        blocks = _resolved_blocks(
            choice="approve",
            decided_by="alice",
            target_action="reroute",
        )
        text = blocks[0]["text"]["text"]
        assert "approved" in text.lower()
        assert "alice" in text

    def test_resolved_blocks_reject_message(self):
        from backend.src.services.slack_service import _resolved_blocks

        blocks = _resolved_blocks(
            choice="reject",
            decided_by="bob",
            target_action="reroute",
        )
        text = blocks[0]["text"]["text"]
        assert "rejected" in text.lower()

    def test_resolved_blocks_timeout_message(self):
        from backend.src.services.slack_service import _resolved_blocks

        blocks = _resolved_blocks(
            choice="timeout",
            decided_by="system (timeout)",
            target_action="reroute",
        )
        text = blocks[0]["text"]["text"]
        assert "expired" in text.lower() or "timed out" in text.lower()


# ─── post_hitl_alert stub (no Slack configured) ──────────────────────────────

class TestPostHitlAlertStub:
    @pytest.mark.asyncio
    async def test_stub_returns_ts_and_expiry_when_no_token(self):
        from backend.src.services.slack_service import post_hitl_alert

        with patch("backend.src.services.slack_service.settings") as ms:
            ms.slack_bot_token = None
            ms.slack_channel_id = None
            ms.hitl_timeout_minutes = 30

            ts, expires_at = await post_hitl_alert(
                action_id="test-id",
                user_input="test query",
                severity="high",
                summary="summary",
                target_action="scale_resources",
                estimated_impact=600.0,
            )

        assert ts.startswith("msg_")
        from datetime import datetime, timedelta
        assert expires_at > datetime.utcnow()
        assert expires_at < datetime.utcnow() + timedelta(minutes=31)

    @pytest.mark.asyncio
    async def test_update_hitl_message_stub_noop(self):
        """update_hitl_message should silently no-op when Slack is not configured."""
        from backend.src.services.slack_service import update_hitl_message

        with patch("backend.src.services.slack_service.settings") as ms:
            ms.slack_bot_token = None
            ms.slack_channel_id = None
            # Should not raise
            await update_hitl_message(
                message_ts="msg_123",
                choice="approve",
                decided_by="alice",
                target_action="reroute",
            )


# ─── HITL audit logging ───────────────────────────────────────────────────────

class TestHitlAuditLogging:
    @pytest.mark.asyncio
    async def test_audit_log_written_on_slack_action(self):
        """_handle_hitl_action writes an audit entry with correct approval_choice."""
        from datetime import datetime
        from backend.src.api.routes.slack_interactions import _handle_hitl_action

        mock_action = MagicMock()
        mock_action.id = "action-123"
        mock_action.user_input = "test query"
        mock_action.execution_status = "escalated"
        mock_action.decision = json.dumps({"target_action": "reroute"})
        mock_action.slack_message_ts = "msg_ts_123"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_action
        mock_session.execute.return_value = mock_result
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        audit_calls: list[dict] = []

        async def mock_write_audit(session, **kwargs):
            audit_calls.append(kwargs)
            return MagicMock(id="audit-1")

        with (
            patch("backend.src.api.routes.slack_interactions.AsyncSessionLocal", return_value=mock_session),
            patch("backend.src.api.routes.slack_interactions.write_audit_log", side_effect=mock_write_audit),
            patch("backend.src.api.routes.slack_interactions.update_hitl_message", new_callable=AsyncMock),
            patch("backend.src.api.routes.slack_interactions.redis_service") as mock_redis,
        ):
            mock_redis.publish = AsyncMock()
            await _handle_hitl_action(
                action_id="action-123",
                slack_action="hitl_approve",
                user_id="U123",
                user_name="alice",
                response_url="",
            )

        assert len(audit_calls) == 1
        assert audit_calls[0]["event_type"] == "hitl_approve"
        assert audit_calls[0]["approval_choice"] == "approve"
        assert "alice" in audit_calls[0]["notes"]

    @pytest.mark.asyncio
    async def test_audit_note_says_rejected_for_reject(self):
        """Audit note for rejection must say 'rejected', not 'approved'."""
        from backend.src.api.routes.slack_interactions import _handle_hitl_action

        mock_action = MagicMock()
        mock_action.id = "action-456"
        mock_action.user_input = "q"
        mock_action.execution_status = "escalated"
        mock_action.decision = json.dumps({"target_action": "scale_resources"})
        mock_action.slack_message_ts = "msg_ts_456"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_action
        mock_session.execute.return_value = mock_result
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        audit_calls: list[dict] = []

        async def mock_write_audit(session, **kwargs):
            audit_calls.append(kwargs)
            return MagicMock(id="audit-2")

        with (
            patch("backend.src.api.routes.slack_interactions.AsyncSessionLocal", return_value=mock_session),
            patch("backend.src.api.routes.slack_interactions.write_audit_log", side_effect=mock_write_audit),
            patch("backend.src.api.routes.slack_interactions.update_hitl_message", new_callable=AsyncMock),
            patch("backend.src.api.routes.slack_interactions.redis_service") as mock_redis,
        ):
            mock_redis.publish = AsyncMock()
            await _handle_hitl_action(
                action_id="action-456",
                slack_action="hitl_reject",
                user_id="U456",
                user_name="bob",
                response_url="",
            )

        assert audit_calls[0]["approval_choice"] == "reject"
        assert "rejected" in audit_calls[0]["notes"].lower()
        assert "approved" not in audit_calls[0]["notes"].lower()


# ─── HITL timeout sweep ───────────────────────────────────────────────────────

class TestHitlTimeout:
    @pytest.mark.asyncio
    async def test_expired_action_gets_auto_rejected(self):
        from datetime import datetime, timedelta
        from backend.src.services.hitl_timeout import _expire_action

        mock_action = MagicMock()
        mock_action.id = "expired-action-id"
        mock_action.user_input = "test query"
        mock_action.execution_status = "escalated"
        mock_action.slack_message_ts = "msg_ts_expired"
        mock_action.decision = json.dumps({"target_action": "reroute"})

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()

        audit_calls: list[dict] = []

        async def mock_write_audit(session, **kwargs):
            audit_calls.append(kwargs)
            return MagicMock(id="audit-timeout")

        with (
            patch("backend.src.services.hitl_timeout.write_audit_log", side_effect=mock_write_audit),
            patch("backend.src.services.hitl_timeout.redis_service") as mock_redis,
            patch("backend.src.services.hitl_timeout.update_hitl_message", new_callable=AsyncMock),
            patch("backend.src.services.hitl_timeout.post_timeout_notice", new_callable=AsyncMock),
        ):
            mock_redis.publish = AsyncMock()
            await _expire_action(mock_session, mock_action)

        assert mock_action.execution_status == "timeout"
        assert mock_session.commit.called
        assert len(audit_calls) == 1
        assert audit_calls[0]["event_type"] == "hitl_timeout"
        assert audit_calls[0]["approval_choice"] == "reject"
