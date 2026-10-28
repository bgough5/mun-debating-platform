"""Offline, deterministic provider. Calls nothing; used for tests, demo mode and by default.

Its "suggestions" are deliberately transparent: it restates the archetype model's
estimate and cites only evidence already recorded in the platform. With nothing
recorded it gives no source, so the suggestion is stored as unknown.
"""
from __future__ import annotations

import hashlib
import re

from app.ai.base import PositionRequest, PositionSuggestion

OFFER_WORDS = re.compile(r"\b(if|provided|in exchange|in return|would support|could support|amend|condition)\b", re.I)
STANCE_WORDS = {2: "strongly supports", 1: "supports", 0: "is undecided on", -1: "opposes", -2: "strongly opposes"}


def _pick(options: list[str], *keys) -> str:
    h = int(hashlib.sha256("|".join(map(str, keys)).encode()).hexdigest()[:8], 16)
    return options[h % len(options)]


class FakeProvider:
    name = "offline (no AI service)"
    sends_data_off_device = False

    def suggest_position(self, req: PositionRequest) -> PositionSuggestion:
        if not req.known_sources:
            return PositionSuggestion(None, f"No recorded source for {req.country} on this text, so the position is unknown. "
                                            "Find an official statement or a voting record and record it as evidence.",
                                      [], self.name)
        # With sources, restate what they already say (the median of recorded positions).
        positions = sorted(p for p, _ in req.known_sources if p is not None)
        pos = positions[len(positions) // 2] if positions else None
        cites = [c for _, c in req.known_sources if c][:3]
        return PositionSuggestion(pos, f"Based only on evidence already recorded for {req.country}: "
                                       f"it {STANCE_WORDS.get(pos, 'has an unclear view of')} this text. Verify the sources.",
                                  cites, self.name)

    def roleplay(self, country, stance_hint, archetype_lines, history, student_message):
        s = 0 if stance_hint is None else max(-2, min(2, stance_hint))
        if OFFER_WORDS.search(student_message or "") and s < 2:
            s += 1          # a concrete conditional offer moves the AI delegation one step
            opener = _pick(["That offer changes our calculation.", "We could look at that.", "Put that in writing and we will consider it."],
                           country, len(history))
        else:
            opener = _pick(["Our position has not changed.", "We have heard this argument before.", "You will need to give us more than that."],
                           country, len(history))
        line = archetype_lines.get(s) or archetype_lines.get(str(s)) or f"{country} {STANCE_WORDS[s]} this text."
        follow = _pick(["What exactly would your delegation offer in return?", "Which paragraph are you prepared to change?",
                        "Who pays for this, and when?", "How would this be checked?"], country, student_message)
        return f"{opener} {line} {follow}"

    def coach(self, criterion, descriptors, self_level, reflection):
        if not descriptors:
            return f"Think about {criterion}: what would a stronger version of your speech do differently?"
        lvl = self_level or 1
        here = descriptors[min(lvl, len(descriptors)) - 1]
        nxt = descriptors[lvl] if lvl < len(descriptors) else None
        out = [f"You placed yourself at level {lvl} for {criterion}: “{here}”."]
        if nxt:
            out.append(f"The next level up is: “{nxt}”.")
            out.append("Which one moment in your speech could you rework to reach it? What would you need to prepare?")
        else:
            out.append("That's the top band. What would make it consistent across a whole speech?")
        if reflection:
            out.append("You wrote that you would change something next time: try just that one change in your next practice.")
        return " ".join(out)
