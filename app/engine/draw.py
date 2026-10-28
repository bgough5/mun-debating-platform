"""Debating draws (spec Phase 3): seeded random first round, then power-paired.

Pure functions, no database. Deterministic: the same teams, history and seed
always give the same draw.

Rules, in order of priority:
1. Every active team debates once per round, except one bye if the number is odd.
   The bye goes to the lowest-ranked team (random order in round 1) that hasn't had one.
2. No repeat pairings where avoidable.
3. No two teams from the same house where avoidable (house carnivals), if asked.
4. Power pairing: teams are paired within their win bracket, top down, pulling the
   next team up when a bracket is odd.
5. Sides: the team that has been affirmative more often goes negative; ties are
   broken by a seeded coin, so they are balanced over the event and reproducible.
Rooms go to the top of the draw first (accessible rooms to teams that need them);
adjudicators are allocated by rating, best to the top brackets, avoiding anyone
from either team's house.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class TeamState:
    id: int
    name: str = ""
    house: int | None = None
    wins: float = 0
    points: float = 0
    margin: float = 0
    aff: int = 0
    neg: int = 0
    byes: int = 0
    opponents: set = field(default_factory=set)
    needs_accessible: bool = False


@dataclass
class Adj:
    id: int
    rating: float = 5
    house: int | None = None
    seen_teams: set = field(default_factory=set)


@dataclass
class Room:
    id: int
    accessible: bool = True
    priority: int = 50


@dataclass
class Pair:
    aff: int
    neg: int | None            # None = bye
    bracket: float = 0
    position: int = 0
    room: int | None = None
    adjudicators: list = field(default_factory=list)   # (adj_id, role)
    relaxed: list = field(default_factory=list)       # which rules had to be broken, in plain English


def rank_key(t: TeamState):
    """Ladder order: wins, then total points, then margin, then id (D-012 style fixed tie-break)."""
    return (-t.wins, -t.points, -t.margin, t.id)


def _side_clash(a: TeamState, b: TeamState) -> bool:
    """Both teams are owed the same side (both have been affirmative more often, or both negative)."""
    ba, bb = a.aff - a.neg, b.aff - b.neg
    return (ba > 0 and bb > 0) or (ba < 0 and bb < 0)


def _ok(a: TeamState, b: TeamState, avoid_house: bool, level: int) -> bool:
    """Level 0 keeps every rule; each higher level gives up one, least important first:
    side balance, then same house, then repeat pairings."""
    if level <= 2 and b.id in a.opponents:
        return False
    if level <= 1 and avoid_house and a.house is not None and a.house == b.house:
        return False
    if level == 0 and _side_clash(a, b):
        return False
    return True


def _pair_greedy(order: list[TeamState], avoid_house: bool) -> list[tuple[TeamState, TeamState, list]]:
    """Pair down the ordered list, taking for each team the nearest valid opponent.
    Relaxes the house rule, then the repeat rule, only when nothing else works."""
    remaining = list(order)
    pairs = []
    while remaining:
        a = remaining.pop(0)
        partner, broke = None, []
        for level in (0, 1, 2, 3):
            for i, b in enumerate(remaining):
                if _ok(a, b, avoid_house, level):
                    partner = remaining.pop(i)
                    broke = _broken(a, partner, avoid_house)
                    break
            if partner:
                break
        if partner is None:      # only possible if one team is left (handled by bye before)
            raise ValueError("odd number of teams reached pairing")
        pairs.append((a, partner, broke))
    return _repair(pairs, avoid_house)


def _repair(pairs, avoid_house):
    """Try swapping opponents between pairs to remove any broken rule (keeps order otherwise)."""
    def bad(a, b):
        return ((b.id in a.opponents) * 4 + (avoid_house and a.house is not None and a.house == b.house) * 2
                + _side_clash(a, b))
    pairs = [list(p) for p in pairs]
    for i, (a, b, broke) in enumerate(pairs):
        cost = bad(a, b)
        if not cost:
            continue
        best = None
        for j, (c, d, _) in enumerate(pairs):
            if j == i:
                continue
            new_cost = bad(a, d) + bad(c, b)
            if new_cost < cost + bad(c, d):
                if best is None or new_cost < best[1]:
                    best = (j, new_cost)
        if best is not None:
            j = best[0]
            c, d, _ = pairs[j]
            pairs[i] = [a, d, _broken(a, d, avoid_house)]
            pairs[j] = [c, b, _broken(c, b, avoid_house)]
    return [tuple(p) for p in pairs]


def _broken(a, b, avoid_house):
    out = []
    if avoid_house and a.house is not None and a.house == b.house:
        out.append("same house")
    if b.id in a.opponents:
        out.append("repeat pairing")
    return out


def _sides(a: TeamState, b: TeamState, rng: random.Random) -> tuple[TeamState, TeamState]:
    bal_a, bal_b = a.aff - a.neg, b.aff - b.neg
    if bal_a > bal_b:
        return b, a
    if bal_b > bal_a:
        return a, b
    return (a, b) if rng.random() < 0.5 else (b, a)


def make_draw(teams: list[TeamState], kind: str, seed: int, avoid_house: bool = True) -> list[Pair]:
    rng = random.Random(seed)
    active = sorted(teams, key=lambda t: t.id)
    if kind == "random":
        order = list(active)
        rng.shuffle(order)
    else:
        order = sorted(active, key=rank_key)
    bye = None
    if len(order) % 2:
        # lowest-placed team that hasn't had a bye; if everyone has, the lowest-placed
        candidates = [t for t in reversed(order) if t.byes == min(x.byes for x in order)]
        bye = candidates[0]
        order = [t for t in order if t.id != bye.id]
    pairs_raw = _pair_greedy(order, avoid_house)
    pairs = []
    for i, (a, b, broke) in enumerate(pairs_raw):
        aff, neg = _sides(a, b, rng)
        pairs.append(Pair(aff.id, neg.id, bracket=max(a.wins, b.wins), position=i + 1, relaxed=broke))
    if bye:
        pairs.append(Pair(bye.id, None, bracket=bye.wins, position=len(pairs) + 1))
    return pairs


def allocate_rooms(pairs: list[Pair], rooms: list[Room], teams: dict[int, TeamState]) -> list[str]:
    """Top of the draw gets the highest-priority rooms; teams that need an accessible room get one first."""
    problems = []
    free = sorted(rooms, key=lambda r: (-r.priority, r.id))
    debates = [p for p in pairs if p.neg is not None]
    needs = [p for p in debates if teams[p.aff].needs_accessible or teams[p.neg].needs_accessible]
    for p in needs + [p for p in debates if p not in needs]:
        pool = [r for r in free if r.accessible] if p in needs else free
        if not pool:
            pool = free
            if p in needs:
                problems.append(f"No accessible room left for debate {p.position}.")
        if not pool:
            problems.append(f"Not enough rooms: debate {p.position} has no room.")
            continue
        room = pool[0]
        p.room = room.id
        free.remove(room)
    return problems


def allocate_adjudicators(pairs: list[Pair], adjs: list[Adj], teams: dict[int, TeamState]) -> list[str]:
    """Best adjudicators to the strongest brackets; no adjudicator from either team's house where avoidable.
    Spare adjudicators become panellists (rating >= 5) or trainees, top debates first."""
    problems = []
    debates = sorted([p for p in pairs if p.neg is not None], key=lambda p: (-p.bracket, p.position))
    pool = sorted(adjs, key=lambda a: (-a.rating, a.id))

    def conflict(a: Adj, p: Pair) -> int:
        houses = {teams[p.aff].house, teams[p.neg].house} - {None}
        c = 2 if (a.house is not None and a.house in houses) else 0
        c += 1 if (p.aff in a.seen_teams or p.neg in a.seen_teams) else 0
        return c

    for p in debates:
        if not pool:
            problems.append(f"Not enough adjudicators: debate {p.position} has none.")
            continue
        best = min(pool, key=lambda a: (conflict(a, p), -a.rating, a.id))
        if conflict(best, p) >= 2:
            problems.append(f"Debate {p.position}: the only available adjudicator is from one of the teams' houses.")
        p.adjudicators.append((best.id, "chair"))
        pool.remove(best)
    i = 0
    while pool and debates:
        p = debates[i % len(debates)]
        cand = [a for a in pool if conflict(a, p) < 2] or pool
        a = cand[0]
        p.adjudicators.append((a.id, "panel" if a.rating >= 5 else "trainee"))
        pool.remove(a)
        i += 1
    return problems


# ---------- small groups and class practice (D-022) ----------

def plan_practice(n: int, max_per_team: int = 3) -> list[dict]:
    """How to split n students (1-25) into practice debates. Every student gets a role.

    Returns rooms like {"format": "3v3", "aff": 3, "neg": 3, "adjudicators": 1}
    or {"format": "solo", "speakers": 1}. Teams shrink and roles combine for small
    numbers; odd numbers become a student adjudicator rather than a left-out student.
    """
    if n <= 0:
        return []
    if n == 1:
        return [{"format": "solo", "speakers": 1, "note": "Solo speech practice with timer and rubric self-review."}]
    if n == 2:
        return [{"format": "1v1", "aff": 1, "neg": 1, "adjudicators": 0, "note": "Each speaker gives a case and a reply; peer-review each other."}]
    if n == 3:
        return [{"format": "1v1", "aff": 1, "neg": 1, "adjudicators": 1, "note": "One student adjudicates with the ballot, then swap."}]
    rooms = []
    left = n
    size = min(max_per_team, 3)
    while left > 0:
        if left >= 2 * size + 1 and (left - (2 * size + 1)) != 1:
            rooms.append({"format": f"{size}v{size}", "aff": size, "neg": size, "adjudicators": 1})
            left -= 2 * size + 1
        elif left >= 2 * size and (left - 2 * size) not in (1,):
            rooms.append({"format": f"{size}v{size}", "aff": size, "neg": size, "adjudicators": 0})
            left -= 2 * size
        elif left >= 5:
            rooms.append({"format": "2v2", "aff": 2, "neg": 2, "adjudicators": 1})
            left -= 5
        elif left == 4:
            rooms.append({"format": "2v2", "aff": 2, "neg": 2, "adjudicators": 0})
            left -= 4
        elif left == 3:
            rooms.append({"format": "1v1", "aff": 1, "neg": 1, "adjudicators": 1})
            left -= 3
        elif left == 2:
            rooms.append({"format": "1v1", "aff": 1, "neg": 1, "adjudicators": 0})
            left -= 2
        else:   # one left over: make them an extra adjudicator in the first room
            rooms[0]["adjudicators"] += 1
            left -= 1
    return rooms


ROLES = {
    1: ["Speaker: give your case, rebut the other side, and finish with a reply"],
    2: ["1st speaker: define the motion, set up the team line, give the first arguments",
        "2nd speaker: rebut, add arguments, then summarise (covers the 3rd speaker's job)"],
    3: ["1st speaker: define, team line, first arguments", "2nd speaker: rebuttal and main arguments",
        "3rd speaker: rebuttal and summary of the debate"],
    4: ["1st speaker: define, team line, first arguments", "2nd speaker: rebuttal and main arguments",
        "3rd speaker: rebuttal and summary", "Reply speaker: biased summary (one of the first two speakers)"],
}
