"""
NLP Router – Week 1-2 Control Tower
Converts natural language logistics queries into structured JSON.
"""
from __future__ import annotations

import json
import os
from typing import Any

from anthropic import Anthropic

_SYSTEM_PROMPT = """You are a logistics query parser for a Southeast-Asian delivery platform.
Convert the user's natural language input into a JSON object.
Return ONLY valid JSON with no markdown fences.

Available regions: MY, SG, HK, TW
Available query_types: bottleneck_analysis, delivery_status, route_optimisation,
                       incident_report, driver_availability, cost_analysis

Response schema:
{
  "query_type": "<one of the types above>",
  "region": "<MY|SG|HK|TW>",
  "metric": "<relevant metric, e.g. delivery_time | cost | throughput>",
  "time_frame": "<realtime|today|week|month>",
  "filters": {}
}"""


async def parse_nl_command(user_input: str) -> dict[str, Any]:
    """Convert a natural-language logistics request into a structured query dict.

    Example
    -------
    >>> await parse_nl_command("Show me delivery bottlenecks in KL right now")
    {"query_type": "bottleneck_analysis", "region": "MY",
     "metric": "delivery_time", "time_frame": "realtime", "filters": {}}
    """
    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    response = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=256,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Parse: {user_input}"}],
    )

    raw_text = response.content[0].text.strip()
    return json.loads(raw_text)
