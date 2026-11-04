"""The rules of The Session (docs/design/solo-campaign.md). `apply(scn, game, action)` returns a new game and what
happened; it never changes the game it was given. A game is plain JSON (lists, dicts, numbers, strings), so it can
be saved to the database or, for a guest, kept in their browser and signed.

How a country votes. On any clause, each delegation has the vote engine's mean position for that clause's
commitments (`Scenario.dist`), plus one fixed draw of its own mood for the whole game (shared within its bloc,
as in the engine), plus what the game has done:
  - sway: goodwill each actor (you, or a rival) has built with it, which pulls it towards that actor's stance on
    the clause (+1 support, -1 oppose);
  - a regional group's endorsement, which pulls its members towards the endorsing actor's stance.
Above `c_yes` it votes yes, below `c_no` no, otherwise it abstains. The debrief lists every one of these pulls.
"""
from __future__ import annotations

import copy
import math
import random

from app.engine.rules import tally
from app.modules.mun.worldmap import REGIONS
from app.modules.sim.campaign import content as K
from app.modules.sim.campaign.scenario import Scenario

VERSION = 1
LENGTHS = {"quick": {"chapters": 1, "turns": 4}, "standard": {"chapters": 3, "turns": 5}, "full": {"chapters": 3, "turns": 6}}
DIFFICULTIES = {"easy": {"rivals": 1, "ap": 1, "step": 0.2}, "standard": {"rivals": 2, "ap": 2, "step": 0.3},
                "hard": {"rivals": 3, "ap": 3, "step": 0.4}}
STANCES = ("firm", "open", "bridge")
VOTES = ("yes", "abstain", "no")

R = {   # every number the balance harness tunes lives here
    "ap": 3, "ap_respect": 7, "start_influence": 6, "income": 2, "endorse_income": 1, "rival_income": 2,
    "start_respect": 3, "respect_max": 10, "trust_max": 3,
    "lobby_step": 0.35, "lobby_step_read": 0.5, "redline_step": 0.1, "sway_cap": 1.2, "redline": -1.5,
    "promise_sway": 0.2, "side_event_cost": 3, "side_event_step": 0.15, "endorse_pull": 0.25, "lean_min": 0.3,
    "favour_trust": 2, "offer_cost": 2, "offer_step": 0.5, "propose_cost": 1, "amend_cost": 1, "strike_cost": 2,
    "draft_max": 10, "sponsors": 3, "signatories_share": 0.2, "sponsor_lean": 0.6, "objective_influence": 3,
    "rival_amendments": 1, "bloc_whip_step": 0.25, "abstain_trust": 1, "abstain_cost": 2,
}


class GameError(Exception):
    """An action the rules don't allow; the message says why, in plain words."""


# ---------------------------------------------------------------- setting up

def _rng(g: dict) -> random.Random:
    g["n"] += 1
    return random.Random(f"{g['seed']}:{g['n']}")


def mandate_for(scn: Scenario, iso3: str) -> dict:
    """Your secret instructions: get your country's two most wanted commitments in, keep its least wanted out. They
    come from your country's stated positions in the scenario, so they're as real (or as invented) as the scenario."""
    pos = scn.positions.get(iso3, {})
    single = {t: scn.dist([t]).get(iso3, (0.0, 1.5))[0] for t in scn.tags}
    order = sorted(scn.tags, key=lambda t: (pos.get(t, 0), single[t], t))
    return {"must": order[-1], "also": order[-2], "red": order[0]}


def _pick_rivals(scn: Scenario, iso3: str, mandate: dict, n: int) -> list[dict]:
    mine = scn.positions.get(iso3, {})
    cands = []
    for m in scn.members:
        if m.iso3 == iso3 or m.iso3 in scn.rule.veto:
            continue
        p = scn.positions.get(m.iso3, {})
        clash = p.get(mandate["red"], 0) - p.get(mandate["must"], 0)
        cands.append((-(clash + (0.5 if m.p5 else 0)), m.iso3))
    out = []
    for _, r in sorted(cands)[:n]:
        p = scn.positions.get(r, {})
        wants = sorted((t for t in scn.tags if mine.get(t, 0) <= 0), key=lambda t: (-p.get(t, 0), t != mandate["red"], t))
        blocks = sorted((t for t in scn.tags if mine.get(t, 0) > 0), key=lambda t: (p.get(t, 0), t != mandate["must"], t))
        want = wants[0] if wants else mandate["red"]
        block = blocks[0] if blocks else mandate["must"]
        if want == block:
            block = mandate["must"] if want != mandate["must"] else mandate["red"]
        out.append({"iso3": r, "want": want, "block": block, "influence": R["start_influence"], "sponsors": [], "signatories": []})
    return out


def _moods(scn: Scenario, seed: int) -> dict:
    """Each delegation's fixed mood for the game, correlated within blocs like the engine's hidden mandates."""
    rng = random.Random(f"{seed}:moods")
    groups: dict[str, float] = {}
    out = {}
    for m in sorted(scn.members, key=lambda m: m.iso3):
        z = rng.gauss(0, 1)
        if m.group:
            g = groups.setdefault(m.group, random.Random(f"{seed}:{m.group}").gauss(0, 1))
            rho = max(0.0, min(0.95, m.rho))
            z = math.sqrt(rho) * g + math.sqrt(1 - rho) * z
        out[m.iso3] = round(z, 4)
    return out


def new_game(scn: Scenario, iso3: str, length: str = "standard", difficulty: str = "standard", path: str = "mandate",
             seed: int = 1) -> dict:
    if not scn.member(iso3):
        raise GameError("Choose a country that sits on this committee.")
    if length not in LENGTHS or difficulty not in DIFFICULTIES or path not in K.PATHS:
        raise GameError("Choose a length, a difficulty and a victory path.")
    mandate = mandate_for(scn, iso3)
    rivals = _pick_rivals(scn, iso3, mandate, DIFFICULTIES[difficulty]["rivals"])
    others = [m.iso3 for m in scn.members]
    g = {
        "v": VERSION, "pack": scn.code, "seed": int(seed), "n": 0, "iso3": iso3, "length": length, "difficulty": difficulty,
        "path": path, "phase": "chapter", "chapter": 1, "turn": 1, "ap": R["ap"],
        "influence": R["start_influence"], "respect": R["start_respect"], "expertise": 0, "xp": 0,
        "mandate": mandate, "rivals": rivals, "moods": _moods(scn, seed),
        "trust": {i: 0 for i in others}, "sway": {"you": {i: 0.0 for i in others}, **{r["iso3"]: {i: 0.0 for i in others} for r in rivals}},
        "draft": [{"id": f"d{i + 1}", "text": c["text"], "tags": list(c["tags"]), "author": "draft", "amended_by": []}
                  for i, c in enumerate(scn.draft)],
        "cards": [c["id"] for c in scn.cards], "struck": [], "next_id": 1,
        "promises": [], "favours": [], "whip": {}, "read": [], "skills": [], "sponsors": [], "signatories": [],
        "endorse": {}, "region_last": {}, "asked": [], "question": None, "event": None, "mods": {},
        "objectives": {}, "tabled_first": None, "summit": None, "result": None,
        "stats": {}, "log": [],
    }
    _start_turn(scn, g)
    return g


# ---------------------------------------------------------------- reading the room

def _others(g: dict) -> set:
    return {g["iso3"], *[r["iso3"] for r in g["rivals"]]}


def stance(scn: Scenario, g: dict, actor: str, clause: dict) -> int:
    """Whether an actor (you or a rival) supports (+1) or opposes (-1) a clause, or doesn't mind (0)."""
    tags = clause["tags"]
    if actor == "you":
        s = g.get("summit") or {}
        if clause["id"] in s.get("my_votes", {}):
            return {"yes": 1, "no": -1, "abstain": 0}[s["my_votes"][clause["id"]]]
        must, red = g["mandate"]["must"], g["mandate"]["red"]
        if red in tags:
            return -1
        if must in tags or g["mandate"].get("also") in tags or clause.get("author") == "you":
            return 1
        mu = scn.dist(tags).get(g["iso3"], (0, 1))[0]
    else:
        rv = next(r for r in g["rivals"] if r["iso3"] == actor)
        if rv["block"] in tags:
            return -1
        if rv["want"] in tags or clause.get("author") == actor:
            return 1
        mu = scn.dist(tags).get(actor, (0, 1))[0]
    return 1 if mu >= 0.4 else -1 if mu <= -0.4 else 0


def latent(scn: Scenario, g: dict, iso: str, clause: dict, stances: dict | None = None, mood: bool = True) -> float:
    mu, sigma = scn.dist(clause["tags"]).get(iso, (0.0, 1.5))
    x = mu + (sigma * g["moods"].get(iso, 0.0) if mood else 0.0)
    stances = stances if stances is not None else {a: stance(scn, g, a, clause) for a in ["you", *[r["iso3"] for r in g["rivals"]]]}
    for actor, s in stances.items():
        x += g["sway"].get(actor, {}).get(iso, 0.0) * s
    owner = g["endorse"].get((scn.member(iso).region if scn.member(iso) else ""))
    if owner:
        x += R["endorse_pull"] * stances.get(owner, 0)
    return x


def vote_of(scn: Scenario, x: float) -> str:
    return "yes" if x > scn.c_yes else "no" if x < scn.c_no else "abstain"


def votes_on(scn: Scenario, g: dict, clause: dict, my_vote: str | None = None, favour_for: set | None = None) -> dict:
    """Every delegation's vote on a clause: yours as cast, rivals' by their stance, the rest from the model."""
    stances = {a: stance(scn, g, a, clause) for a in ["you", *[r["iso3"] for r in g["rivals"]]]}
    if my_vote:
        stances["you"] = {"yes": 1, "no": -1, "abstain": 0}[my_vote]
    out = {}
    for m in scn.members:
        if m.iso3 == g["iso3"]:
            out[m.iso3] = my_vote or ("yes" if stances["you"] > 0 else "no" if stances["you"] < 0 else "abstain")
        elif m.iso3 in stances:
            out[m.iso3] = {1: "yes", -1: "no", 0: "abstain"}[stances[m.iso3]]
        elif favour_for and m.iso3 in favour_for and stances["you"]:
            out[m.iso3] = "yes" if stances["you"] > 0 else "no"
        else:
            out[m.iso3] = vote_of(scn, latent(scn, g, m.iso3, clause, stances))
            if out[m.iso3] == "no" and m.iso3 in g.get("pledges", []) and stances["you"] > 0 and not red_line(scn, m.iso3, clause["tags"]):
                out[m.iso3] = "abstain"
    return out


def red_line(scn: Scenario, iso: str, tags) -> bool:
    """A commitment a country has said it can never accept (-2 in the scenario): no pledge covers it."""
    return any((scn.positions.get(iso, {}).get(t) or 0) <= -2 for t in tags)


def chance(scn: Scenario, g: dict, clause: dict, runs: int = 300) -> dict:
    """The whip dial: how likely a clause is to pass, as you can see it (moods unknown, so they are sampled)."""
    stances = {a: stance(scn, g, a, clause) for a in ["you", *[r["iso3"] for r in g["rivals"]]]}
    rng = random.Random(f"{g['seed']}:dial:{clause['id']}:{g['n']}")
    base = {m.iso3: latent(scn, g, m.iso3, clause, stances, mood=False) for m in scn.members}
    sig = {i: s for i, (_, s) in scn.dist(clause["tags"]).items()}
    passed = 0
    yes_total = 0
    for _ in range(runs):
        votes = {}
        for m in scn.members:
            if m.iso3 == g["iso3"] or any(r["iso3"] == m.iso3 for r in g["rivals"]):
                s = stances["you"] if m.iso3 == g["iso3"] else stances[m.iso3]
                votes[m.iso3] = {1: "yes", -1: "no", 0: "abstain"}[s]
            else:
                votes[m.iso3] = vote_of(scn, base[m.iso3] + sig.get(m.iso3, 1.0) * rng.gauss(0, 1))
        out = tally(scn.rule, votes, len(votes))
        passed += int(out.passed)
        yes_total += out.yes
    return {"p_pass": round(passed / runs, 3), "yes": round(yes_total / runs, 1)}


def lean(scn: Scenario, g: dict, actor: str, iso: str) -> float:
    """How far a delegation leans towards an actor overall: goodwill, trust and shared interests."""
    if actor == "you":
        must, red = g["mandate"]["must"], g["mandate"]["red"]
        extra = 0.15 * g["trust"].get(iso, 0)
    else:
        rv = next(r for r in g["rivals"] if r["iso3"] == actor)
        must, red, extra = rv["want"], rv["block"], 0.0
    agree = (scn.dist([must]).get(iso, (0, 1))[0] - scn.dist([red]).get(iso, (0, 1))[0]) / 4
    return g["sway"][actor].get(iso, 0.0) + extra + 0.4 * agree


def _region_members(scn: Scenario, region: str) -> list[str]:
    return [m.iso3 for m in scn.members if m.region == region]


# ---------------------------------------------------------------- turns

def _log(g: dict, who: str, text: str, kind: str = "info", at: str | None = None) -> None:
    """`at`: the country (or regional group) the line is about, so the board can light it up."""
    e = {"when": _when(g), "who": who, "text": text, "kind": kind}
    if at:
        e["at"] = at
    g["log"].append(e)


def _when(g: dict) -> str:
    if g["phase"] == "summit":
        return "Summit"
    if g["phase"] == "done":
        return "Result"
    return f"Chapter {g['chapter']}, turn {g['turn']}"


def _start_turn(scn: Scenario, g: dict) -> None:
    rng = _rng(g)
    deck = K.EVENTS + scn.events + scn.events       # the scenario's own events come up about as often as the general ones
    ev = rng.choice(deck)
    g["mods"] = {}
    eff = ev["effect"]
    g["ap"] = R["ap"] + (1 if g["respect"] >= R["ap_respect"] else 0) + eff.get("ap", 0)
    g["mods"]["lobby_cost"] = eff.get("lobby_cost", 0)
    if eff.get("influence"):
        g["influence"] += eff["influence"]
    card = {"id": ev["id"], "title": ev["title"], "body": ev["body"], "teaches": ev["teaches"],
            "hypothetical": bool(ev.get("scenario")) and not scn.fictional}   # a scenario's own event on a real issue is labelled
    if eff.get("region_mood"):
        regions = sorted({m.region for m in scn.members if m.region in REGIONS})
        if regions:
            reg = rng.choice(regions)
            actor = g["region_last"].get(reg)
            card["body"] = f"The {REGIONS[reg]} meets. " + (
                ("Your work with it pays off." if actor == "you" else "It warms to a rival's draft.") if actor else "No one has courted it yet.")
            if actor:
                for iso in _region_members(scn, reg):
                    if iso not in _others(g):
                        _sway(g, actor, iso, eff["region_mood"])
    if eff.get("spotlight"):
        # The news turns attention to one commitment: delegations that support it warm to whoever is championing it.
        tag, amount = eff["spotlight"]["tag"], eff["spotlight"]["amount"]
        champions = (["you"] if tag in (g["mandate"]["must"], g["mandate"].get("also")) else []) + \
            [r["iso3"] for r in g["rivals"] if r["want"] == tag]
        for iso in scn.isos:
            if iso not in _others(g) and ((scn.positions.get(iso, {}).get(tag) or 0) >= 1 or scn.dist([tag]).get(iso, (0, 1))[0] >= 0.4):
                for actor in champions:
                    _sway(g, actor, iso, amount)
    if eff.get("question"):
        left = [q for q in K.QUESTIONS if q["id"] not in g["asked"]] or K.QUESTIONS
        q = rng.choice(left)
        g["asked"].append(q["id"])
        g["question"] = q["id"]
        card["body"] = q["ask"]
    g["event"] = card
    _log(g, "news", card["title"], "event")
    rivals_move(scn, g)


def _sway(g: dict, actor: str, iso: str, amount: float) -> float:
    cur = g["sway"][actor].get(iso, 0.0)
    new = max(-R["sway_cap"], min(R["sway_cap"], cur + amount))
    g["sway"][actor][iso] = round(new, 4)
    return new - cur


def _spend(g: dict, ap: int = 0, influence: int = 0) -> None:
    if g["ap"] < ap:
        raise GameError("You're out of action points this turn. End the turn.")
    if g["influence"] < influence:
        raise GameError(f"That needs {influence} Influence; you have {g['influence']}.")
    g["ap"] -= ap
    g["influence"] -= influence


def _clause(g: dict, cid: str) -> dict:
    c = next((c for c in g["draft"] if c["id"] == cid), None)
    if not c:
        raise GameError("That clause isn't in the draft.")
    return c


def _country(scn: Scenario, g: dict, iso: str, allow_rival: bool = False) -> None:
    if not scn.member(iso) or iso == g["iso3"]:
        raise GameError("Choose another delegation on the committee.")
    if not allow_rival and any(r["iso3"] == iso for r in g["rivals"]):
        raise GameError("Rival delegations won't be moved. Work around them.")


def lobby_cost(scn: Scenario, g: dict, iso: str) -> int:
    mu = scn.dist([g["mandate"]["must"]]).get(iso, (0, 1))[0] + g["sway"]["you"].get(iso, 0.0)
    cost = 1 + max(0, min(2, round(-mu)))
    if g["respect"] >= 6:
        cost -= 1
    if g["trust"].get(iso, 0) >= 2:
        cost -= 1
    return max(1, cost + g["mods"].get("lobby_cost", 0))


def bucket(x: float) -> int:
    return 2 if x >= 1.2 else 1 if x >= 0.4 else 0 if x > -0.4 else -1 if x > -1.2 else -2


LINES = {
    2: "We strongly support your position and will say so on the floor.",
    1: "We can support you, though we'd welcome some changes.",
    0: "We are still consulting our capital. We may abstain.",
    -1: "We have serious concerns about where you're taking this text.",
    -2: "We cannot accept this. Our instructions are clear.",
}


# ---------------------------------------------------------------- actions

def apply(scn: Scenario, game: dict, action: dict) -> tuple[dict, dict]:
    g = copy.deepcopy(game)
    do = action.get("do")
    if g["phase"] == "done":
        raise GameError("This session is over. Start a new one.")
    handler = (CHAPTER if g["phase"] == "chapter" else SUMMIT).get(do)
    if not handler:
        raise GameError("That isn't something you can do now.")
    out = handler(scn, g, action) or {}
    g["stats"][do] = g["stats"].get(do, 0) + 1
    return g, out


def a_lobby(scn, g, a):
    iso = a.get("iso3")
    _country(scn, g, iso)
    cost = lobby_cost(scn, g, iso)
    _spend(g, 1, cost)
    must = g["mandate"]["must"]
    mu = scn.dist([must]).get(iso, (0, 1))[0]
    if mu <= R["redline"]:
        moved = _sway(g, "you", iso, R["redline_step"])
        heard = "That is a red line for us. We won't move on it, though we respect your efforts."
    else:
        moved = _sway(g, "you", iso, R["lobby_step_read"] if iso in g["read"] else R["lobby_step"])
        heard = LINES[bucket(mu + g["sway"]["you"][iso])]
    g["region_last"][scn.member(iso).region] = "you"
    _log(g, "you", f"You lobbied {scn.member(iso).name}.", "action", iso)
    return {"heard": heard, "moved": round(moved, 2), "cost": cost, "red_line": mu <= R["redline"]}


def a_read(scn, g, a):
    iso = a.get("iso3")
    _country(scn, g, iso, allow_rival=True)
    if iso in g["read"]:
        raise GameError("You've already read that country file.")
    _spend(g, 1)
    g["read"].append(iso)
    g["expertise"] += 1
    g["xp"] += 1
    _log(g, "you", f"You read the file on {scn.member(iso).name}.", "action", iso)
    return {"file": country_file(scn, g, iso)}


def country_file(scn: Scenario, g: dict, iso: str) -> dict:
    pos = scn.positions.get(iso, {})
    out = {"iso3": iso, "name": scn.member(iso).name, "region": REGIONS.get(scn.member(iso).region, ""), "p5": scn.member(iso).p5,
           "positions": [{"tag": t, "label": scn.tags[t], "position": pos.get(t)} for t in sorted(scn.tags)],
           "red_lines": [scn.tags[t] for t in sorted(scn.tags) if (pos.get(t) or 0) <= -2],
           "sources": scn.sources.get(iso, []), "estimate": True, "fictional": scn.fictional}
    if "read_room" in g["skills"]:
        out["mood"] = "warmer than usual" if g["moods"].get(iso, 0) > 0.3 else "cooler than usual" if g["moods"].get(iso, 0) < -0.3 else "as usual"
    return out


def a_propose(scn, g, a):
    card = next((c for c in scn.cards if c["id"] == a.get("card")), None)
    if not card or card["id"] not in g["cards"]:
        raise GameError("That clause card isn't on the table.")
    if len(g["draft"]) >= R["draft_max"]:
        raise GameError("The draft is full. Strike or merge a clause first.")
    _spend(g, 1, 0 if g["respect"] >= 8 else R["propose_cost"])
    text = (a.get("text") or "").strip()[:400]
    g["cards"].remove(card["id"])
    cid = f"p{g['next_id']}"
    g["next_id"] += 1
    g["draft"].append({"id": cid, "text": text or card["text"], "tags": list(card["tags"]), "author": "you", "amended_by": [],
                       "card": card["id"], "own_words": bool(text)})
    _log(g, "you", "You proposed a clause: " + (text or card["text"]), "action")
    return {"clause": cid}


def room_accepts(scn: Scenario, g: dict, clause: dict, new_tags: list | None) -> bool:
    """A working group only changes text by agreement. Striking a clause works only if it wouldn't pass now;
    amending someone else's clause works only if the new version would win at least as many yes votes."""
    before = votes_on(scn, g, clause)
    if new_tags is None:
        return not tally(scn.rule, before, len(before)).passed
    after = votes_on(scn, g, {**clause, "tags": new_tags})
    return sum(v == "yes" for v in after.values()) >= sum(v == "yes" for v in before.values())


def a_amend(scn, g, a):
    c = _clause(g, a.get("clause"))
    add, remove = a.get("add"), a.get("remove")
    tags = list(c["tags"])
    if add:
        if add not in scn.tags or add in tags:
            raise GameError("Choose a commitment the clause doesn't already make.")
        tags.append(add)
    if remove:
        if remove not in tags:
            raise GameError("The clause doesn't make that commitment.")
        tags.remove(remove)
    if not tags or len(tags) > 3 or tags == c["tags"]:
        raise GameError("A clause makes between one and three commitments.")
    _spend(g, 1, 0 if "friendly" in g["skills"] else R["amend_cost"])
    if c["author"] != "you" and not room_accepts(scn, g, c, tags):
        g["influence"] += 0 if "friendly" in g["skills"] else R["amend_cost"]
        _log(g, "you", "The working group didn't accept your amendment.", "warning")
        return {"accepted": False}
    _break_promises_if_changed(scn, g, c, tags)
    c["tags"] = tags
    if c["author"] != "you" and "you" not in c["amended_by"]:
        c["amended_by"].append("you")
    _log(g, "you", f"You amended a clause: now {', '.join(scn.tags[t].lower() for t in tags)}.", "action")
    return {"accepted": True}


def a_strike(scn, g, a):
    c = _clause(g, a.get("clause"))
    if len(g["draft"]) <= 1:
        raise GameError("The draft needs at least one clause.")
    _spend(g, 1, R["strike_cost"])
    if not room_accepts(scn, g, c, None):
        g["influence"] += R["strike_cost"]
        _log(g, "you", "The working group wants that clause and kept it.", "warning")
        return {"accepted": False}
    fans = sorted((iso for iso in scn.isos if iso not in _others(g) and scn.dist(c["tags"]).get(iso, (0, 1))[0] >= 1.0),
                  key=lambda i: -scn.dist(c["tags"])[i][0])[:3]
    for iso in fans:
        g["trust"][iso] = max(-R["trust_max"], g["trust"][iso] - 1)
    if any(g["trust"].get(i, 0) >= 2 for i in fans):
        g["respect"] = max(0, g["respect"] - 1)
    _break_promises_if_changed(scn, g, c, None)
    g["draft"].remove(c)
    g["struck"].append({**c, "by": "you"})
    _log(g, "you", "You struck a clause from the draft.", "action")
    return {"upset": fans, "accepted": True}


def _break_promises_if_changed(scn, g, clause, new_tags) -> None:
    for p in g["promises"]:
        if p["clause"] == clause["id"] and p["kept"] is None:
            p["kept"] = False
            g["trust"][p["iso3"]] = max(-R["trust_max"], g["trust"][p["iso3"]] - 2)
            g["respect"] = max(0, g["respect"] - 1)
            _log(g, "you", f"You broke your promise to {scn.member(p['iso3']).name}.", "warning")


def a_promise(scn, g, a):
    iso = a.get("iso3")
    _country(scn, g, iso)
    c = _clause(g, a.get("clause"))
    if any(p["iso3"] == iso and p["kept"] is None for p in g["promises"]):
        raise GameError("You already have a promise open with that delegation.")
    if scn.dist(c["tags"]).get(iso, (0, 1))[0] < 0.4:
        raise GameError("They don't want that clause, so a promise to back it means nothing to them.")
    g["promises"].append({"iso3": iso, "clause": c["id"], "kept": None})
    g["trust"][iso] = min(R["trust_max"], g["trust"][iso] + 1)
    _sway(g, "you", iso, R["promise_sway"] * (2 if "back_channel" in g["skills"] else 1))
    _log(g, "you", f"You promised {scn.member(iso).name} to back a clause.", "action", iso)
    return {}


def a_side_event(scn, g, a):
    reg = a.get("region")
    members = [i for i in _region_members(scn, reg) if i not in _others(g)]
    if reg not in REGIONS or not members:
        raise GameError("Choose a regional group with delegations on this committee.")
    _spend(g, 2, R["side_event_cost"])
    for iso in members:
        _sway(g, "you", iso, R["side_event_step"])
    g["region_last"][reg] = "you"
    _log(g, "you", f"You hosted a side event for the {REGIONS[reg]}.", "action", reg)
    return {"reached": members}


def a_favour(scn, g, a):
    iso = a.get("iso3")
    _country(scn, g, iso)
    if g["trust"].get(iso, 0) < R["favour_trust"]:
        raise GameError("They don't trust you enough yet. Keep your promises first.")
    _spend(g, 1)
    g["favours"].append(iso)
    g["trust"][iso] = 0
    _log(g, "you", f"{scn.member(iso).name} owes you a favour at the summit.", "action")
    return {}


def a_whip(scn, g, a):
    iso = a.get("iso3")
    _country(scn, g, iso)
    if a.get("vote") not in VOTES:
        raise GameError("Predict yes, no or abstain.")
    _spend(g, 1)
    g["whip"][iso] = a["vote"]
    _log(g, "you", f"You predicted {scn.member(iso).name} will vote {a['vote']} on the final resolution.", "action")
    return {}


def _signers_needed(scn: Scenario) -> int:
    return max(2, math.ceil(len(scn.members) * R["signatories_share"]))


def a_sign(scn, g, a):
    if not (g["chapter"] == LENGTHS[g["length"]]["chapters"]):
        raise GameError("Sponsors and signatories are gathered in the last chapter.")
    iso, role = a.get("iso3"), a.get("role")
    _country(scn, g, iso)
    if role not in ("sponsor", "signatory") or iso in g["sponsors"] or iso in g["signatories"]:
        raise GameError("Ask a delegation that hasn't signed yet to be a sponsor or a signatory.")
    ln = lean(scn, g, "you", iso)
    if role == "sponsor" and ln < R["sponsor_lean"] and g["trust"].get(iso, 0) < 2:
        raise GameError("They won't sponsor a draft they don't back. Ask them to be a signatory instead.")
    if role == "signatory" and ln < 0:
        raise GameError("They don't want this draft debated at all.")
    _spend(g, 1)
    g["sponsors" if role == "sponsor" else "signatories"].append(iso)
    _log(g, "you", f"{scn.member(iso).name} signed as a {role}.", "action", iso)
    return {}


def a_answer(scn, g, a):
    q = next((q for q in K.QUESTIONS if q["id"] == g.get("question")), None)
    if not q:
        raise GameError("There's no procedure question to answer.")
    right = a.get("option") == q["answer"]
    g["question"] = None
    if right:
        g["expertise"] += 1
        g["xp"] += 1
        g["respect"] = min(R["respect_max"], g["respect"] + 1)
    else:
        g["respect"] = max(0, g["respect"] - 1)
    _log(g, "you", ("Right: " if right else "Not quite: ") + q["why"], "learn")
    return {"right": right, "why": q["why"], "answer": q["options"][q["answer"]]}


def a_skill(scn, g, a):
    s = K.SKILLS.get(a.get("skill"))
    if not s or a["skill"] in g["skills"]:
        raise GameError("Choose a skill you don't have yet.")
    if s["needs"] and s["needs"] not in g["skills"]:
        raise GameError(f"Unlock {K.SKILLS[s['needs']]['name']} first.")
    if g["xp"] < K.SKILL_COST:
        raise GameError(f"A skill needs {K.SKILL_COST} Expertise; you have {g['xp']} to spend.")
    g["xp"] -= K.SKILL_COST
    g["skills"].append(a["skill"])
    _log(g, "you", f"You unlocked {s['name']}.", "learn")
    return {}


def a_divide(scn, g, a):
    if "division" not in g["skills"]:
        raise GameError("Unlock Division of the question first.")
    c = _clause(g, a.get("clause"))
    if len(c["tags"]) < 2 or len(g["draft"]) >= R["draft_max"]:
        raise GameError("Only a clause with two or more commitments can be divided, and the draft must have room.")
    _spend(g, 1)
    first, rest = c["tags"][:1], c["tags"][1:]
    c["tags"] = first
    cid = f"p{g['next_id']}"
    g["next_id"] += 1
    g["draft"].insert(g["draft"].index(c) + 1, {"id": cid, "text": c["text"] + " (second part)", "tags": rest,
                                                "author": c["author"], "amended_by": list(set(c["amended_by"]) | {"you"})})
    if c["author"] != "you" and "you" not in c["amended_by"]:
        c["amended_by"].append("you")
    _log(g, "you", "You divided a clause in two.", "action")
    return {"clause": cid}


def a_merge(scn, g, a):
    if "merge" not in g["skills"]:
        raise GameError("Unlock Merge first.")
    c1, c2 = _clause(g, a.get("a")), _clause(g, a.get("b"))
    tags = list(dict.fromkeys(c1["tags"] + c2["tags"]))
    if c1 is c2 or len(tags) > 3:
        raise GameError("Merge two different clauses with three commitments or fewer between them.")
    _spend(g, 1)
    _break_promises_if_changed(scn, g, c2, None)
    c1["tags"], c1["text"] = tags, c1["text"].rstrip(";.") + "; and " + c2["text"]
    c1["author"] = "you" if c1["author"] == "you" or c2["author"] == "you" else c1["author"]
    if c1["author"] != "you" and "you" not in c1["amended_by"]:
        c1["amended_by"].append("you")
    g["draft"].remove(c2)
    _log(g, "you", "You merged two clauses.", "action")
    return {}


def a_bloc_whip(scn, g, a):
    if "bloc_whip" not in g["skills"]:
        raise GameError("Unlock Bloc whip first.")
    grp = a.get("group")
    members = [m.iso3 for m in scn.members if m.group == grp and m.iso3 not in _others(g)]
    if not grp or not members:
        raise GameError("Choose a bloc with delegations on this committee.")
    _spend(g, 2, 2 + len(members) // 3)
    for iso in members:
        if scn.dist([g["mandate"]["must"]]).get(iso, (0, 1))[0] > R["redline"]:
            _sway(g, "you", iso, R["bloc_whip_step"])
    _log(g, "you", f"You whipped the {grp} bloc.", "action")
    return {"reached": members}


def a_abstain(scn, g, a):
    """Ask a permanent member to abstain rather than veto: in real Councils this is how texts survive a member's
    doubts. It costs the trust you've built with that delegation, and it never covers its red lines."""
    iso = a.get("iso3")
    _country(scn, g, iso)
    if iso not in scn.rule.veto:
        raise GameError("Only a permanent member of the Security Council can veto, so only they can pledge to abstain.")
    if iso in g.setdefault("pledges", []):
        raise GameError("They've already pledged to abstain.")
    if g["trust"].get(iso, 0) < R["abstain_trust"]:
        raise GameError("They don't trust you enough to make that pledge. Build trust first: keep a promise to them.")
    _spend(g, 1, R["abstain_cost"])
    g["trust"][iso] -= 2
    g["pledges"].append(iso)
    _log(g, "you", f"{scn.member(iso).name} pledged to abstain rather than veto, except on its red lines.", "action")
    return {}


def a_end_turn(scn, g, a):
    if g.get("question"):
        g["question"] = None          # an unanswered procedure moment simply passes
    _upkeep(scn, g)
    return {}


# ---------------------------------------------------------------- rivals

def _rival_spend(rv: dict, cost: int) -> bool:
    if rv["influence"] < cost:
        return False
    rv["influence"] -= cost
    return True


def rivals_move(scn: Scenario, g: dict) -> None:
    d = DIFFICULTIES[g["difficulty"]]
    last = g["chapter"] == LENGTHS[g["length"]]["chapters"]
    for rv in g["rivals"]:
        name = scn.member(rv["iso3"]).name
        tried: set = set()
        for _ in range(d["ap"]):
            want_in = any(rv["want"] in c["tags"] for c in g["draft"])
            blocked = [c for c in g["draft"] if rv["block"] in c["tags"]]
            if not want_in:
                card = next((c for c in scn.cards if c["id"] in g["cards"] and rv["want"] in c["tags"] and rv["block"] not in c["tags"]), None)
                if card and len(g["draft"]) < R["draft_max"] and _rival_spend(rv, 1):
                    g["cards"].remove(card["id"])
                    cid = f"p{g['next_id']}"
                    g["next_id"] += 1
                    g["draft"].append({"id": cid, "text": card["text"], "tags": list(card["tags"]), "author": rv["iso3"], "amended_by": [], "card": card["id"]})
                    _log(g, rv["iso3"], f"{name} proposed a clause: {card['text']}", "rival")
                    continue
            blocked = [c for c in blocked if c["id"] not in tried]
            if blocked:
                c = blocked[0]
                tried.add(c["id"])
                new = [t for t in c["tags"] if t != rv["block"]]
                if len(c["tags"]) > 1 and _rival_spend(rv, 1):
                    if c["author"] != rv["iso3"] and not room_accepts(scn, g, c, new):
                        _log(g, rv["iso3"], f"{name} tried to amend a clause; the working group refused.", "rival")
                        continue
                    c["tags"] = new
                    c["amended_by"].append(rv["iso3"])
                    _log(g, rv["iso3"], f"{name} amended a clause to drop {scn.tags[rv['block']].lower()}.", "rival")
                    continue
                if len(c["tags"]) == 1 and len(g["draft"]) > 1 and _rival_spend(rv, 2):
                    if not room_accepts(scn, g, c, None):
                        _log(g, rv["iso3"], f"{name} moved to strike a clause; the working group kept it.", "rival")
                        continue
                    g["draft"].remove(c)
                    g["struck"].append({**c, "by": rv["iso3"]})
                    for p in g["promises"]:
                        if p["clause"] == c["id"] and p["kept"] is None:
                            p["kept"] = "void"
                    _log(g, rv["iso3"], f"{name} struck a clause from the draft.", "rival")
                    continue
            if last and (len(rv["sponsors"]) < R["sponsors"] or len(rv["signatories"]) + len(rv["sponsors"]) < _signers_needed(scn)):
                taken = set(g["sponsors"]) | set(g["signatories"]) | set(rv["sponsors"]) | set(rv["signatories"])
                pool = sorted((i for i in scn.isos if i not in _others(g) and i not in taken), key=lambda i: -lean(scn, g, rv["iso3"], i))
                if pool:
                    who = pool[0]
                    role = "sponsor" if len(rv["sponsors"]) < R["sponsors"] and lean(scn, g, rv["iso3"], who) >= R["sponsor_lean"] else "signatory"
                    if lean(scn, g, rv["iso3"], who) >= 0:
                        rv["sponsors" if role == "sponsor" else "signatories"].append(who)
                        _log(g, rv["iso3"], f"{scn.member(who).name} signed {name}'s draft as a {role}.", "rival", who)
                        continue
            # lobby the delegation where its goodwill matters most: closest to the middle, in a group it could win
            targets = []
            for iso in scn.isos:
                if iso in _others(g) or scn.dist([rv["want"]]).get(iso, (0, 1))[0] <= R["redline"]:
                    continue
                ln = lean(scn, g, rv["iso3"], iso)
                if g["sway"][rv["iso3"]][iso] >= R["sway_cap"]:
                    continue
                targets.append((abs(ln - 0.35), iso))
            if targets and _rival_spend(rv, 1):
                iso = sorted(targets)[0][1]
                _sway(g, rv["iso3"], iso, d["step"])
                g["region_last"][scn.member(iso).region] = rv["iso3"]
                _log(g, rv["iso3"], f"{name} lobbied {scn.member(iso).name}.", "rival", iso)


# ---------------------------------------------------------------- upkeep and chapters

def _endorsements(scn: Scenario, g: dict) -> None:
    actors = ["you", *[r["iso3"] for r in g["rivals"]]]
    for reg in sorted({m.region for m in scn.members if m.region in REGIONS}):
        voters = [i for i in _region_members(scn, reg) if i not in _others(g)]
        if len(voters) < 2:
            continue
        counts = {a: sum(1 for i in voters if lean(scn, g, a, i) > R["lean_min"] and
                         all(lean(scn, g, a, i) >= lean(scn, g, b, i) for b in actors if b != a)) for a in actors}
        best = max(actors, key=lambda a: (counts[a], a == "you"))
        owner = best if counts[best] * 2 > len(voters) else None
        if g["endorse"].get(reg) != owner:
            who = "you" if owner == "you" else (scn.member(owner).name if owner else None)
            _log(g, owner or "news", f"The {REGIONS[reg]} now endorses " + ("your draft." if owner == "you" else f"{who}'s draft." if owner else "no one."),
                 "endorse")
            if owner:
                g["endorse"][reg] = owner
            else:
                g["endorse"].pop(reg, None)


def _objective(scn: Scenario, g: dict) -> bool:
    ch, last = g["chapter"], g["chapter"] == LENGTHS[g["length"]]["chapters"]
    drafted = len(g["draft"]) >= 4 and any(c["author"] == "you" for c in g["draft"])
    endorsed = "you" in g["endorse"].values()
    tabled = len(g["sponsors"]) >= R["sponsors"] and len(g["sponsors"]) + len(g["signatories"]) >= _signers_needed(scn)
    if g["length"] == "quick":
        return drafted and tabled
    return {1: drafted, 2: endorsed, 3: tabled}[ch] if not (last and ch != 3) else tabled


def _upkeep(scn: Scenario, g: dict) -> None:
    _endorsements(scn, g)
    mine = sum(1 for v in g["endorse"].values() if v == "you")
    g["influence"] += R["income"] + mine * R["endorse_income"]
    for rv in g["rivals"]:
        rv["influence"] += R["rival_income"] + sum(1 for v in g["endorse"].values() if v == rv["iso3"]) * R["endorse_income"]
    L = LENGTHS[g["length"]]
    if g["turn"] < L["turns"]:
        g["turn"] += 1
        _start_turn(scn, g)
        return
    met = _objective(scn, g)
    g["objectives"][str(g["chapter"])] = met
    if met:
        g["influence"] += R["objective_influence"]
        g["respect"] = min(R["respect_max"], g["respect"] + 1)
    _log(g, "you", f"Chapter {g['chapter']} " + ("goal met." if met else "goal missed."), "objective")
    if g["chapter"] < L["chapters"]:
        g["chapter"] += 1
        g["turn"] = 1
        _start_turn(scn, g)
        return
    g["tabled_first"] = bool(met) if g["length"] == "quick" or g["chapter"] == 3 else None
    _open_summit(scn, g)


# ---------------------------------------------------------------- the summit

def _open_summit(scn: Scenario, g: dict) -> None:
    g["phase"] = "summit"
    g["ap"] = 0
    g["event"] = None
    g["question"] = None
    if g["tabled_first"] is False:
        g["respect"] = max(0, g["respect"] - 1)
    g["summit"] = {"step": "speech", "queue": [c["id"] for c in g["draft"]], "i": 0, "my_votes": {}, "results": [],
                   "amendments_left": R["rival_amendments"] * len(g["rivals"]) + (1 if g["tabled_first"] is False else 0),
                   "po_used": False, "pending": None, "final": None}
    _log(g, "news", "The summit opens. The draft is put to the vote clause by clause.", "event")


def _pending(scn: Scenario, g: dict) -> None:
    s = g["summit"]
    s["pending"] = None
    if s["i"] >= len(s["queue"]) or s["amendments_left"] <= 0:
        return
    c = _clause(g, s["queue"][s["i"]])
    for rv in g["rivals"]:
        if rv["block"] in c["tags"] and len(c["tags"]) > 1:
            s["pending"] = {"by": rv["iso3"], "remove": rv["block"], "tags": [t for t in c["tags"] if t != rv["block"]]}
            return
        if rv["want"] not in c["tags"] and rv["block"] not in c["tags"] and len(c["tags"]) < 3 and \
                not any(rv["want"] in x["tags"] for x in g["draft"]):
            s["pending"] = {"by": rv["iso3"], "add": rv["want"], "tags": c["tags"] + [rv["want"]]}
            return


def s_speech(scn, g, a):
    s = g["summit"]
    if s["step"] != "speech":
        raise GameError("The opening speeches are over.")
    st = a.get("stance")
    if st not in STANCES:
        raise GameError("Choose a stance: firm, open or bridge.")
    must = g["mandate"]["must"]
    for iso in scn.isos:
        if iso in _others(g):
            continue
        mu = scn.dist([must]).get(iso, (0, 1))[0]
        if st == "firm":
            _sway(g, "you", iso, 0.15 if mu >= 0.4 else -0.05 if mu <= -0.4 else 0)
        elif st == "bridge" and abs(mu) < 0.4:
            _sway(g, "you", iso, 0.15)
    if st == "open":
        g["respect"] = min(R["respect_max"], g["respect"] + 1)
    s["step"] = "clause"
    s["speech"] = st
    _pending(scn, g)
    _log(g, "you", f"You gave a {st} opening speech.", "action")
    return {}


def s_decide(scn, g, a):
    s = g["summit"]
    if s["step"] != "clause":
        raise GameError("There's no clause before the committee.")
    choice, my_vote = a.get("choice", "stand"), a.get("vote")
    if my_vote not in VOTES:
        raise GameError("Cast your vote on the clause: yes, no or abstain.")
    c = _clause(g, s["queue"][s["i"]])
    out = {"clause": c["id"]}
    p = s["pending"]
    if choice == "point_of_order":
        if "point_of_order" not in g["skills"] or s["po_used"] or not p:
            raise GameError("A point of order needs the skill, a floor amendment to rule out, and can be used once.")
        s["po_used"] = True
        out["amendment"] = "ruled out of order"
        p = None
    elif choice == "accept":
        if not p:
            raise GameError("There's no floor amendment to accept.")
        c["tags"] = p["tags"]
        c["amended_by"].append(p["by"])
        g["respect"] = min(R["respect_max"], g["respect"] + 1)
        out["amendment"] = "accepted as friendly"
        p = None
    elif choice == "offer":
        _spend(g, 0, R["offer_cost"])
        want = {"yes": 1, "no": -1, "abstain": 0}[my_vote]
        if want:
            st = {x: stance(scn, g, x, c) for x in ["you", *[r["iso3"] for r in g["rivals"]]]}
            st["you"] = want
            cands = [(abs(latent(scn, g, i, c, st) - (scn.c_yes if want > 0 else scn.c_no)), i) for i in scn.isos
                     if i not in _others(g) and vote_of(scn, latent(scn, g, i, c, st)) != ("yes" if want > 0 else "no")]
            if cands:
                iso = sorted(cands)[0][1]
                _sway(g, "you", iso, R["offer_step"])
                out["offer"] = iso
    elif choice not in ("stand", "favour"):
        raise GameError("Choose what to do: stand firm, make a last offer, call in a favour, accept or rule out an amendment.")
    if p:   # an unfriendly floor amendment is voted on first
        trial = {**c, "tags": p["tags"]}
        st_votes = votes_on(scn, g, trial, my_vote="no")
        res = tally(scn.rule, st_votes, len(st_votes))
        s["amendments_left"] -= 1
        if res.passed:
            c["tags"] = p["tags"]
            c["amended_by"].append(p["by"])
        out["amendment"] = "adopted" if res.passed else "rejected"
        _log(g, p["by"], f"{scn.member(p['by']).name}'s floor amendment was {out['amendment']}.", "rival")
    favour = set()
    if choice == "favour":
        if not g["favours"]:
            raise GameError("No one owes you a favour.")
        favour = {g["favours"].pop(0)}
    s["my_votes"][c["id"]] = my_vote
    votes = votes_on(scn, g, c, my_vote=my_vote, favour_for=favour)
    res = tally(scn.rule, votes, len(votes))
    for pr in g["promises"]:
        if pr["clause"] == c["id"] and pr["kept"] is None:
            pr["kept"] = my_vote == "yes"
            if pr["kept"]:
                g["respect"] = min(R["respect_max"], g["respect"] + 1)
            else:
                g["trust"][pr["iso3"]] = max(-R["trust_max"], g["trust"][pr["iso3"]] - 2)
                g["respect"] = max(0, g["respect"] - 1)
    s["results"].append({"clause": c["id"], "tags": list(c["tags"]), "passed": res.passed, "yes": res.yes, "no": res.no,
                         "abstain": res.abstain, "votes": votes, "summary": res.summary})
    _log(g, "news", f"Clause {s['i'] + 1} " + ("adopted" if res.passed else "rejected") + f": {res.summary}.", "vote")
    out.update({"passed": res.passed, "summary": res.summary, "votes": votes})
    s["i"] += 1
    if s["i"] >= len(s["queue"]):
        s["step"] = "final"
        s["pending"] = None
    else:
        _pending(scn, g)
    return out


def s_final(scn, g, a):
    s = g["summit"]
    if s["step"] != "final":
        raise GameError("Vote on every clause first.")
    my_vote = a.get("vote")
    if my_vote not in VOTES:
        raise GameError("Cast your vote on the resolution: yes, no or abstain.")
    kept = [r for r in s["results"] if r["passed"]]
    tags = list(dict.fromkeys(t for r in kept for t in r["tags"]))
    final = {"id": "final", "tags": tags, "author": "draft"}
    if tags:
        votes = votes_on(scn, g, final, my_vote=my_vote, favour_for=set(g["favours"]))
        res = tally(scn.rule, votes, len(votes))
        passed, summary, counts = res.passed, res.summary, {"yes": res.yes, "no": res.no, "abstain": res.abstain}
    else:
        votes, passed, summary, counts = {}, False, "No clauses were adopted, so there is no resolution to vote on.", {"yes": 0, "no": 0, "abstain": 0}
    s["final"] = {"tags": tags, "votes": votes, "passed": passed, "summary": summary, **counts, "my_vote": my_vote}
    _log(g, "news", ("The resolution is adopted. " if passed else "The resolution fails. ") + summary, "vote")
    if not passed and scn.rule.veto:
        s["step"] = "statement"
        s["statement_options"] = list(dict.fromkeys(t for r in s["results"] for t in r["tags"])) or list(scn.tags)
        _log(g, "news", "The resolution has failed. The President of the Council proposes a statement instead, "
                        "agreed by consensus: it is not binding, but it is the Council's voice.", "event")
        return {"final": s["final"], "statement": True}
    g["phase"] = "done"
    g["result"] = score(scn, g)
    return {"final": s["final"], "result": g["result"]}


def s_statement(scn, g, a):
    """A Presidential Statement: no vote, adopted only if no member objects (consensus). Weaker than a resolution,
    so it earns at most silver."""
    s = g["summit"]
    if s["step"] != "statement":
        raise GameError("A Presidential Statement comes only after a resolution fails in the Council.")
    tags = [t for t in (a.get("tags") or []) if t in s["statement_options"]]
    if a.get("skip") or not tags:
        s["statement"] = {"tags": [], "adopted": False, "objectors": []}
    else:
        votes = votes_on(scn, g, {"id": "statement", "tags": tags, "author": "you"}, my_vote="yes")
        objectors = sorted(i for i, v in votes.items() if v == "no")
        s["statement"] = {"tags": tags, "adopted": not objectors, "objectors": objectors}
        _log(g, "news", "The Presidential Statement is " + ("agreed by consensus." if not objectors else
             "blocked: " + ", ".join(scn.member(i).name for i in objectors) + " objected."), "vote")
    g["phase"] = "done"
    g["result"] = score(scn, g)
    return {"statement": s["statement"], "result": g["result"]}


# ---------------------------------------------------------------- scoring

def score(scn: Scenario, g: dict) -> dict:
    s, f = g["summit"], g["summit"]["final"]
    must, red = g["mandate"]["must"], g["mandate"]["red"]
    passed, tags = f["passed"], f["tags"]
    also = g["mandate"].get("also")
    got = [must in tags, also in tags, red not in tags]
    mandate = 3 if passed and all(got) else 2 if passed and got[0] and (got[1] or got[2]) else \
        1 if (passed and (got[0] or got[2])) or (not passed and red in tags) else 0
    share = f["yes"] / max(1, len(scn.members))
    mine_regions = sum(1 for v in g["endorse"].values() if v == "you")
    consensus = 0 if not passed else 3 if share >= 0.75 and mine_regions >= 2 else 2 if share >= 0.65 and mine_regions >= 1 else 1
    kept = [r["clause"] for r in s["results"] if r["passed"]]
    clauses = {c["id"]: c for c in g["draft"]}
    credit = [1.0 if clauses[c]["author"] == "you" else 0.5 if "you" in clauses[c]["amended_by"] else 0.0 for c in kept if c in clauses]
    own = sum(credit) / len(credit) if credit else 0.0
    own_kept = sum(1 for x in credit if x == 1.0)
    architect = 0 if not passed else 3 if own >= 0.65 and own_kept >= 3 and share >= 0.65 else \
        2 if own >= 0.5 and own_kept >= 2 else 1 if own >= 0.25 else 0
    st = s.get("statement") or {}
    if not passed and st.get("adopted"):
        sg = [must in st["tags"], also in st["tags"], red not in st["tags"]]
        mandate = max(mandate, 2 if sg[0] and sg[2] else 1 if sg[0] or sg[2] else 0)
        consensus = max(consensus, 2 if mine_regions >= 1 else 1)
        mine_tags = {t for c in g["draft"] if c["author"] == "you" for t in c["tags"]}
        architect = max(architect, 1 if mine_tags & set(st["tags"]) else 0)
    judged = [(iso, v) for iso, v in g["whip"].items() if iso in f["votes"]]
    right = sum(1 for iso, v in judged if f["votes"][iso] == v)
    acc = right / len(judged) if judged else 0.0
    need = min(5, max(3, len(scn.members) // 4))
    broken = sum(1 for p in g["promises"] if p["kept"] is False)
    kingmaker = 0 if len(judged) < need else 3 if acc >= 0.8 and broken == 0 and g["respect"] >= 7 else \
        2 if acc >= 0.65 and broken <= 1 and g["respect"] >= 5 else 1 if acc >= 0.5 else 0
    paths = {"mandate": mandate, "consensus": consensus, "architect": architect, "kingmaker": kingmaker}
    return {"passed": passed, "statement": bool(st.get("adopted")), "paths": paths, "chosen": g["path"], "grade": paths[g["path"]],
            "share_yes": round(share, 3), "own_text": round(own, 3), "whip_right": right, "whip_judged": len(judged),
            "broken_promises": broken, "kept_promises": sum(1 for p in g["promises"] if p["kept"] is True),
            "endorsements": mine_regions, "respect": g["respect"], "expertise": g["expertise"]}


GRADES = {0: "No medal", 1: "Bronze", 2: "Silver", 3: "Gold"}

CHAPTER = {"lobby": a_lobby, "read": a_read, "propose": a_propose, "amend": a_amend, "strike": a_strike, "promise": a_promise,
           "side_event": a_side_event, "favour": a_favour, "whip": a_whip, "sign": a_sign, "answer": a_answer, "skill": a_skill,
           "divide": a_divide, "merge": a_merge, "bloc_whip": a_bloc_whip, "abstain": a_abstain, "end_turn": a_end_turn}
SUMMIT = {"speech": s_speech, "decide": s_decide, "final": s_final, "statement": s_statement, "skill": a_skill}
