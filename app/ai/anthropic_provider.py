"""Anthropic (Claude) provider. NOT enabled by default and NOT tested against the live API.

It is used only when the coordinator records school approval and selects it
(Admin → Intelligence), with the `anthropic` package installed and an API key in
the named environment variable (never in the repository). Requests carry country
and resolution text only; student messages are sent only for the practice
delegation, which itself needs school approval (spec §8.7).
"""
from __future__ import annotations

import json
import os
import re

from app.ai.base import PositionRequest, PositionSuggestion

SYSTEM_POSITION = (
    "You estimate how a UN member state would likely vote on a draft resolution paragraph, for a school Model UN class. "
    "Only state a position you can support with real, citable sources (URLs or document symbols such as A/RES/..). "
    "If you cannot cite a source, return position null. Never present an estimate as fact. "
    'Reply with JSON only: {"position": -2..2 or null, "rationale": "...", "sources": ["..."]}'
)
SYSTEM_ROLEPLAY = (
    "You play a UN member state's delegation in a school Model UN practice negotiation, labelled to the student as AI. "
    "Stay in role, be brief (2-4 sentences), respond to the student's actual offer, and ask what they will give in return. "
    "Never write the student's speech, clause or amendment for them."
)
SYSTEM_COACH = (
    "You coach a school student on a practice speech using the rubric descriptors given. Ask 2-3 questions that point "
    "them toward the next level. Do not write or rewrite any part of their speech."
)


class AnthropicProvider:
    name = "Anthropic Claude (school-approved)"
    sends_data_off_device = True

    def __init__(self, model: str = "claude-opus-5-5", api_key_env: str = "ANTHROPIC_API_KEY", client=None):
        self.model = model
        if client is None:
            import anthropic          # optional dependency: pip install anthropic
            key = os.environ.get(api_key_env)
            if not key:
                raise RuntimeError(f"Set the {api_key_env} environment variable on this laptop to use the AI service.")
            client = anthropic.Anthropic(api_key=key)
        self.client = client

    def _ask(self, system: str, content: str, max_tokens: int = 2000) -> str:
        response = self.client.messages.create(
            model=self.model, max_tokens=max_tokens, system=system,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": content}],
        )
        if response.stop_reason == "refusal":
            return ""
        return "".join(b.text for b in response.content if b.type == "text")

    def suggest_position(self, req: PositionRequest) -> PositionSuggestion:
        text = self._ask(SYSTEM_POSITION, json.dumps({"country": req.country, "iso3": req.iso3, "topic": req.topic,
                                                      "paragraph": req.paragraph_text, "tags": req.tags}))
        m = re.search(r"\{.*\}", text, re.S)
        try:
            data = json.loads(m.group(0)) if m else {}
        except json.JSONDecodeError:
            data = {}
        pos = data.get("position")
        pos = int(pos) if isinstance(pos, (int, float)) and -2 <= pos <= 2 else None
        sources = [str(s)[:300] for s in (data.get("sources") or []) if str(s).strip()][:5]
        return PositionSuggestion(pos, str(data.get("rationale") or "")[:1000], sources, self.name)

    def roleplay(self, country, stance_hint, archetype_lines, history, student_message):
        convo = "\n".join(f"{who}: {txt}" for who, txt in history[-10:])
        return self._ask(SYSTEM_ROLEPLAY, f"You are {country}. Your likely stance (−2..+2): {stance_hint}.\n{convo}\n"
                                          f"Student: {student_message}", max_tokens=600)

    def coach(self, criterion, descriptors, self_level, reflection):
        return self._ask(SYSTEM_COACH, json.dumps({"criterion": criterion, "levels": descriptors, "self_level": self_level,
                                                   "reflection": reflection}), max_tokens=800)
