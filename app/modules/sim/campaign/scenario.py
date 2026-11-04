"""A scenario for the campaign: one installed pack committee, read once and then used without the database.

Countries' positions come from the real vote engine. For a set of commitments (tags) the engine's own
`build_inputs` gathers every source that applies (the pack's evidence on each tag, archetype priors, bloc
evidence, voting history) and `distribution` turns them into a mean and spread. The campaign adds its effects
(lobbying, endorsements) on top of that mean; it never replaces it. Results are cached per set of tags.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path

from app.db import one, rows
from app.engine.rules import VotingRule

PACKS = Path(__file__).resolve().parents[3] / "db" / "seed" / "packs"
ZERO_DRAFT = 3              # clauses the draft starts with; the rest of the pack's clauses become clause cards


@dataclass
class Member:
    iso3: str
    name: str
    region: str
    p5: bool
    group: str = ""          # the bloc whose members share a mood (as in the engine)
    rho: float = 0.0


@dataclass
class Scenario:
    code: str
    title: str
    fictional: bool
    committee_id: int
    resolution_id: int
    rule: VotingRule
    members: list[Member]
    tags: dict[str, str]                       # code -> what it commits countries to
    draft: list[dict]                          # the zero draft: [{"text", "tags"}]
    cards: list[dict]                          # clause cards: [{"id", "text", "tags", "kind"}]
    positions: dict[str, dict[str, int]]       # iso3 -> tag -> the pack's stated position (-2..2), for country files
    sources: dict[str, list[str]]              # iso3 -> source links (real-issue packs)
    news: list[dict]
    events: list[dict]                         # the scenario's own events (pack "campaign.events")
    c_yes: float
    c_no: float
    _dist: dict = field(default_factory=dict, repr=False)
    _loader: object = field(default=None, repr=False)

    @property
    def isos(self) -> list[str]:
        return [m.iso3 for m in self.members]

    def member(self, iso3: str) -> Member | None:
        return next((m for m in self.members if m.iso3 == iso3), None)

    def dist(self, tags) -> dict[str, tuple[float, float]]:
        """iso3 -> (mean, spread) of each country's position on a clause committing countries to these tags."""
        key = frozenset(t for t in tags if t in self.tags)
        if not key:
            return {m.iso3: (0.0, 1.5) for m in self.members}
        if key not in self._dist:
            self._dist[key] = self._loader(sorted(key))
        return self._dist[key]

    def warm(self, max_size: int = 3) -> int:
        """Work out every set of up to `max_size` tags now (the balance harness does this once per scenario)."""
        n = 0
        for k in range(1, max_size + 1):
            for combo in combinations(sorted(self.tags), k):
                self.dist(combo)
                n += 1
        return n


def load(conn, committee_id: int, code: str) -> Scenario:
    from app.engine.model import distribution
    from app.modules.mun.predict import active_model, build_inputs, committee_rule
    c = one(conn, "SELECT * FROM committee WHERE id = ?", (committee_id,))
    res = one(conn, "SELECT * FROM resolution WHERE committee_id = ? AND deleted_at IS NULL ORDER BY id LIMIT 1", (committee_id,))
    _, rule = committee_rule(conn, committee_id)
    _, params = active_model(conn)
    pack = json.loads((PACKS / f"{code}.json").read_text(encoding="utf-8"))
    dels = rows(conn, "SELECT d.iso3, c.name, c.region, c.p5 FROM delegation d JOIN country c ON c.iso3 = d.iso3 "
                      "WHERE d.committee_id = ? AND d.deleted_at IS NULL ORDER BY d.iso3", (committee_id,))
    members = [Member(d["iso3"], d["name"], d["region"] or "", bool(d["p5"])) for d in dels]
    target0 = {"kind": "paragraph", "id": None, "paragraph_id": None, "amendment_id": None, "resolution_id": res["id"],
               "committee_id": committee_id, "negate": False, "label": "Campaign clause"}
    first_tag = sorted(pack["tags"])[0]
    inputs, _ = build_inputs(conn, {**target0, "tags": [first_tag]}, params)
    groups = {ci.iso3: (ci.corr_group, ci.rho) for ci in inputs}
    for m in members:
        m.group, m.rho = groups.get(m.iso3, ("", 0.0))

    def loader(tags: list[str]) -> dict:
        inp, _ = build_inputs(conn_holder[0], {**target0, "tags": tags}, params)
        return {ci.iso3: (round((d := distribution(ci, params)).mu, 4), round(d.sigma, 4)) for ci in inp}

    conn_holder = [conn]
    operative = [{"text": p["text"], "tags": list(p["tags"])} for p in pack["resolution"]["operative"]]
    zero = operative[:ZERO_DRAFT]
    cards = [{"id": f"c{i + 1}", "text": p["text"], "tags": p["tags"], "kind": "pack"} for i, p in enumerate(operative[ZERO_DRAFT:])]
    camp = pack.get("campaign") or {}
    cards += [{"id": f"k{i + 1}", "text": c["text"], "tags": list(c["tags"]), "kind": "campaign"} for i, c in enumerate(camp.get("cards") or [])]
    covered = {t for c in cards for t in c["tags"]}
    for t, label in sorted(pack["tags"].items()):          # a plain card for any commitment no card offers, so every one can be proposed
        if t not in covered:
            cards.append({"id": f"t-{t}", "text": f"{label}.", "tags": [t], "kind": "commitment"})
    events = [{"id": f"s{i + 1}", "title": ev["title"], "body": ev["body"], "teaches": ev["teaches"], "effect": dict(ev["effect"]),
               "scenario": True} for i, ev in enumerate(camp.get("events") or [])]
    scn = Scenario(code=code, title=pack["title"], fictional=bool(pack.get("fictional")), committee_id=committee_id,
                   resolution_id=res["id"], rule=rule, members=members, tags=dict(pack["tags"]), draft=zero, cards=cards,
                   positions={iso: dict(v) for iso, v in pack["positions"].items()},
                   sources={iso: list(v) if isinstance(v, list) else [v] for iso, v in (pack.get("sources") or {}).items()},
                   news=list(pack.get("news") or []), events=events, c_yes=params.c_yes, c_no=params.c_no)
    scn._loader = loader
    scn._conn_holder = conn_holder
    return scn


def rebind(scn: Scenario, conn) -> Scenario:
    """Point a cached scenario at a new connection (the server opens one per request)."""
    scn._conn_holder[0] = conn
    return scn

