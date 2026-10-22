"""
Room / lobby / phase state machine for Whip Count multiplayer.

Pure Python, no networking, no game logic (no stanceOf, no scoring — that
stays client-side in shared/engine.js per the architecture decision recorded
in HANDOVER.md 11a). This module only tracks who is in a room, what phase
the round is in, and what settings the teacher picked. The server built on
top of this (server.py) is a thin relay: it broadcasts state and passes
game-event payloads through without interpreting them.
"""

from __future__ import annotations

import random
import string
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum


class Phase(Enum):
    LOBBY = "lobby"
    CLAUSE_PITCH = "clause_pitch"
    BRIEF = "brief"
    WHIP = "whip"
    NEGOTIATION = "negotiation"
    AMENDMENT = "amendment"
    DIVISION = "division"
    RESULTS = "results"


# Order phases advance through on a plain "next phase" call. Teacher can
# still jump to any phase explicitly (goto_phase) — lessons never run to
# the clock, and a teacher may need to skip or redo a step.
PHASE_ORDER = [
    Phase.LOBBY,
    Phase.CLAUSE_PITCH,
    Phase.BRIEF,
    Phase.WHIP,
    Phase.NEGOTIATION,
    Phase.AMENDMENT,
    Phase.DIVISION,
    Phase.RESULTS,
]

VALID_PLAYER_COUNTS = (3, 5, 7, 9)

# Room codes: fixed-width, uppercase, excludes visually ambiguous characters
# (0/O, 1/I) since a code gets read off a projector across a classroom.
_CODE_ALPHABET = "".join(c for c in string.ascii_uppercase + string.digits if c not in "01OI")
_CODE_LENGTH = 4


class RoomError(ValueError):
    """Raised for any invalid state transition or request on a Room."""


@dataclass
class RoomSettings:
    player_count: int = 5
    pack_id: str = "climate2026"
    clause_id: str | None = None  # None = random clause each round
    whip_count_enabled: bool = True  # teacher toggle per lesson (11a #2)
    full_assembly: bool = False  # remaining pack countries vote alongside players
    word_limit_min: int = 60
    word_limit_max: int = 150
    negotiation_seconds: int = 480  # 8 minutes, mid-point of the 6-10 min spec
    tone_mode: str = "standard"  # "standard" (section 10) or "junior" (11a #6 exception)

    def __post_init__(self) -> None:
        if self.player_count not in VALID_PLAYER_COUNTS:
            raise RoomError(f"player_count must be one of {VALID_PLAYER_COUNTS}, got {self.player_count}")
        if self.tone_mode not in ("standard", "junior"):
            raise RoomError(f"tone_mode must be 'standard' or 'junior', got {self.tone_mode!r}")


@dataclass
class Player:
    id: str
    name: str
    country: str | None = None
    connected: bool = True
    joined_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "country": self.country,
            "connected": self.connected,
        }


@dataclass
class LogEntry:
    seq: int
    player_id: str | None
    kind: str
    payload: dict
    ts: float
    round_number: int
    visible_to: frozenset[str] | None = None  # None = every player can see it; the teacher always can

    def to_dict(self) -> dict:
        return {
            "seq": self.seq,
            "playerId": self.player_id,
            "kind": self.kind,
            "payload": self.payload,
            "ts": self.ts,
            "roundNumber": self.round_number,
        }


class Room:
    def __init__(self, code: str, settings: RoomSettings | None = None):
        self.code = code
        self.settings = settings or RoomSettings()
        self.phase = Phase.LOBBY
        self.players: dict[str, Player] = {}
        self.teacher_connected = False
        self.round_number = 1
        self._log: list[LogEntry] = []
        self._seq = 0

    # ---- players ----

    def add_player(self, name: str) -> Player:
        if self.phase is not Phase.LOBBY:
            raise RoomError("cannot join after the round has started")
        if len(self.players) >= self.settings.player_count:
            raise RoomError(f"room is full ({self.settings.player_count} players)")
        player_id = uuid.uuid4().hex[:8]
        player = Player(id=player_id, name=name)
        self.players[player_id] = player
        return player

    def remove_player(self, player_id: str) -> None:
        self.players.pop(player_id, None)

    def set_player_connected(self, player_id: str, connected: bool) -> None:
        player = self.players.get(player_id)
        if player is None:
            raise RoomError(f"no such player {player_id!r} in room {self.code}")
        player.connected = connected

    def is_full(self) -> bool:
        return len(self.players) >= self.settings.player_count

    # ---- countries ----

    def assign_countries(self, assignments: dict[str, str]) -> None:
        """assignments: player_id -> country name. Must cover exactly the
        current roster, one country per player, no repeats."""
        roster = set(self.players.keys())
        given = set(assignments.keys())
        if given != roster:
            raise RoomError("country assignments must cover exactly the current player roster")
        countries = list(assignments.values())
        if len(set(countries)) != len(countries):
            raise RoomError("each player must be assigned a distinct country")
        for player_id, country in assignments.items():
            self.players[player_id].country = country

    def random_assign_countries(self, available_countries: list[str]) -> None:
        if len(available_countries) < len(self.players):
            raise RoomError("not enough countries in the pack to cover every player")
        picks = random.sample(available_countries, len(self.players))
        self.assign_countries(dict(zip(self.players.keys(), picks)))

    # ---- phase ----

    def advance_phase(self) -> Phase:
        idx = PHASE_ORDER.index(self.phase)
        if idx == len(PHASE_ORDER) - 1:
            raise RoomError("already at the final phase; start a new round instead")
        if self.phase is Phase.LOBBY:
            self._check_odd_roster()
        self.phase = PHASE_ORDER[idx + 1]
        return self.phase

    def goto_phase(self, phase: Phase) -> Phase:
        if not isinstance(phase, Phase):
            raise RoomError(f"not a valid phase: {phase!r}")
        if phase is not Phase.LOBBY and phase is not self.phase:
            self._check_odd_roster()
        self.phase = phase
        return self.phase

    def new_round(self) -> None:
        """Start another round with the same roster (leaderboard persists
        within a lesson's session; wiping between lessons is a caller
        concern — see HANDOVER 11a #4). Goes back to CLAUSE_PITCH, not
        BRIEF: a fresh round means a fresh open pitch for which clause gets
        debated next (11a), not a re-run of the last round's clause."""
        self._check_odd_roster()
        self.round_number += 1
        self.phase = Phase.CLAUSE_PITCH
        self.settings.clause_id = None
        for player in self.players.values():
            player.country = None

    def _check_odd_roster(self) -> None:
        n = len(self.players)
        if n == 0 or n % 2 == 0:
            raise RoomError(
                f"cannot proceed past the lobby with {n} players — odd counts only "
                "(prevents tied divisions, see HANDOVER.md section 10)"
            )

    # ---- settings ----

    def update_settings(self, **changes) -> None:
        # Also allowed in CLAUSE_PITCH: that's when the teacher's client
        # locks in the clauseId resolved from the open pitch/second (11a),
        # since a player can't call update_settings themselves.
        if self.phase not in (Phase.LOBBY, Phase.CLAUSE_PITCH):
            raise RoomError("settings can only change in the lobby or during the clause pitch")
        current = self.settings.__dict__.copy()
        current.update(changes)
        self.settings = RoomSettings(**current)

    # ---- event log (thin relay: opaque game-event passthrough) ----

    def log_event(self, player_id: str | None, kind: str, payload: dict,
                  visible_to: set[str] | None = None) -> LogEntry:
        self._seq += 1
        entry = LogEntry(seq=self._seq, player_id=player_id, kind=kind, payload=payload, ts=time.time(),
                          round_number=self.round_number,
                          visible_to=frozenset(visible_to) if visible_to is not None else None)
        self._log.append(entry)
        return entry

    def events_since(self, seq: int, viewer_player_id: str | None = None) -> list[LogEntry]:
        """viewer_player_id=None means the teacher — sees every entry,
        public or private. A player only sees public entries (visible_to
        is None) plus private ones they're a party to."""
        entries = [e for e in self._log if e.seq > seq]
        if viewer_player_id is None:
            return entries
        return [e for e in entries if e.visible_to is None or viewer_player_id in e.visible_to]

    # ---- serialisation ----

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "phase": self.phase.value,
            "roundNumber": self.round_number,
            "teacherConnected": self.teacher_connected,
            "settings": {
                "playerCount": self.settings.player_count,
                "packId": self.settings.pack_id,
                "clauseId": self.settings.clause_id,
                "whipCountEnabled": self.settings.whip_count_enabled,
                "fullAssembly": self.settings.full_assembly,
                "wordLimitMin": self.settings.word_limit_min,
                "wordLimitMax": self.settings.word_limit_max,
                "negotiationSeconds": self.settings.negotiation_seconds,
                "toneMode": self.settings.tone_mode,
            },
            "players": [p.to_dict() for p in self.players.values()],
        }


class RoomRegistry:
    """In-memory store of live rooms, keyed by room code."""

    def __init__(self):
        self._rooms: dict[str, Room] = {}

    def create_room(self, settings: RoomSettings | None = None) -> Room:
        code = self._new_code()
        room = Room(code, settings)
        self._rooms[code] = room
        return room

    def get(self, code: str) -> Room | None:
        return self._rooms.get(code.upper())

    def drop(self, code: str) -> None:
        self._rooms.pop(code.upper(), None)

    def _new_code(self) -> str:
        for _ in range(100):
            code = "".join(random.choices(_CODE_ALPHABET, k=_CODE_LENGTH))
            if code not in self._rooms:
                return code
        raise RoomError("could not generate a free room code")
