"""
Unit tests for NexusFlow AI backend services.
These tests mock Anthropic API calls so they run without credentials.
"""
from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

# ---------------------------------------------------------------------------
# VidStega Audit Trail – no Anthropic dependency, fully testable offline
# ---------------------------------------------------------------------------

from backend.src.services.vidstega_audit import (
    VidStegaAuditTrail,
    embed_lsb,
    extract_lsb,
    sign_image,
    verify_signature,
)


class TestLSBSteganography:
    def test_roundtrip_short_payload(self):
        img = Image.new("RGB", (100, 100), color=(200, 200, 200))
        payload = "hello nexusflow"
        stamped = embed_lsb(img, payload)
        recovered = extract_lsb(stamped)
        assert recovered == payload

    def test_roundtrip_json_payload(self):
        img = Image.new("RGB", (200, 200), color=(128, 128, 128))
        data = json.dumps({"decision_id": "abc123", "amount_usd": 999.99})
        stamped = embed_lsb(img, data)
        recovered = extract_lsb(stamped)
        assert json.loads(recovered) == json.loads(data)

    def test_payload_too_large_raises(self):
        img = Image.new("RGB", (5, 5), color=(0, 0, 0))
        long_payload = "x" * 10_000
        with pytest.raises(ValueError, match="too large"):
            embed_lsb(img, long_payload)


class TestImageSigning:
    def test_valid_signature(self):
        data = b"some image bytes"
        sig = sign_image(data, "secret")
        assert verify_signature(data, sig, "secret")

    def test_tampered_data_fails(self):
        data = b"some image bytes"
        sig = sign_image(data, "secret")
        assert not verify_signature(b"tampered", sig, "secret")

    def test_wrong_secret_fails(self):
        data = b"some image bytes"
        sig = sign_image(data, "secret")
        assert not verify_signature(data, sig, "wrong-secret")


class TestVidStegaAuditTrail:
    def setup_method(self):
        self.trail = VidStegaAuditTrail(signing_secret="test-secret")

    def test_create_and_verify(self):
        image_bytes, sig = self.trail.create_audit_record(
            decision_id="decision-001",
            ai_reasoning={"rule": "amount > $10K", "confidence": 0.97},
            user_approval="manager@nexusflow.ai",
            amount=12_500.0,
        )
        result = self.trail.verify_audit_record(image_bytes, sig)
        assert result["valid"] is True
        assert result["audit_data"]["decision_id"] == "decision-001"
        assert result["audit_data"]["amount_usd"] == 12_500.0

    def test_verify_detects_tampered_image(self):
        image_bytes, sig = self.trail.create_audit_record(
            decision_id="d-002",
            ai_reasoning={},
            user_approval="admin",
            amount=100.0,
        )
        tampered = image_bytes[:-10] + b"\x00" * 10
        result = self.trail.verify_audit_record(tampered, sig)
        assert result["valid"] is False


# ---------------------------------------------------------------------------
# Model Router – mock Anthropic calls
# ---------------------------------------------------------------------------

from backend.src.services.model_router import IntelligentModelRouter, RouterStats


class TestIntelligentModelRouter:
    def _make_mock_response(self, text: str, tokens: int = 50) -> MagicMock:
        msg = MagicMock()
        msg.content = [MagicMock(text=text)]
        msg.usage = MagicMock(output_tokens=tokens)
        return msg

    @pytest.mark.asyncio
    async def test_simple_query_uses_haiku(self):
        router = IntelligentModelRouter()
        classify_resp = self._make_mock_response(
            json.dumps({"complexity": "simple", "reason": "basic status"}), tokens=10
        )
        exec_resp = self._make_mock_response("Your delivery is on time.", tokens=20)

        with patch.object(router._client.messages, "create", side_effect=[classify_resp, exec_resp]):
            result = await router.route_and_execute("What is my delivery status?")

        assert result.complexity == "simple"
        assert "haiku" in result.model_used

    @pytest.mark.asyncio
    async def test_complex_query_uses_sonnet(self):
        router = IntelligentModelRouter()
        classify_resp = self._make_mock_response(
            json.dumps({"complexity": "complex", "reason": "optimisation needed"}), tokens=10
        )
        exec_resp = self._make_mock_response("Here is the optimised route...", tokens=80)

        with patch.object(router._client.messages, "create", side_effect=[classify_resp, exec_resp]):
            result = await router.route_and_execute("Optimise delivery routes for KL tomorrow")

        assert result.complexity == "complex"
        assert "sonnet" in result.model_used

    @pytest.mark.asyncio
    async def test_high_value_overrides_to_sonnet(self):
        router = IntelligentModelRouter()
        classify_resp = self._make_mock_response(
            json.dumps({"complexity": "simple", "reason": "basic query"}), tokens=10
        )
        exec_resp = self._make_mock_response("Approved.", tokens=10)

        with patch.object(router._client.messages, "create", side_effect=[classify_resp, exec_resp]):
            result = await router.route_and_execute(
                "Approve refund", context={"amount": 15_000}
            )

        assert "sonnet" in result.model_used

    @pytest.mark.asyncio
    async def test_escalate_uses_opus(self):
        router = IntelligentModelRouter()
        classify_resp = self._make_mock_response(
            json.dumps({"complexity": "escalate", "reason": "fraud suspected"}), tokens=10
        )
        exec_resp = self._make_mock_response("Escalating to fraud team.", tokens=30)

        with patch.object(router._client.messages, "create", side_effect=[classify_resp, exec_resp]):
            result = await router.route_and_execute("This transaction looks fraudulent")

        assert result.complexity == "escalate"
        assert "opus" in result.model_used

    @pytest.mark.asyncio
    async def test_stats_accumulate(self):
        router = IntelligentModelRouter()
        classify_resp = self._make_mock_response(
            json.dumps({"complexity": "simple", "reason": "easy"}), tokens=5
        )
        exec_resp = self._make_mock_response("OK", tokens=5)

        with patch.object(router._client.messages, "create", side_effect=[classify_resp, exec_resp]):
            await router.route_and_execute("Test query")

        assert router.stats.total_queries == 1
        assert router.stats.haiku_count == 1


# ---------------------------------------------------------------------------
# NLP Router – mock Anthropic calls
# ---------------------------------------------------------------------------

from backend.src.agent.nlp_router import parse_nl_command


class TestNLPRouter:
    @pytest.mark.asyncio
    async def test_parses_bottleneck_query(self):
        expected = {
            "query_type": "bottleneck_analysis",
            "region": "MY",
            "metric": "delivery_time",
            "time_frame": "realtime",
            "filters": {},
        }
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(expected))]
        mock_client.messages.create.return_value = mock_response

        with patch("backend.src.agent.nlp_router.Anthropic", return_value=mock_client):
            result = await parse_nl_command("Show me delivery bottlenecks in KL right now")

        assert result["query_type"] == "bottleneck_analysis"
        assert result["region"] == "MY"

    @pytest.mark.asyncio
    async def test_returns_dict(self):
        expected = {
            "query_type": "cost_analysis",
            "region": "SG",
            "metric": "cost",
            "time_frame": "week",
            "filters": {},
        }
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(expected))]
        mock_client.messages.create.return_value = mock_response

        with patch("backend.src.agent.nlp_router.Anthropic", return_value=mock_client):
            result = await parse_nl_command("Cost analysis for Singapore this week")

        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Oddle Dispatcher – mock Anthropic calls
# ---------------------------------------------------------------------------

from backend.src.services.oddle_dispatcher import OddleAutonomousDispatcher, TrafficIncident


class TestOddleDispatcher:
    def _make_mock_response(self, data: dict) -> MagicMock:
        msg = MagicMock()
        msg.content = [MagicMock(text=json.dumps(data))]
        return msg

    @pytest.mark.asyncio
    async def test_detect_and_dispatch_returns_result(self):
        dispatcher = OddleAutonomousDispatcher()

        severity_data = {
            "severity": "high",
            "delay_minutes": 35,
            "affected_deliveries": 47,
            "estimated_delay_cost_usd": 1200.0,
            "recommended_action": "reroute",
        }
        alternatives_data = {
            "alternatives": [
                {
                    "route_name": "Merdeka Route",
                    "capacity_pct": 85,
                    "extra_cost_usd": 240.0,
                    "estimated_saving_usd": 960.0,
                    "description": "Via Jalan Merdeka",
                }
            ]
        }
        decision_data = {
            "action": "REROUTE",
            "chosen_route": "Merdeka Route",
            "reasoning": "REROUTE saves $960 vs $1,200 delay cost.",
            "net_saving_usd": 960.0,
        }

        side_effects = [
            self._make_mock_response(severity_data),
            self._make_mock_response(alternatives_data),
            self._make_mock_response(decision_data),
        ]

        with patch.object(dispatcher._client.messages, "create", side_effect=side_effects):
            incident = TrafficIncident(
                incident_id="INC-001",
                location="Federal Highway, KL",
                region="MY",
                description="Major jam, 40-minute delay",
            )
            result = await dispatcher.detect_and_dispatch(incident)

        assert result.decision["action"] == "REROUTE"
        assert result.decision["net_saving_usd"] == 960.0
        assert result.impact["affected_deliveries"] == 47
        # Slack payload should include approve/reject buttons
        block_types = [b["type"] for b in result.slack_payload["blocks"]]
        assert "actions" in block_types
