"""
Intelligent Model Router – Weeks 7-8
Routes queries to the cheapest Anthropic model that can handle them,
tracking usage and cost savings across the fleet.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any

from anthropic import Anthropic

# Cost per 1 000 output tokens (USD) – approximate list prices
_MODEL_COST_PER_1K: dict[str, float] = {
    "claude-3-5-haiku-20241022": 0.0001,   # ~$0.10 / 1M tokens
    "claude-3-5-sonnet-20241022": 0.003,   # ~$3.00 / 1M tokens
    "claude-3-opus-20240229": 0.015,       # ~$15.00 / 1M tokens  (fraud escalation)
}

_CLASSIFIER_SYSTEM = """Classify the complexity of a logistics support query.
Return ONLY valid JSON.
Schema: {"complexity": "simple|complex|escalate", "reason": "<one sentence>"}
- simple: routine lookups, status checks, basic FAQs
- complex: multi-step reasoning, optimisation, cost analysis
- escalate: suspected fraud, high-value anomalies, regulatory queries"""


@dataclass
class RouteResult:
    query: str
    complexity: str
    model_used: str
    response_text: str
    tokens_used: int
    cost_usd: float
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class RouterStats:
    total_queries: int = 0
    haiku_count: int = 0
    sonnet_count: int = 0
    opus_count: int = 0
    total_cost_usd: float = 0.0
    # Hypothetical cost if every query used opus
    hypothetical_all_opus_usd: float = 0.0

    @property
    def savings_usd(self) -> float:
        return self.hypothetical_all_opus_usd - self.total_cost_usd

    @property
    def savings_pct(self) -> float:
        if self.hypothetical_all_opus_usd == 0:
            return 0.0
        return (self.savings_usd / self.hypothetical_all_opus_usd) * 100


class IntelligentModelRouter:
    """Routes each query to the cheapest model able to handle it."""

    def __init__(self) -> None:
        self._client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.stats = RouterStats()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def route_and_execute(self, query: str, context: dict[str, Any] | None = None) -> RouteResult:
        """Classify, route, and execute a query.  Returns a :class:`RouteResult`."""
        context = context or {}

        # Step 1 – classify complexity
        complexity = await self.classify_query(query)

        # Step 2 – select model
        model = self._select_model(complexity, context)

        # Step 3 – execute
        response = self._client.messages.create(
            model=model,
            max_tokens=512,
            system="You are a helpful logistics support assistant for Southeast Asia.",
            messages=[{"role": "user", "content": query}],
        )

        output_text = response.content[0].text.strip()
        tokens = response.usage.output_tokens
        cost = (tokens / 1000) * _MODEL_COST_PER_1K[model]

        result = RouteResult(
            query=query,
            complexity=complexity,
            model_used=model,
            response_text=output_text,
            tokens_used=tokens,
            cost_usd=cost,
        )

        self._update_stats(model, tokens, cost)
        return result

    async def classify_query(self, query: str) -> str:
        """Return 'simple', 'complex', or 'escalate' for *query*."""
        response = self._client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=64,
            system=_CLASSIFIER_SYSTEM,
            messages=[{"role": "user", "content": query}],
        )
        data = json.loads(response.content[0].text.strip())
        return data.get("complexity", "simple")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _select_model(self, complexity: str, context: dict[str, Any]) -> str:
        amount = context.get("amount", 0)

        # High-value transactions → always use the more capable model
        if amount > 10_000:
            return "claude-3-5-sonnet-20241022"

        if complexity == "simple":
            return "claude-3-5-haiku-20241022"
        elif complexity == "complex":
            return "claude-3-5-sonnet-20241022"
        else:  # escalate (suspected fraud, regulatory)
            return "claude-3-opus-20240229"

    def _update_stats(self, model: str, tokens: int, cost: float) -> None:
        opus_cost = (tokens / 1000) * _MODEL_COST_PER_1K["claude-3-opus-20240229"]

        self.stats.total_queries += 1
        self.stats.total_cost_usd += cost
        self.stats.hypothetical_all_opus_usd += opus_cost

        if "haiku" in model:
            self.stats.haiku_count += 1
        elif "sonnet" in model:
            self.stats.sonnet_count += 1
        else:
            self.stats.opus_count += 1
