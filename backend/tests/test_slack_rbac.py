"""
Tests for Slack RBAC — permission checks, user CRUD, and API route enforcement.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─── slack_auth service ───────────────────────────────────────────────────────

class TestBootstrapAdmins:
    def test_bootstrap_ids_parsed_correctly(self):
        from backend.src.services.slack_auth import _bootstrap_admin_ids
        with patch("backend.src.services.slack_auth.settings") as ms:
            ms.slack_admin_user_ids = "U001,U002, U003 "
            ids = _bootstrap_admin_ids()
        assert ids == {"U001", "U002", "U003"}

    def test_empty_string_yields_empty_set(self):
        from backend.src.services.slack_auth import _bootstrap_admin_ids
        with patch("backend.src.services.slack_auth.settings") as ms:
            ms.slack_admin_user_ids = ""
            ids = _bootstrap_admin_ids()
        assert ids == set()


class TestCheckPermission:
    @pytest.mark.asyncio
    async def test_bootstrap_admin_always_passes(self):
        from backend.src.services.slack_auth import check_permission
        mock_session = AsyncMock()
        with patch("backend.src.services.slack_auth._bootstrap_admin_ids", return_value={"U_BOOT"}):
            result = await check_permission(mock_session, "U_BOOT", ["admin"])
        assert result is True
        # DB should not be queried for bootstrap users
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_registered_analyst_passes_analyst_check(self):
        from backend.src.services.slack_auth import check_permission
        mock_user = MagicMock()
        mock_user.role = "analyst"
        mock_session = AsyncMock()
        with (
            patch("backend.src.services.slack_auth._bootstrap_admin_ids", return_value=set()),
            patch("backend.src.services.slack_auth.get_user", return_value=mock_user),
        ):
            result = await check_permission(mock_session, "U_ANA", ["admin", "analyst"])
        assert result is True

    @pytest.mark.asyncio
    async def test_analyst_denied_admin_only(self):
        from backend.src.services.slack_auth import check_permission
        mock_user = MagicMock()
        mock_user.role = "analyst"
        mock_session = AsyncMock()
        with (
            patch("backend.src.services.slack_auth._bootstrap_admin_ids", return_value=set()),
            patch("backend.src.services.slack_auth.get_user", return_value=mock_user),
        ):
            result = await check_permission(mock_session, "U_ANA", ["admin"])
        assert result is False

    @pytest.mark.asyncio
    async def test_unknown_user_denied(self):
        from backend.src.services.slack_auth import check_permission
        mock_session = AsyncMock()
        with (
            patch("backend.src.services.slack_auth._bootstrap_admin_ids", return_value=set()),
            patch("backend.src.services.slack_auth.get_user", return_value=None),
        ):
            result = await check_permission(mock_session, "U_UNKNOWN", ["admin", "analyst"])
        assert result is False


class TestRegisterUser:
    @pytest.mark.asyncio
    async def test_new_user_is_added(self):
        from backend.src.services.slack_auth import register_user
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        with patch("backend.src.services.slack_auth.get_user", return_value=None):
            added_user = MagicMock()
            added_user.slack_user_id = "U_NEW"
            added_user.role = "analyst"

            def capture_add(obj):
                obj.slack_user_id = "U_NEW"
                obj.role = "analyst"

            mock_session.add.side_effect = capture_add

            async def fake_refresh(obj):
                obj.slack_user_id = "U_NEW"
                obj.role = "analyst"

            mock_session.refresh.side_effect = fake_refresh

            result = await register_user(
                mock_session,
                slack_user_id="U_NEW",
                slack_username="alice",
                role="analyst",
                added_by="U_ADMIN",
            )
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_existing_user_role_updated(self):
        from backend.src.services.slack_auth import register_user
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        existing = MagicMock()
        existing.role = "analyst"
        existing.slack_username = "alice"

        async def fake_refresh(obj):
            pass

        mock_session.refresh.side_effect = fake_refresh

        with patch("backend.src.services.slack_auth.get_user", return_value=existing):
            await register_user(
                mock_session,
                slack_user_id="U_EXIST",
                slack_username="alice-renamed",
                role="admin",
                added_by="U_ADMIN",
            )

        assert existing.role == "admin"
        assert existing.slack_username == "alice-renamed"
        mock_session.commit.assert_called_once()
        # add() must NOT be called for an update
        mock_session.add.assert_not_called()


class TestRemoveUser:
    @pytest.mark.asyncio
    async def test_remove_existing_user_returns_true(self):
        from backend.src.services.slack_auth import remove_user
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.delete = AsyncMock()

        with patch("backend.src.services.slack_auth.get_user", return_value=MagicMock()):
            result = await remove_user(mock_session, "U_DEL")

        assert result is True
        mock_session.delete.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_missing_user_returns_false(self):
        from backend.src.services.slack_auth import remove_user
        mock_session = AsyncMock()

        with patch("backend.src.services.slack_auth.get_user", return_value=None):
            result = await remove_user(mock_session, "U_GHOST")

        assert result is False
        mock_session.delete.assert_not_called()


# ─── /slack/users API routes ──────────────────────────────────────────────────

class TestSlackUsersCheckRoute:
    @pytest.mark.asyncio
    async def test_bootstrap_user_returns_admin_role(self):
        from backend.src.api.routes.slack_users import check_user_role
        with patch("backend.src.api.routes.slack_users._bootstrap_admin_ids", return_value={"U_BOOT"}):
            result = await check_user_role(slack_user_id="U_BOOT")
        assert result["role"] == "admin"
        assert result["source"] == "bootstrap"

    @pytest.mark.asyncio
    async def test_unknown_user_returns_null_role(self):
        from backend.src.api.routes.slack_users import check_user_role
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("backend.src.api.routes.slack_users._bootstrap_admin_ids", return_value=set()),
            patch("backend.src.api.routes.slack_users.AsyncSessionLocal", return_value=mock_session),
            patch("backend.src.api.routes.slack_users.get_user", return_value=None),
        ):
            result = await check_user_role(slack_user_id="U_NOBODY")
        assert result["role"] is None
        assert result["source"] is None


class TestSlackUsersListRoute:
    @pytest.mark.asyncio
    async def test_non_admin_gets_403(self):
        from fastapi import HTTPException
        from backend.src.api.routes.slack_users import get_users
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("backend.src.api.routes.slack_users.AsyncSessionLocal", return_value=mock_session),
            patch("backend.src.api.routes.slack_users.check_permission", return_value=False),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_users(caller_id="U_ANALYST", org_id="default")
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_gets_user_list(self):
        from backend.src.api.routes.slack_users import get_users
        from datetime import datetime
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        fake_user = MagicMock()
        fake_user.id = "row-1"
        fake_user.slack_user_id = "U_ANA"
        fake_user.slack_username = "alice"
        fake_user.role = "analyst"
        fake_user.added_by = "U_ADMIN"
        fake_user.org_id = "default"
        fake_user.created_at = datetime.utcnow()

        with (
            patch("backend.src.api.routes.slack_users.AsyncSessionLocal", return_value=mock_session),
            patch("backend.src.api.routes.slack_users.check_permission", return_value=True),
            patch("backend.src.api.routes.slack_users.list_users", return_value=[fake_user]),
        ):
            result = await get_users(caller_id="U_ADMIN", org_id="default")

        assert len(result) == 1
        assert result[0].slack_user_id == "U_ANA"
        assert result[0].role == "analyst"


class TestSlackUsersAddRoute:
    @pytest.mark.asyncio
    async def test_non_admin_gets_403(self):
        from fastapi import HTTPException
        from backend.src.api.routes.slack_users import add_user, RegisterRequest
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        body = RegisterRequest(
            slack_user_id="U_NEW",
            role="analyst",
            caller_id="U_ANALYST",
        )
        with (
            patch("backend.src.api.routes.slack_users.AsyncSessionLocal", return_value=mock_session),
            patch("backend.src.api.routes.slack_users.check_permission", return_value=False),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await add_user(body, org_id="default")
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_can_add_user(self):
        from backend.src.api.routes.slack_users import add_user, RegisterRequest
        from datetime import datetime
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        saved_user = MagicMock()
        saved_user.id = "new-row"
        saved_user.slack_user_id = "U_NEW"
        saved_user.slack_username = None
        saved_user.role = "analyst"
        saved_user.added_by = "U_ADMIN"
        saved_user.org_id = "default"
        saved_user.created_at = datetime.utcnow()

        body = RegisterRequest(
            slack_user_id="U_NEW",
            role="analyst",
            caller_id="U_ADMIN",
        )
        with (
            patch("backend.src.api.routes.slack_users.AsyncSessionLocal", return_value=mock_session),
            patch("backend.src.api.routes.slack_users.check_permission", return_value=True),
            patch("backend.src.api.routes.slack_users.register_user", return_value=saved_user),
        ):
            result = await add_user(body)

        assert result.slack_user_id == "U_NEW"
        assert result.role == "analyst"


class TestSlackUsersDeleteRoute:
    @pytest.mark.asyncio
    async def test_non_admin_gets_403(self):
        from fastapi import HTTPException
        from backend.src.api.routes.slack_users import delete_user, RemoveRequest
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        body = RemoveRequest(caller_id="U_ANALYST")
        with (
            patch("backend.src.api.routes.slack_users.AsyncSessionLocal", return_value=mock_session),
            patch("backend.src.api.routes.slack_users.check_permission", return_value=False),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await delete_user("U_TARGET", body)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_missing_user_gives_404(self):
        from fastapi import HTTPException
        from backend.src.api.routes.slack_users import delete_user, RemoveRequest
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        body = RemoveRequest(caller_id="U_ADMIN")
        with (
            patch("backend.src.api.routes.slack_users.AsyncSessionLocal", return_value=mock_session),
            patch("backend.src.api.routes.slack_users.check_permission", return_value=True),
            patch("backend.src.api.routes.slack_users.remove_user", return_value=False),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await delete_user("U_GHOST", body)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_admin_can_delete_existing_user(self):
        from backend.src.api.routes.slack_users import delete_user, RemoveRequest
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        body = RemoveRequest(caller_id="U_ADMIN")
        with (
            patch("backend.src.api.routes.slack_users.AsyncSessionLocal", return_value=mock_session),
            patch("backend.src.api.routes.slack_users.check_permission", return_value=True),
            patch("backend.src.api.routes.slack_users.remove_user", return_value=True),
        ):
            result = await delete_user("U_DEL", body)
        assert result == {"removed": "U_DEL"}
