"""
Tests for multi-tenancy: org_id scoping across models, audit writes, and
the get_org_id dependency.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── Model org_id defaults ─────────────────────────────────────────────────────

class TestModelOrgIdDefaults:
    def test_agent_action_has_org_id_column(self):
        """org_id column exists on AgentAction with a server_default of 'default'."""
        from backend.src.db.models import AgentAction
        col = AgentAction.__table__.c["org_id"]
        assert col is not None
        assert str(col.server_default.arg) == "default"

    def test_audit_log_has_org_id_column(self):
        from backend.src.db.models import AuditLog
        col = AuditLog.__table__.c["org_id"]
        assert col is not None
        assert str(col.server_default.arg) == "default"

    def test_slack_user_has_org_id_column(self):
        from backend.src.db.models import SlackUser
        col = SlackUser.__table__.c["org_id"]
        assert col is not None
        assert str(col.server_default.arg) == "default"

    def test_agent_action_custom_org_id(self):
        from backend.src.db.models import AgentAction
        action = AgentAction(user_id="u1", user_input="test", org_id="acme")
        assert action.org_id == "acme"

    def test_audit_log_custom_org_id(self):
        from backend.src.db.models import AuditLog
        log = AuditLog(event_type="test_event", org_id="acme")
        assert log.org_id == "acme"


# ── get_org_id dependency ─────────────────────────────────────────────────────

class TestGetOrgId:
    def _make_request(self, headers: dict) -> MagicMock:
        req = MagicMock()
        req.headers = headers
        return req

    def test_returns_header_value(self):
        from backend.src.api.deps import get_org_id
        req = self._make_request({"X-Org-ID": "acme"})
        with patch("backend.src.api.deps.settings") as ms:
            ms.org_id_header = "X-Org-ID"
            ms.default_org_id = "default"
            assert get_org_id(req) == "acme"

    def test_returns_default_when_header_missing(self):
        from backend.src.api.deps import get_org_id
        req = self._make_request({})
        with patch("backend.src.api.deps.settings") as ms:
            ms.org_id_header = "X-Org-ID"
            ms.default_org_id = "default"
            assert get_org_id(req) == "default"

    def test_returns_default_for_empty_header(self):
        from backend.src.api.deps import get_org_id
        req = self._make_request({"X-Org-ID": "   "})
        with patch("backend.src.api.deps.settings") as ms:
            ms.org_id_header = "X-Org-ID"
            ms.default_org_id = "default"
            assert get_org_id(req) == "default"

    def test_strips_whitespace(self):
        from backend.src.api.deps import get_org_id
        req = self._make_request({"X-Org-ID": "  acme  "})
        with patch("backend.src.api.deps.settings") as ms:
            ms.org_id_header = "X-Org-ID"
            ms.default_org_id = "default"
            assert get_org_id(req) == "acme"


# ── audit_service org_id passthrough ─────────────────────────────────────────

class TestAuditServiceOrgId:
    @pytest.mark.asyncio
    async def test_write_audit_log_passes_org_id(self):
        from backend.src.services.audit_service import write_audit_log
        from backend.src.db.models import AuditLog

        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        captured = {}

        def capture_add(obj):
            captured["entry"] = obj

        session.add.side_effect = capture_add

        await write_audit_log(
            session,
            event_type="test",
            user_id="u1",
            org_id="tenant-a",
        )

        assert captured["entry"].org_id == "tenant-a"

    @pytest.mark.asyncio
    async def test_write_audit_log_defaults_org_id(self):
        from backend.src.services.audit_service import write_audit_log

        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        captured = {}

        def capture_add(obj):
            captured["entry"] = obj

        session.add.side_effect = capture_add

        await write_audit_log(session, event_type="test")

        assert captured["entry"].org_id == "default"


# ── list_users org_id scoping ─────────────────────────────────────────────────

class TestListUsersOrgScope:
    @pytest.mark.asyncio
    async def test_list_users_filters_by_org_id(self):
        """list_users() should only return users with matching org_id."""
        from backend.src.services.slack_auth import list_users
        from backend.src.db.models import SlackUser

        user_a = SlackUser(slack_user_id="U1", role="analyst", org_id="acme")
        user_b = SlackUser(slack_user_id="U2", role="viewer", org_id="other")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [user_a]

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        users = await list_users(session, org_id="acme")
        assert len(users) == 1
        assert users[0].org_id == "acme"

    @pytest.mark.asyncio
    async def test_list_users_default_org(self):
        from backend.src.services.slack_auth import list_users

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        users = await list_users(session)  # no org_id = "default"
        assert users == []


# ── Teams service no-op ───────────────────────────────────────────────────────

class TestTeamsServiceNoop:
    @pytest.mark.asyncio
    async def test_no_op_when_webhook_not_configured(self):
        """post_hitl_alert must not raise when webhook URL is missing."""
        from backend.src.services.teams_service import post_hitl_alert

        with patch("backend.src.services.teams_service.settings") as ms:
            ms.teams_hitl_webhook_url = None
            ms.hitl_timeout_minutes = 30
            # Should complete without error (no HTTP call)
            await post_hitl_alert(
                action_id="act-123",
                user_input="test query",
                severity="high",
                summary="High congestion",
                target_action="reroute",
                estimated_impact=50000.0,
            )

    @pytest.mark.asyncio
    async def test_posts_when_webhook_configured(self):
        from backend.src.services.teams_service import post_hitl_alert
        from unittest.mock import AsyncMock

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("backend.src.services.teams_service.settings") as ms, \
             patch("httpx.AsyncClient", return_value=mock_client):
            ms.teams_hitl_webhook_url = "https://teams.example.com/webhook"
            ms.hitl_timeout_minutes = 30
            await post_hitl_alert(
                action_id="act-456",
                user_input="delay in KL",
                severity="critical",
                summary="Critical delay",
                target_action="dispatch",
                estimated_impact=100000.0,
            )

        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        assert call_kwargs.args[0] == "https://teams.example.com/webhook"
