"""The provider interface every AI backend implements."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class PositionSuggestion:
    position: int | None          # -2..+2, or None when the provider can't say
    rationale: str
    sources: list = field(default_factory=list)   # each a citation or URL; empty -> stored as unknown
    provider: str = ""


@dataclass
class PositionRequest:
    """What is sent to a provider. Country and resolution text only: never student names or student writing
    (spec §8.7), unless the school has approved that use."""
    iso3: str
    country: str
    topic: str
    paragraph_text: str
    tags: list
    known_sources: list = field(default_factory=list)    # citations already recorded as evidence


class AIProvider(Protocol):
    name: str
    sends_data_off_device: bool

    def suggest_position(self, req: PositionRequest) -> PositionSuggestion: ...

    def roleplay(self, country: str, stance_hint: int | None, archetype_lines: dict, history: list[tuple[str, str]],
                 student_message: str) -> str: ...

    def coach(self, criterion: str, descriptors: list[str], self_level: int | None, reflection: str) -> str: ...
