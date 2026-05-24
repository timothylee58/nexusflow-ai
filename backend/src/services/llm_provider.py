"""Multi-provider LLM gateway: anthropic | openai | ilmu | heuristic."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Literal

from src.config import settings

logger = logging.getLogger(__name__)

LlmTier = Literal["parse", "analyze"]
VALID_PROVIDERS = frozenset({"auto", "heuristic", "anthropic", "openai", "ilmu"})


@dataclass(frozen=True)
class LlmCompletion:
    text: str
    model: str
    tokens_used: int


def resolve_llm_provider() -> str:
    """Return active provider id: heuristic | anthropic | openai | ilmu."""
    requested = (settings.llm_provider or "auto").strip().lower()
    if requested not in VALID_PROVIDERS:
        logger.warning("Unknown LLM_PROVIDER=%s; using auto", requested)
        requested = "auto"

    if requested == "heuristic":
        return "heuristic"

    if requested == "anthropic":
        return "anthropic" if settings.anthropic_api_key else "heuristic"

    if requested == "openai":
        return "openai" if settings.openai_api_key else "heuristic"

    if requested == "ilmu":
        return "ilmu" if _ilmu_api_key() else "heuristic"

    # auto — prefer MY sovereign Ilmu, then Anthropic, then OpenAI
    if _ilmu_api_key():
        return "ilmu"
    if settings.anthropic_api_key:
        return "anthropic"
    if settings.openai_api_key:
        return "openai"
    return "heuristic"


def is_llm_enabled() -> bool:
    return resolve_llm_provider() != "heuristic"


def _ilmu_api_key() -> str | None:
    return settings.ilmu_api_key or settings.openai_api_key


def _model_for_tier(provider: str, tier: LlmTier) -> str:
    if provider == "anthropic":
        return (
            settings.anthropic_parse_model
            if tier == "parse"
            else settings.anthropic_analysis_model
        )
    if provider == "ilmu":
        return settings.ilmu_parse_model if tier == "parse" else settings.ilmu_analysis_model
    return settings.openai_parse_model if tier == "parse" else settings.openai_analysis_model


def _complete_anthropic(*, system: str, user: str, model: str, max_tokens: int) -> LlmCompletion:
    from anthropic import Anthropic

    client = Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = response.content[0].text
    tokens = response.usage.output_tokens if response.usage else 0
    return LlmCompletion(text=text, model=model, tokens_used=tokens)


def _complete_openai_compatible(
    *,
    api_key: str,
    base_url: str | None,
    system: str,
    user: str,
    model: str,
    max_tokens: int,
) -> LlmCompletion:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
    )
    choice = response.choices[0].message.content or ""
    tokens = response.usage.completion_tokens if response.usage else 0
    return LlmCompletion(text=choice, model=model, tokens_used=tokens)


def _complete_sync(*, system: str, user: str, tier: LlmTier) -> LlmCompletion:
    provider = resolve_llm_provider()
    model = _model_for_tier(provider, tier)
    max_tokens = 256 if tier == "parse" else 1024

    if provider == "anthropic":
        return _complete_anthropic(system=system, user=user, model=model, max_tokens=max_tokens)

    if provider == "ilmu":
        return _complete_openai_compatible(
            api_key=_ilmu_api_key() or "",
            base_url=settings.ilmu_base_url,
            system=system,
            user=user,
            model=model,
            max_tokens=max_tokens,
        )

    if provider == "openai":
        return _complete_openai_compatible(
            api_key=settings.openai_api_key or "",
            base_url=settings.openai_base_url,
            system=system,
            user=user,
            model=model,
            max_tokens=max_tokens,
        )

    raise RuntimeError("LLM called while provider is heuristic")


async def complete_text(*, system: str, user: str, tier: LlmTier) -> LlmCompletion | None:
    if not is_llm_enabled():
        return None

    try:
        return await asyncio.to_thread(
            _complete_sync,
            system=system,
            user=user,
            tier=tier,
        )
    except Exception as exc:
        logger.error("LLM completion failed (%s): %s", resolve_llm_provider(), exc, exc_info=True)
        raise
