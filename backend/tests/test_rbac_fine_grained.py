"""
Tests for fine-grained 4-role RBAC: admin | operator | analyst | viewer.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── ROLE_HIERARCHY constant ───────────────────────────────────────────────────

class TestRoleHierarchyConstant:
    def test_hierarchy_includes_all_four_roles(self):
        from backend.src.services.slack_auth import ROLE_HIERARCHY
        assert set(ROLE_HIERARCHY) == {"admin", "operator", "analyst", "viewer"}

    def test_admin_is_first_in_hierarchy(self):
        from backend.src.services.slack_auth import ROLE_HIERARCHY
        assert ROLE_HIERARCHY[0] == "admin"

    def test_viewer_is_last_in_hierarchy(self):
        from backend.src.services.slack_auth import ROLE_HIERARCHY
        assert ROLE_HIERARCHY[-1] == "viewer"

    def test_role_any_covers_all_roles(self):
        from backend.src.services.slack_auth import ROLE_ANY, ROLE_HIERARCHY
        assert set(ROLE_ANY) == set(ROLE_HIERARCHY)


# ── check_permission with 4 roles ─────────────────────────────────────────────

def _make_user(role: str):
    from backend.src.db.models import SlackUser
    return SlackUser(slack_user_id="U123", role=role, org_id="default")


class TestCheckPermissionFourRoles:
    @pytest.mark.asyncio
    async def test_admin_passes_admin_only(self):
        from backend.src.services.slack_auth import check_permission
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_scalar_result(_make_user("admin")))
        with patch("backend.src.services.slack_auth._bootstrap_admin_ids", return_value=set()):
            assert await check_permission(session, "U123", ["admin"]) is True

    @pytest.mark.asyncio
    async def test_operator_passes_admin_or_operator(self):
        from backend.src.services.slack_auth import check_permission
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_scalar_result(_make_user("operator")))
        with patch("backend.src.services.slack_auth._bootstrap_admin_ids", return_value=set()):
            assert await check_permission(session, "U123", ["admin", "operator"]) is True

    @pytest.mark.asyncio
    async def test_operator_denied_admin_only(self):
        from backend.src.services.slack_auth import check_permission
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_scalar_result(_make_user("operator")))
        with patch("backend.src.services.slack_auth._bootstrap_admin_ids", return_value=set()):
            assert await check_permission(session, "U123", ["admin"]) is False

    @pytest.mark.asyncio
    async def test_analyst_passes_analyst_and_above(self):
        from backend.src.services.slack_auth import check_permission
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_scalar_result(_make_user("analyst")))
        with patch("backend.src.services.slack_auth._bootstrap_admin_ids", return_value=set()):
            result = await check_permission(
                session, "U123", ["admin", "operator", "analyst"]
            )
        assert result is True

    @pytest.mark.asyncio
    async def test_analyst_denied_operator_and_above(self):
        from backend.src.services.slack_auth import check_permission
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_scalar_result(_make_user("analyst")))
        with patch("backend.src.services.slack_auth._bootstrap_admin_ids", return_value=set()):
            assert await check_permission(session, "U123", ["admin", "operator"]) is False

    @pytest.mark.asyncio
    async def test_viewer_passes_role_any(self):
        from backend.src.services.slack_auth import check_permission, ROLE_ANY
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_scalar_result(_make_user("viewer")))
        with patch("backend.src.services.slack_auth._bootstrap_admin_ids", return_value=set()):
            assert await check_permission(session, "U123", ROLE_ANY) is True

    @pytest.mark.asyncio
    async def test_viewer_denied_analyst_and_above(self):
        from backend.src.services.slack_auth import check_permission
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_scalar_result(_make_user("viewer")))
        with patch("backend.src.services.slack_auth._bootstrap_admin_ids", return_value=set()):
            result = await check_permission(
                session, "U123", ["admin", "operator", "analyst"]
            )
        assert result is False

    @pytest.mark.asyncio
    async def test_unknown_user_denied_any_role(self):
        from backend.src.services.slack_auth import check_permission, ROLE_ANY
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_scalar_result(None))
        with patch("backend.src.services.slack_auth._bootstrap_admin_ids", return_value=set()):
            assert await check_permission(session, "U999", ROLE_ANY) is False

    @pytest.mark.asyncio
    async def test_bootstrap_admin_always_passes(self):
        from backend.src.services.slack_auth import check_permission
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_scalar_result(None))
        with patch("backend.src.services.slack_auth._bootstrap_admin_ids", return_value={"U_BOOTSTRAP"}):
            assert await check_permission(session, "U_BOOTSTRAP", ["admin"]) is True


# ── register_user with org_id ─────────────────────────────────────────────────

class TestRegisterUserOrgId:
    @pytest.mark.asyncio
    async def test_register_sets_org_id(self):
        from backend.src.services.slack_auth import register_user

        session = AsyncMock()
        # No existing user
        session.execute = AsyncMock(return_value=_scalar_result(None))
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        captured = {}

        def capture_add(obj):
            captured["user"] = obj

        session.add.side_effect = capture_add

        await register_user(
            session,
            slack_user_id="U100",
            slack_username="alice",
            role="operator",
            added_by="U_ADMIN",
            org_id="tenant-x",
        )

        assert captured["user"].org_id == "tenant-x"
        assert captured["user"].role == "operator"

    @pytest.mark.asyncio
    async def test_register_updates_org_id_on_existing_user(self):
        from backend.src.services.slack_auth import register_user

        existing = _make_user("analyst")
        existing.org_id = "old-org"

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_scalar_result(existing))
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        result = await register_user(
            session,
            slack_user_id="U123",
            slack_username="bob",
            role="operator",
            added_by="U_ADMIN",
            org_id="new-org",
        )

        assert result.org_id == "new-org"
        assert result.role == "operator"


# ── Slack users route role pattern ────────────────────────────────────────────

class TestSlackUsersRolePattern:
    def test_operator_role_accepted(self):
        from backend.src.api.routes.slack_users import RegisterRequest
        req = RegisterRequest(
            slack_user_id="U1",
            role="operator",
            caller_id="U_ADMIN",
        )
        assert req.role == "operator"

    def test_viewer_role_accepted(self):
        from backend.src.api.routes.slack_users import RegisterRequest
        req = RegisterRequest(
            slack_user_id="U1",
            role="viewer",
            caller_id="U_ADMIN",
        )
        assert req.role == "viewer"

    def test_invalid_role_rejected(self):
        import pydantic
        from backend.src.api.routes.slack_users import RegisterRequest
        with pytest.raises(pydantic.ValidationError):
            RegisterRequest(
                slack_user_id="U1",
                role="superadmin",
                caller_id="U_ADMIN",
            )

    def test_all_four_roles_accepted(self):
        from backend.src.api.routes.slack_users import RegisterRequest
        for role in ("admin", "operator", "analyst", "viewer"):
            req = RegisterRequest(slack_user_id="U1", role=role, caller_id="U_ADMIN")
            assert req.role == role


# ── Helpers ───────────────────────────────────────────────────────────────────

def _scalar_result(obj):
    """Return a mock SQLAlchemy result that yields `obj` from scalar_one_or_none()."""
    mock = MagicMock()
    mock.scalar_one_or_none.return_value = obj
    return mock
