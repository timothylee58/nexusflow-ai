"""
Oddle Autonomous Dispatcher – Weeks 3-4
Detects traffic incidents, analyses impact, proposes reroutes, and posts
Slack-style Block Kit alerts for human-in-the-loop approval.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any

from anthropic import Anthropic

_INCIDENT_ANALYSIS_SYSTEM = """You are a logistics dispatch AI for Southeast Asia.
Given a traffic incident, return a JSON analysis. Return ONLY valid JSON.

Schema:
{
  "severity": "low|medium|high|critical",
  "delay_minutes": <int>,
  "affected_deliveries": <int>,
  "estimated_delay_cost_usd": <float>,
  "recommended_action": "monitor|reroute|escalate"
}"""

_ROUTE_ALTERNATIVES_SYSTEM = """You are a route planning AI for Southeast Asian logistics.
Suggest up to 3 alternative routes given an incident. Return ONLY valid JSON.

Schema:
{
  "alternatives": [
    {
      "route_name": "<name>",
      "capacity_pct": <int 0-100>,
      "extra_cost_usd": <float>,
      "estimated_saving_usd": <float>,
      "description": "<short description>"
    }
  ]
}"""

_DECISION_SYSTEM = """You are an autonomous dispatch decision engine.
Given severity, impact data, and alternatives, choose the best action. Return ONLY valid JSON.

Schema:
{
  "action": "REROUTE|MONITOR|ESCALATE",
  "chosen_route": "<route_name or null>",
  "reasoning": "<one sentence>",
  "net_saving_usd": <float>
}"""


@dataclass
class TrafficIncident:
    incident_id: str
    location: str
    region: str  # MY | SG | HK | TW
    description: str
    reported_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class DispatchResult:
    incident: TrafficIncident
    severity: dict[str, Any]
    impact: dict[str, Any]
    alternatives: dict[str, Any]
    decision: dict[str, Any]
    slack_payload: dict[str, Any]


class OddleAutonomousDispatcher:
    """Autonomous dispatcher that analyses incidents and prepares approval alerts."""

    def __init__(self) -> None:
        self._client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def detect_and_dispatch(self, incident: TrafficIncident) -> DispatchResult:
        severity = await self.analyse_incident_severity(incident)
        impact = await self.calculate_impact(incident, severity)
        alternatives = await self.find_route_alternatives(incident)
        decision = await self.make_dispatch_decision(severity, impact, alternatives)
        slack_payload = self._build_slack_payload(incident, decision, impact)

        return DispatchResult(
            incident=incident,
            severity=severity,
            impact=impact,
            alternatives=alternatives,
            decision=decision,
            slack_payload=slack_payload,
        )

    # ------------------------------------------------------------------
    # Internal steps
    # ------------------------------------------------------------------

    async def analyse_incident_severity(self, incident: TrafficIncident) -> dict[str, Any]:
        response = self._client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=256,
            system=_INCIDENT_ANALYSIS_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Incident at {incident.location} ({incident.region}): "
                        f"{incident.description}"
                    ),
                }
            ],
        )
        return json.loads(response.content[0].text.strip())

    async def calculate_impact(
        self, incident: TrafficIncident, severity: dict[str, Any]
    ) -> dict[str, Any]:
        affected = severity.get("affected_deliveries", 0)
        delay_cost = severity.get("estimated_delay_cost_usd", 0.0)
        return {
            "affected_deliveries": affected,
            "estimated_delay_cost_usd": delay_cost,
            "region": incident.region,
            "incident_id": incident.incident_id,
        }

    async def find_route_alternatives(self, incident: TrafficIncident) -> dict[str, Any]:
        response = self._client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=512,
            system=_ROUTE_ALTERNATIVES_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Find alternatives for incident at {incident.location} "
                        f"in {incident.region}. Description: {incident.description}"
                    ),
                }
            ],
        )
        return json.loads(response.content[0].text.strip())

    async def make_dispatch_decision(
        self,
        severity: dict[str, Any],
        impact: dict[str, Any],
        alternatives: dict[str, Any],
    ) -> dict[str, Any]:
        context = json.dumps(
            {"severity": severity, "impact": impact, "alternatives": alternatives}
        )
        response = self._client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=256,
            system=_DECISION_SYSTEM,
            messages=[{"role": "user", "content": context}],
        )
        return json.loads(response.content[0].text.strip())

    # ------------------------------------------------------------------
    # Slack Block Kit payload (human-in-the-loop approval)
    # ------------------------------------------------------------------

    def _build_slack_payload(
        self,
        incident: TrafficIncident,
        decision: dict[str, Any],
        impact: dict[str, Any],
    ) -> dict[str, Any]:
        action = decision.get("action", "MONITOR")
        reasoning = decision.get("reasoning", "")
        saving = decision.get("net_saving_usd", 0)
        affected = impact.get("affected_deliveries", 0)

        return {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🚨 Dispatch Alert – {incident.region} | {incident.incident_id}",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Location:*\n{incident.location}"},
                        {"type": "mrkdwn", "text": f"*Action:*\n{action}"},
                        {"type": "mrkdwn", "text": f"*Affected Deliveries:*\n{affected}"},
                        {"type": "mrkdwn", "text": f"*Est. Saving:*\n${saving:.2f}"},
                    ],
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*AI Reasoning:*\n{reasoning}"},
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "✅ APPROVE"},
                            "style": "primary",
                            "action_id": f"approve_{incident.incident_id}",
                            "value": json.dumps(
                                {
                                    "incident_id": incident.incident_id,
                                    "decision": decision,
                                }
                            ),
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "❌ REJECT"},
                            "style": "danger",
                            "action_id": f"reject_{incident.incident_id}",
                            "value": incident.incident_id,
                        },
                    ],
                },
            ]
        }
