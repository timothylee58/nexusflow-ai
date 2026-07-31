"""
Tests for P5: SSE traffic channel wiring and VidStega audit receipt endpoints.
"""
from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── VidStega endpoints ────────────────────────────────────────────────────────

class TestVidStegaCreateEndpoint:
    @pytest.mark.asyncio
    async def test_create_returns_image_b64_and_signature(self):
        from backend.src.api.routes.orchestration import create_vidstega_receipt, VidStegaCreateRequest

        body = VidStegaCreateRequest(
            decision_id="DEC-001",
            ai_reasoning={"rule": "test", "confidence": 0.99},
            user_approval="admin@test.com",
            amount=5000.0,
        )
        with patch("backend.src.api.routes.orchestration.settings") as ms:
            ms.vidstega_signing_secret = "test-secret"
            result = await create_vidstega_receipt(body)

        assert "image_b64" in result
        assert "signature" in result
        assert result["decision_id"] == "DEC-001"
        # image_b64 must be valid base64
        decoded = base64.b64decode(result["image_b64"])
        assert decoded[:4] == b"\x89PNG"  # PNG magic bytes

    @pytest.mark.asyncio
    async def test_create_with_zero_amount(self):
        from backend.src.api.routes.orchestration import create_vidstega_receipt, VidStegaCreateRequest

        body = VidStegaCreateRequest(
            decision_id="DEC-002",
            ai_reasoning={},
            user_approval="pending",
            amount=0.0,
        )
        with patch("backend.src.api.routes.orchestration.settings") as ms:
            ms.vidstega_signing_secret = "test-secret"
            result = await create_vidstega_receipt(body)
        assert result["decision_id"] == "DEC-002"


class TestVidStegaVerifyEndpoint:
    @pytest.mark.asyncio
    async def test_verify_returns_valid_true_for_fresh_receipt(self):
        from backend.src.api.routes.orchestration import (
            create_vidstega_receipt,
            verify_vidstega_receipt,
            VidStegaCreateRequest,
            VidStegaVerifyRequest,
        )

        body = VidStegaCreateRequest(
            decision_id="DEC-VERIFY",
            ai_reasoning={"test": True},
            user_approval="approved",
            amount=100.0,
        )
        with patch("backend.src.api.routes.orchestration.settings") as ms:
            ms.vidstega_signing_secret = "shared-secret"
            created = await create_vidstega_receipt(body)

            verify_body = VidStegaVerifyRequest(
                image_b64=created["image_b64"],
                signature=created["signature"],
            )
            result = await verify_vidstega_receipt(verify_body)

        assert result["valid"] is True
        assert result["audit_data"]["decision_id"] == "DEC-VERIFY"

    @pytest.mark.asyncio
    async def test_verify_detects_tampered_signature(self):
        from backend.src.api.routes.orchestration import (
            create_vidstega_receipt,
            verify_vidstega_receipt,
            VidStegaCreateRequest,
            VidStegaVerifyRequest,
        )

        body = VidStegaCreateRequest(
            decision_id="DEC-TAMPER",
            ai_reasoning={"test": True},
            user_approval="approved",
            amount=0.0,
        )
        with patch("backend.src.api.routes.orchestration.settings") as ms:
            ms.vidstega_signing_secret = "real-secret"
            created = await create_vidstega_receipt(body)

        # Verify with a wrong secret — signature won't match
        with patch("backend.src.api.routes.orchestration.settings") as ms:
            ms.vidstega_signing_secret = "wrong-secret"
            verify_body = VidStegaVerifyRequest(
                image_b64=created["image_b64"],
                signature=created["signature"],
            )
            result = await verify_vidstega_receipt(verify_body)
        assert result["valid"] is False

    @pytest.mark.asyncio
    async def test_verify_rejects_invalid_base64(self):
        from fastapi import HTTPException
        from backend.src.api.routes.orchestration import verify_vidstega_receipt, VidStegaVerifyRequest

        body = VidStegaVerifyRequest(image_b64="!!!not-base64!!!", signature="abc")
        with patch("backend.src.api.routes.orchestration.settings") as ms:
            ms.vidstega_signing_secret = "secret"
            with pytest.raises(HTTPException) as exc:
                await verify_vidstega_receipt(body)
        assert exc.value.status_code == 400


class TestGetActionReceipt:
    @pytest.mark.asyncio
    async def test_returns_png_for_existing_action(self):
        from fastapi import HTTPException
        from backend.src.api.routes.orchestration import get_action_receipt

        mock_action = MagicMock()
        mock_action.user_input = "test query"
        mock_action.execution_path = json.dumps(["parse", "fetch", "analyze"])
        mock_action.analysis = json.dumps({"severity": "high", "summary": "Test summary"})
        mock_action.decision = json.dumps({"target_action": "reroute", "estimated_impact": 50000.0})
        mock_action.execution_status = "completed"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_action

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        with patch("backend.src.api.routes.orchestration.settings") as ms:
            ms.vidstega_signing_secret = "test-secret"
            response = await get_action_receipt("action-123", session=session, org_id="default")

        assert response.media_type == "image/png"
        assert response.body[:4] == b"\x89PNG"
        assert "X-VidStega-Signature" in response.headers

    @pytest.mark.asyncio
    async def test_returns_404_for_missing_action(self):
        from fastapi import HTTPException
        from backend.src.api.routes.orchestration import get_action_receipt

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        with patch("backend.src.api.routes.orchestration.settings") as ms:
            ms.vidstega_signing_secret = "test-secret"
            with pytest.raises(HTTPException) as exc:
                await get_action_receipt("nonexistent-id", session=session, org_id="default")
        assert exc.value.status_code == 404


# ── SSE metrics — traffic channel wiring ──────────────────────────────────────

class TestSseMetricsTrafficWiring:
    def test_mock_regional_metrics_has_required_fields(self):
        from backend.src.api.routes.orchestration import _mock_regional_metrics

        m = _mock_regional_metrics("MY")
        assert m["region"] == "MY"
        assert "congestion" in m
        assert "avg_delivery_time" in m
        assert "active_deliveries" in m
        assert "active_incidents" in m

    def test_traffic_channel_constant_is_defined(self):
        from backend.src.api.routes.orchestration import TRAFFIC_CHANNEL
        assert TRAFFIC_CHANNEL == "nexusflow:traffic"
