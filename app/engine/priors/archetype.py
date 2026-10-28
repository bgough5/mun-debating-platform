"""Archetype prior: the v2 `stanceOf` maths from shared/engine.js, ported unchanged.

`raw_score` is what the new engine uses as the "model estimate (archetype)"
prior. `stance_of` keeps the old five-bucket output only so the port can be
parity-tested against the frozen JavaScript (tests/fixtures/stance_parity.json).
The arithmetic order matches the JS exactly so floats agree bit for bit.
"""
from __future__ import annotations

from dataclasses import dataclass

STANCE_NAME = {2: "Strongly support", 1: "Support", 0: "Abstain", -1: "Oppose", -2: "Strongly oppose"}


@dataclass(frozen=True)
class Stance:
    s: int
    raw: float | None = None
    forced: bool = False
    line: str | None = None


def raw_score(weights: dict[str, float], tags: list[str], affinities: dict[str, dict[str, float]]) -> float | None:
    """Weighted average archetype affinity for a tag set, or None if it can't be computed.

    `weights` must preserve the original blend order (dict insertion order), as
    the JS iterates Object.entries(country.w).
    """
    if not tags or not weights:
        return None
    total = 0.0
    wsum = 0.0
    for arch, wt in weights.items():
        aff = affinities.get(arch, {})
        sub = 0
        for t in tags:
            sub += aff.get(t, 0) or 0
        total += (sub / len(tags)) * wt
        wsum += wt
    if wsum == 0:
        return None
    return total / wsum


def bucket(raw: float) -> int:
    return 2 if raw >= 1.15 else 1 if raw >= 0.4 else 0 if raw > -0.4 else -1 if raw > -1.15 else -2


def stance_of(weights, tags, affinities, override: tuple[int, str] | None = None) -> Stance:
    """Exact port of v2 Engine.stanceOf. `override` is (s, line) when one applies."""
    if override is not None:
        return Stance(s=override[0], line=override[1], forced=True)
    if not tags:
        return Stance(s=0)
    raw = raw_score(weights, tags, affinities)
    return Stance(s=bucket(raw), raw=raw)


def apply_tag_amendment(tags: list[str], add: list[str], remove: list[str]) -> list[str]:
    """Port of v2 Engine.applyAmendment (tag add/remove), kept for parity tests."""
    nxt = list(tags)
    for t in remove:
        nxt = [x for x in nxt if x != t]
    for t in add:
        if t not in nxt:
            nxt.append(t)
    return nxt
