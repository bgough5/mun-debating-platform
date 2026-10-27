"""AI features behind a provider interface (spec Phase 4, §8.7).

- The offline FakeProvider is always used unless the coordinator has recorded
  school approval AND chosen a real provider. It calls nothing on the network.
- Every AI suggestion of a country's position is stored as an "AI estimate —
  verify" with its sources, or as unknown (no position) when it has no source.
- AI never writes a student's speech, clause or amendment: the coach asks
  questions and points to the rubric; the practice delegation only plays a role.
"""
from __future__ import annotations

from app.ai.base import AIProvider, PositionSuggestion
from app.ai.fake import FakeProvider


class AIDisabled(Exception):
    pass


REAL_PROVIDERS = ("anthropic",)      # the providers get_provider can build; anything else is not live AI


def ai_live(settings) -> bool:
    """True only when a real AI provider is selected AND the school's approval is recorded (D-053, D-066)."""
    cfg = settings.get("ai", {}) or {}
    return cfg.get("provider", "fake") in REAL_PROVIDERS and bool(cfg.get("school_approved"))


def negotiation_label(settings) -> str:
    """What students see: never call the offline rule-based partner "AI" (D-066)."""
    return "AI delegation" if ai_live(settings) else "Practice negotiation (rule-based)"


def get_provider(settings) -> AIProvider:
    cfg = settings.get("ai", {}) or {}
    name = cfg.get("provider", "fake")
    if name == "off":
        raise AIDisabled("AI features are switched off in the settings.")
    if name == "fake" or not cfg.get("school_approved"):
        # Without recorded school approval only the offline provider is ever used.
        return FakeProvider()
    if name == "anthropic":
        from app.ai.anthropic_provider import AnthropicProvider
        return AnthropicProvider(model=cfg.get("model") or "claude-opus-5-5", api_key_env=cfg.get("api_key_env") or "ANTHROPIC_API_KEY")
    raise AIDisabled(f"Unknown AI provider {name!r}.")


__all__ = ["AIProvider", "PositionSuggestion", "FakeProvider", "get_provider", "AIDisabled", "ai_live", "negotiation_label"]
