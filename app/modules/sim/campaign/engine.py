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
from app.modules.sim.campaign import econ as X
from app.modules.sim.campaign.scenario import Scenario

VERSION = 1
LENGTHS = {"quick": {"chapters": 1, "turns": 5, "deadlines": [5]}, "standard": {"chapters": 3, "turns": 6, "deadlines": [6, 5, 4]},
           "full": {"chapters": 3, "turns": 7, "deadlines": [7, 6, 5]}}   # each stage's deadline: negotiating time runs out
DIFFICULTIES = {"easy": {"rivals": 1, "ap": 1, "step": 0.2}, "standard": {"rivals": 2, "ap": 2, "step": 0.3},
                "hard": {"rivals": 3, "ap": 3, "step": 0.4}}
STANCES = ("firm", "open", "bridge")
VOTES = ("yes", "abstain", "no")

R = {   # every number the balance harness tunes lives here
    "ap": 3, "ap_respect": 7, "start_influence": 6, "income": 1, "endorse_income": 1, "rival_income": 2,
    "start_respect": 4, "respect_max": 10, "trust_max": 3,
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


# Phase 8: rivals that plan, your staff, counter-moves and the golden rule.
R.update({"hire_cost": 4, "staff_max": 5, "secure_cost": 2, "secure_max": 3, "poach_cost": 2, "poach_step": 0.15,
          "reply_respect": 5, "attack": 0.12, "golden_respect": 2, "architect_gold": 0.45})
# Phase 9: the deal table and your capital.
R.update({"capital_start": 6, "capital_max": 10, "deal_funding": 2, "deal_influence": 3, "candidacy_max": 2, "deal_ap": 2})
# Phase 11: stages with breakthroughs, a growing delegation.
R.update({"ap_base": 2, "overtime": [3, 4, 5], "attend_cost": 1, "attend_step": 0.15, "momentum_influence": 2,
          "momentum_respect": 1, "late_respect": 1})
# Phase 12: pitches (lobbying is a choice of two arguments).
R.update({"pitch_step": 0.55})
PLAN = {"easy": {"noise": 0.4, "react": False, "poach": False},       # how rivals choose: easy ones blunder,
        "standard": {"noise": 0.0, "react": False, "poach": True},   # standard ones play the best move,
        "hard": {"noise": 0.0, "react": True, "poach": True}}        # hard ones also answer your last turn
PROMOTE = {2: 2, 3: 5}                     # experience for a second and a third star (faster since 8 Nov)
R["talk_fade"] = 0.93                       # goodwill from talking fades a little each turn; deals, promises and commitments hold
MIN_STAGE_TURNS = 2                         # no breakthrough on a stage's first turn; otherwise move on when you're ready (9 Nov)
ENGAGE = ("talk", "lobby", "deal", "promise", "sign", "abstain", "compromise", "read")   # moves that engage a delegation
ACCURACY = {1: 0.7, 2: 0.85, 3: 1.0}       # how often a report is right, by stars


def start_staff(scn: Scenario, iso3: str, seed: int) -> list[dict]:
    """Big delegations bring more advisers, but greener ones: a permanent member four juniors, a G20 member three, any
    other delegation two seniors. Every mission starts with four stars in all."""
    m = scn.member(iso3)
    stars = [1, 1, 1, 1] if m.p5 else [1, 1, 2] if m.major else [2, 2]
    kinds = ["analyst", "regional", "legal", "analyst"]
    names = list(K.STAFF_NAMES)
    random.Random(f"{seed}:staff").shuffle(names)
    return [_adviser(kinds[i], names[i], s, m.region, i + 1) for i, s in enumerate(stars)]


def _adviser(kind: str, name: str, stars: int, region: str, n: int) -> dict:
    return {"id": f"a{n}", "name": name, "kind": kind, "stars": stars, "xp": 0, "post": None, "since": 0,
            "region": region if kind == "regional" else None, "report": None, "claim": None}


def new_game(scn: Scenario, iso3: str, length: str = "standard", difficulty: str = "standard", path: str = "mandate",
             seed: int = 1, approach: str = "diplomat") -> dict:
    if not scn.member(iso3):
        raise GameError("Choose a country that sits on this committee.")
    if length not in LENGTHS or difficulty not in DIFFICULTIES or path not in K.PATHS:
        raise GameError("Choose a length, a difficulty and a victory path.")
    if approach not in K.APPROACHES:
        raise GameError("Choose an approach.")
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
        "stats": {}, "log": [], "history": [], "drift": {}, "offers": [], "crisis": None, "deals": 0,
        "staff": start_staff(scn, iso3, seed), "secured": [], "reserve": 0, "intent": {}, "tick": 0, "touched": [],
        "last_touched": [], "moved": {}, "countered": [], "proj_prev": {}, "golden": None,
        "capital": R["capital_start"], "dealt": [], "deal_votes": {}, "pledged": 0, "candidacies": [], "recall": 0,
    }
    styles = list(K.RIVAL_STYLES)
    random.Random(f"{seed}:styles").shuffle(styles)
    for i, rv in enumerate(g["rivals"]):
        rv["style"] = styles[i % len(styles)]
    _open_chapter(scn, g)
    _start_turn(scn, g)
    g["approach"] = approach
    if approach == "veteran" and g["staff"]:
        g["staff"][0]["stars"] = 2                           # a senior adviser from the start
    sync_skills(g)
    return g


# ---------------------------------------------------------------- shifting delegations (phase 7)

def drift(g: dict, iso: str, tags) -> float:
    """How far a delegation's position on these commitments has shifted during the session (averaged)."""
    d = g.get("drift", {}).get(iso, {})
    tags = list(tags)
    return sum(d.get(t, 0.0) for t in tags) / len(tags) if tags else 0.0


def shift(scn: Scenario, g: dict, iso: str, tag: str, amount: float, why: str) -> None:
    cur = g.setdefault("drift", {}).setdefault(iso, {}).get(tag, 0.0)
    g["drift"][iso][tag] = round(max(-1.5, min(1.5, cur + amount)), 3)
    word = "warmer towards" if amount > 0 else "cooler towards"
    _log(g, "news", f"{why}: {scn.member(iso).name} is now {word} any clause that {_lc(scn.tags[tag])}.", "shift", iso)


def _lc(label: str) -> str:
    """A commitment label inside a sentence: "Sets up a panel" reads "sets up a panel" (but "UN" stays "UN")."""
    return label[:1].lower() + label[1:] if label[1:2].islower() else label


def mu_of(scn: Scenario, g: dict, iso: str, tags) -> float:
    return scn.dist(tags).get(iso, (0.0, 1.5))[0] + drift(g, iso, tags)


# ---------------------------------------------------------------- chapter crises (phase 7)

def turns_now(g: dict) -> int:
    """The turns in the current chapter: one fewer when the deadline has been brought forward."""
    L = LENGTHS[g["length"]]
    dl = L.get("deadlines") or [L["turns"]]
    t = dl[min(g["chapter"], len(dl)) - 1]
    c = g.get("crisis") or {}
    return t - 1 if c.get("id") == "deadline" and c.get("chapter") == g["chapter"] else t


def _open_chapter(scn: Scenario, g: dict) -> None:
    """Each chapter opens with a crisis card, and a capital or two sends new instructions."""
    g["dealt"] = []
    g["endorse_start"] = [r for r, v in g.get("endorse", {}).items() if v == "you"]   # Bloc meetings need a new endorsement
    rng = _rng(g)
    free = [i for i in scn.isos if i not in _others(g)]
    c = dict(rng.choice(K.CRISES))
    fill = {}
    if c["id"] == "new_government" and free:
        iso = rng.choice(free)
        tag = max(scn.tags, key=lambda t: (abs(scn.positions.get(iso, {}).get(t) or 0), t))
        pos = scn.positions.get(iso, {}).get(tag) or 0
        fill = {"country": scn.member(iso).name, "tag": _lc(scn.tags[tag])}
        c.update(iso=iso, tag=tag)
        shift(scn, g, iso, tag, -0.8 if pos > 0 else 0.8, "A new government")
    elif c["id"] == "press":
        tag = rng.choice(sorted(scn.tags))
        fill = {"tag": _lc(scn.tags[tag])}
        c.update(tag=tag)
        for iso in free:
            d = g.setdefault("drift", {}).setdefault(iso, {})
            d[tag] = round(d.get(tag, 0.0) - 0.25, 3)
    elif c["id"] == "partner" and g["rivals"]:
        rv = rng.choice(g["rivals"])
        fill = {"rival": scn.member(rv["iso3"]).name}
        c.update(rival=rv["iso3"])
    elif c["id"] == "donor":
        g["influence"] += 4
        for rv in g["rivals"]:
            rv["influence"] += 4
    elif c["id"] == "regional_summit":
        regions = sorted({m.region for m in scn.members if m.region in REGIONS})
        reg = rng.choice(regions) if regions else ""
        fill = {"region": REGIONS.get(reg, "a regional group")}
        c.update(region=reg)
    c["title"] = c["title"].format(**{"country": "", "tag": "", "rival": "", "region": "", **fill}).strip()
    c["body"] = c["body"].format(**{"country": "", "tag": "", "rival": "", "region": "", **fill})
    c["chapter"] = g["chapter"]
    g["crisis"] = c
    _log(g, "news", "Crisis: " + c["title"] + ". " + c["body"], "crisis", c.get("iso"))
    # capitals reconsider: one or two delegations shift a little on something they care about
    for _ in range(rng.choice([1, 2])):
        if not free:
            break
        iso = rng.choice(free)
        tag = rng.choice(sorted(scn.tags))
        shift(scn, g, iso, tag, rng.choice([-0.4, 0.4]), "New instructions from a capital")


# ---------------------------------------------------------------- offers at your door (phase 7)

def _make_offers(scn: Scenario, g: dict) -> None:
    """One or two delegations come to you with a deal. Each lasts until the end of the turn."""
    rng = _rng(g)
    g["offers"] = []
    free = [i for i in scn.isos if i not in _others(g)]
    rng.shuffle(free)
    want = rng.choice([1, 2, 2] if g.get("approach") == "envoy" else [1, 1, 2])
    taken = {p["iso3"] for p in g["promises"] if p["kept"] is None}
    for iso in free:
        if len(g["offers"]) >= want:
            break
        if iso in taken:
            continue
        name = scn.member(iso).name
        liked = [c for c in g["draft"] if mu_of(scn, g, iso, c["tags"]) >= 0.8]
        disliked = [(c, t) for c in g["draft"] for t in c["tags"] if len(c["tags"]) > 1 and mu_of(scn, g, iso, [t]) <= -0.8
                    and t not in (g["mandate"]["must"], g["mandate"].get("also"))]
        kinds = []
        trade = _trade_offer(scn, g, iso)
        if trade:
            kinds += ["trade", "trade"]                     # a trade that suits them is the commonest offer
        if liked:
            kinds.append("back")
        if disliked:
            kinds.append("drop")
        if g["trust"].get(iso, 0) >= 1:
            kinds.append("favour")
        if not kinds:
            continue
        kind = rng.choice(kinds)
        oid = f"o{g['n']}{len(g['offers'])}"
        if kind == "trade":
            g["offers"].append({"id": oid, "iso3": iso, **trade})
            _log(g, iso, f"{name} came to you with an offer.", "offer", g["iso3"])
            continue
        if kind == "back":
            c = rng.choice(liked)
            n = g["draft"].index(c) + 1
            g["offers"].append({"id": oid, "iso3": iso, "kind": "back", "clause": c["id"],
                                "text": f"{name}: \u201cBack clause {n} at the summit, and we will stand with your draft.\u201d",
                                "terms": f"You promise to vote yes on clause {n}. They warm to you, and trust you more."})
        elif kind == "drop":
            c, t = rng.choice(disliked)
            n = g["draft"].index(c) + 1
            g["offers"].append({"id": oid, "iso3": iso, "kind": "drop", "clause": c["id"], "tag": t,
                                "text": f"{name}: \u201cDrop the part of clause {n} that {_lc(scn.tags[t]).rstrip('.')}, and we are yours.\u201d",
                                "terms": f"You propose the amendment (the working group must agree). If it passes, they back your draft."})
        else:
            g["offers"].append({"id": oid, "iso3": iso, "kind": "favour",
                                "text": f"{name}: \u201cTwo Influence for the cause, and we owe you a vote when it counts.\u201d",
                                "terms": "You pay 2 Influence. They owe you a favour at the summit."})
        _log(g, iso, f"{name} came to you with an offer.", "offer", g["iso3"])


TRADE_GIVE = {"funding": "Fund our programme", "trade": "Open your market to our exports",
              "candidacy": "Back our candidate at the next UN election", "clause": "Back our clause at the summit",
              "influence": "Put some Influence behind our priorities", "standing": "Speak up for our position in the room"}
TRADE_GET = {"yes": "we vote yes on the whole text", "abstain": "we abstain rather than vote against you",
             "sponsor": "we sponsor your draft", "influence": "we put 3 Influence behind your work",
             "standing": "we praise your work in the room", "favour": "we owe you a vote when it counts",
             "commit": "we sign a commitment to your draft", "intel": "we tell you what a rival is planning"}


def _trade_offer(scn: Scenario, g: dict, iso: str) -> dict | None:
    """What a delegation would propose: the thing it values most from you, for what it can best give back. It asks
    for what its own situation makes it want (its asks), and offers its vote only if its vote is still in play."""
    t = deal_terms(scn, g, iso)
    if t["red_line"] or t["done"]:
        return None
    rng = random.Random(f"{g['seed']}:trade:{iso}:{g.get('tick', 0)}")
    wants = [w for w in t["asks"] if w in t["give"]] + sorted((w for w in t["give"] if w not in t["asks"]), key=lambda w: -t["give"][w])
    if not wants:
        return None
    want = rng.choice(wants[:2])                            # what it most wants from you, with some variety
    final = final_clause(g)
    est = vote_of(scn, latent(scn, g, iso, final, mood=False)) if final["tags"] else None
    last = g["chapter"] == LENGTHS[g["length"]]["chapters"]
    if est == "no" and "abstain" in t["get"]:
        offer = "abstain"                                   # its vote is in play: that's what it trades
    elif est in ("abstain", "no") and "yes" in t["get"]:
        offer = "yes"
    else:                                                   # its vote is already yours: it offers what it has
        pool = [o for o in (("sponsor",) if last else ()) + ("standing", "favour", "commit", "influence", "intel") if o in t["get"]]
        if not pool:
            return None
        offer = rng.choice(pool[:3])
    name = scn.member(iso).name
    return {"kind": "trade", "give": [want], "get": [offer], "clause": t.get("clause"), "cap": t["capital"].get(want, 0),
            "text": f"{name}: \u201c{TRADE_GIVE[want]}, and {TRADE_GET[offer]}.\u201d"}


def a_offer(scn, g, a):
    o = next((x for x in g.get("offers", []) if x["id"] == a.get("id")), None)
    if not o:
        raise GameError("That offer has lapsed.")
    g["offers"].remove(o)
    name = scn.member(o["iso3"]).name
    if a.get("answer") != "accept":
        _log(g, "you", f"You turned down {name}'s offer.", "action", o["iso3"])
        return {"accepted": False}
    out = {"accepted": True}
    if o["kind"] == "trade":
        t = deal_terms(scn, g, o["iso3"])
        if any(w not in t["give"] for w in o["give"]) or any(x not in t["get"] for x in o["get"]):
            raise GameError("That deal can't be done any more.")
        T.apply_terms(scn, g, o["iso3"], o["give"], o["get"], o.get("clause"))
        g["trust"][o["iso3"]] = min(R["trust_max"], g["trust"][o["iso3"]] + 1)
        if o.get("cap"):
            _capital(scn, g, o["cap"], CAPITAL_WHY.get(o["give"][0], "Your capital doesn't like that deal."))
        g["deals"] = g.get("deals", 0) + 1
        _log(g, "you", f"You agreed a trade with {name}.", "deal", o["iso3"])
        return out
    if o["kind"] == "back":
        if any(p["iso3"] == o["iso3"] and p["kept"] is None for p in g["promises"]) or not any(c["id"] == o["clause"] for c in g["draft"]):
            raise GameError("That deal can't be done any more.")
        g["promises"].append({"iso3": o["iso3"], "clause": o["clause"], "kept": None})
        g["trust"][o["iso3"]] = min(R["trust_max"], g["trust"][o["iso3"]] + 1)
        _sway(g, "you", o["iso3"], 0.35)
        if g["mandate"]["red"] in next(c for c in g["draft"] if c["id"] == o["clause"])["tags"]:
            _capital(scn, g, -2, CAPITAL_WHY["clause"])
    elif o["kind"] == "drop":
        c = next((x for x in g["draft"] if x["id"] == o["clause"]), None)
        if not c or o["tag"] not in c["tags"] or len(c["tags"]) < 2:
            raise GameError("That deal can't be done any more.")
        new = [t for t in c["tags"] if t != o["tag"]]
        if c["author"] != "you" and not room_accepts(scn, g, c, new):
            _log(g, "you", f"The working group wouldn't drop it, so the deal with {name} fell through.", "warning", o["iso3"])
            return {"accepted": False, "refused_by_room": True}
        _break_promises_if_changed(scn, g, c, new)
        _hist(scn, g, c, "you", f"removed for {name}: " + _lc(scn.tags[o["tag"]]).rstrip("."), new)
        c["tags"] = new
        if c["author"] != "you" and "you" not in c["amended_by"]:
            c["amended_by"].append("you")
        _sway(g, "you", o["iso3"], 0.5)
        if o["tag"] in (g["mandate"]["must"], g["mandate"].get("also")):
            _capital(scn, g, -2 if o["tag"] == g["mandate"]["must"] else -1, "You traded away part of your instructions for one vote.")
        g["trust"][o["iso3"]] = min(R["trust_max"], g["trust"][o["iso3"]] + 1)
    else:
        _spend(g, 0, 2)
        g["favours"].append(o["iso3"])
    g["deals"] = g.get("deals", 0) + 1
    _log(g, "you", f"You made a deal with {name}.", "action", o["iso3"])
    return out


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
        if rv.get("truce"):                                    # at peace: it backs the merged text, unless its red line is back in
            return 0 if rv["block"] in tags else 1
        if clause.get("id") == "final" and rv["want"] in tags and rv["block"] in tags:
            return 0               # half a loaf: it won't vote down a text that carries what it came for
        if rv["block"] in tags:
            return -1
        if rv["want"] in tags or clause.get("author") == actor:
            return 1
        mu = scn.dist(tags).get(actor, (0, 1))[0]
    return 1 if mu >= 0.4 else -1 if mu <= -0.4 else 0


def latent(scn: Scenario, g: dict, iso: str, clause: dict, stances: dict | None = None, mood: bool = True) -> float:
    mu, sigma = scn.dist(clause["tags"]).get(iso, (0.0, 1.5))
    mu += drift(g, iso, clause["tags"])
    x = mu + (sigma * g["moods"].get(iso, 0.0) if mood else 0.0)
    stances = stances if stances is not None else {a: stance(scn, g, a, clause) for a in ["you", *[r["iso3"] for r in g["rivals"]]]}
    for actor, s in stances.items():
        x += g["sway"].get(actor, {}).get(iso, 0.0) * s
    owner = g["endorse"].get((scn.member(iso).region if scn.member(iso) else ""))
    if owner:
        x += R["endorse_pull"] * stances.get(owner, 0)
    f = clause.get("force", 0)
    if f:                                                     # "Encourages" softens, "Urges" sharpens (the Summit, 8 Nov)
        x = x * 0.7 + 0.25 if f < 0 else x * 1.3 - 0.15
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
            out[m.iso3] = _deal_vote(scn, g, m.iso3, clause, vote_of(scn, latent(scn, g, m.iso3, clause, stances)))
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
    agree = (mu_of(scn, g, iso, [must]) - mu_of(scn, g, iso, [red])) / 4
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
    return f"Turn {g['turn']}" if g.get("length") == "quick" else f"Stage {g['chapter']}, turn {g['turn']}"


def _start_turn(scn: Scenario, g: dict) -> None:
    g["talks"] = None
    rng = _rng(g)
    # No random news each turn since 8 Nov 2026 (each stage's crisis stays): every other turn the Chair puts a
    # procedure question instead. The old deck is kept in content for reference.
    ev = {"id": "procedure", "title": "A procedure moment", "body": "", "teaches": "Knowing the rules of procedure is a power in the room.",
          "effect": {"question": True} if g["turn"] % 2 == 0 else {}}
    g["mods"] = {}
    eff = ev["effect"]
    g["ap"] = sum(x["n"] for x in ap_sources(scn, g)) + eff.get("ap", 0)
    g["ap_given"] = g.get("ap_given", 0) + g["ap"]
    g["overtime"] = 0
    seen = g.setdefault("ap_seen", {})                      # average actions per turn in each stage, for the balance harness
    k = str(g["chapter"])
    seen[k] = round((seen.get(k, 0) * g.get("ap_turns", {}).get(k, 0) + g["ap"]) / (g.get("ap_turns", {}).get(k, 0) + 1), 2)
    g.setdefault("ap_turns", {})[k] = g.get("ap_turns", {}).get(k, 0) + 1
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
    g["event"] = card if eff else None
    if eff:
        _log(g, "news", card["title"], "event")
    g["tick"] = g.get("tick", 0) + 1
    g["last_touched"], g["touched"] = g.get("touched", []), []
    rivals_move(scn, g)
    if g.get("reserve"):
        g["reserve"] = 0
        _log(g, "you", "Your reserve wasn't needed this time.", "info")
    fade_talk(g)
    _meeting(scn, g)
    _make_offers(scn, g)
    _intentions(scn, g)
    _staff_reports(scn, g)
    V.turn_start(scn, g)
    _check_breakthrough(scn, g)
    if g.get("recall"):
        g["recall"] = 0
        g["ap"] = 0
        g["offers"] = []
        g["visits"] = []                                    # nobody calls on an ambassador who's in the capital
        _log(g, "you", "You are in the capital for consultations this turn: no actions.", "warning")


def settle_bargains(scn, g) -> None:
    """A bloc bargain is kept if the draft carries its commitment when the stage ends; broken otherwise."""
    have = {t for c in g["draft"] for t in c["tags"]}
    for b in g.get("bargains", []):
        if b["kept"] is None and b["tag"] in have:
            b["kept"] = True
            for i in _region_members(scn, b["region"]):
                if i not in _others(g):
                    _sway(g, "you", i, 0.25)
            _log(g, "you", f"You kept your word to the {REGIONS[b['region']]}: its members stand with you.", "good")
        elif b["kept"] is None and b.get("by") is not None and g["chapter"] > b["by"]:
            b["kept"] = False
            _betray(scn, g, b["iso3"], f"you promised the {REGIONS[b['region']]} a clause and never tabled it.")
    for b in g.get("bargains", []):
        b.setdefault("by", g["chapter"])


def diligence(scn, g) -> tuple[float, float]:
    """The Ambassador path: the share of your actions you used, and the share of the room you engaged."""
    given = g.get("ap_given", 0)
    used = 1 - g.get("ap_unused", 0) / given if given else 0.0
    free = [i for i in scn.isos if i not in _others(g) and i != g["iso3"]]
    engaged = len(set(g.get("engaged", [])) & set(free)) / len(free) if free else 0.0
    return round(max(0.0, used), 3), round(engaged, 3)


LEVELS = ["Out of reach", "Possible", "Promising", "On course for gold"]


def path_progress(scn, g) -> list[dict]:
    """All five paths are always live (Civ-style, 9 Nov). A rough reading of where each stands now, in words: the
    vote as it stands, what's in the text, your whip sheet, your word and your legwork. Deliberately vague."""
    proj = projection(scn, g)
    tags = {t for c in g["draft"] for t in c["tags"]}
    m = g["mandate"]
    passing = proj["passed"]
    share = proj["yes"] / max(1, len(scn.members))
    mine = sum(1 for v in g["endorse"].values() if v == "you")
    got = [m["must"] in tags, m.get("also") in tags, m["red"] not in tags]
    mandate = 3 if passing and all(got) else 2 if got[0] and (got[1] or got[2]) else 1 if got[0] or got[2] else 0
    consensus = 3 if passing and share >= 0.75 and mine >= 2 and got[0] else 2 if share >= 0.6 and (mine >= 1 or got[0]) else 1 if share >= 0.45 else 0
    credit = [1.0 if c["author"] == "you" else 0.5 if "you" in c.get("amended_by", []) else 0.0 for c in g["draft"]]
    own = sum(credit) / len(credit) if credit else 0.0
    own_n = sum(1 for x in credit if x == 1.0)
    architect = 3 if passing and own >= R["architect_gold"] and own_n >= 3 else 2 if own >= 0.4 and own_n >= 2 else 1 if own_n else 0
    marks = len(g.get("whip", {}))
    broken = sum(1 for p in g["promises"] if p["kept"] is False)
    free = [i for i in scn.isos if i not in _others(g) and i != g["iso3"]]
    kingmaker = 0 if broken > 1 else 3 if marks >= len(free) * 0.6 and not broken and g["respect"] >= 7 else 2 if marks >= 3 and g["respect"] >= 5 else 1 if marks else 0
    used, engaged = diligence(scn, g)
    ambassador = 3 if used >= 0.9 and engaged >= 0.6 else 2 if used >= 0.75 and engaged >= 0.4 else 1 if used >= 0.5 or engaged >= 0.25 else 0
    level = {"mandate": mandate, "consensus": consensus, "architect": architect, "kingmaker": kingmaker, "ambassador": ambassador}
    return [{"code": c, "name": K.PATHS[c]["name"], "level": level[c], "word": LEVELS[level[c]]} for c in K.PATHS]


def fade_talk(g: dict) -> None:
    """Talk fades, deals bind (8 Nov): a little of your goodwill fades each turn, except where a deal, a promise or a
    signed commitment holds the delegation."""
    bound = set(g.get("deal_votes") or {}) | set(g.get("secured", [])) | {p["iso3"] for p in g["promises"] if p["kept"] is None}
    for iso, sw in list(g["sway"]["you"].items()):
        if sw > 0 and iso not in bound:
            g["sway"]["you"][iso] = round(sw * R["talk_fade"], 4)


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
    mu = mu_of(scn, g, iso, [g["mandate"]["must"]]) + g["sway"]["you"].get(iso, 0.0)
    cost = 1 + max(0, min(2, round(-mu)))
    if g["respect"] >= 6:
        cost -= 1
    if g["trust"].get(iso, 0) >= 2:
        cost -= 1
    floor = 0 if g.get("approach") == "linguist" else 1
    return max(floor, cost + g["mods"].get("lobby_cost", 0) - (1 if g.get("approach") == "linguist" else 0))


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
    why = T.locked(g, do)
    if why:
        raise GameError(why)
    handler = (CHAPTER if g["phase"] == "chapter" else SUMMIT).get(do)
    if not handler:
        raise GameError("That isn't something you can do now.")
    standing = g["respect"]
    out = handler(scn, g, action) or {}
    if g["respect"] <= 0 < standing and g["phase"] != "done" and not g.get("recall"):
        _recall(scn, g)
    g["stats"][do] = g["stats"].get(do, 0) + 1
    if isinstance(action.get("iso3"), str) and do not in ("post", "end_turn"):
        g.setdefault("touched", []).append(action["iso3"])
    if do in ENGAGE and isinstance(action.get("iso3"), str) and action["iso3"] not in g.setdefault("engaged", []):
        g["engaged"].append(action["iso3"])
    if do not in ("end_turn", "advance") and _check_breakthrough(scn, g):
        out["breakthrough"] = True
    if g["phase"] == "chapter" and do not in ("end_turn", "advance", "stay", "visit", "mark", "whip", "post", "answer") and not g.get("conv"):
        vid = V.after_move(scn, g, action)
        if vid:
            out["visit"] = vid
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
    out = {"heard": heard, "moved": round(moved, 2), "cost": cost, "red_line": mu <= R["redline"]}
    if g["length"] != "quick" and g["chapter"] >= 2:          # from Bloc meetings: its lean towards each rival
        out["leans"] = {scn.member(r["iso3"]).name: round(lean(scn, g, r["iso3"], iso), 2) for r in g["rivals"]}
    if g["length"] != "quick" and g["chapter"] >= 3 and final_clause(g)["tags"]:   # in Sponsors: how it would vote now
        out["would_vote"] = vote_of(scn, latent(scn, g, iso, final_clause(g), mood=False))
    return out


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
           "listens_to": T.listens_to(scn, g, iso) if "seed" in g else [],   # (the Almanac has no game to read)
           "sources": scn.sources.get(iso, []), "estimate": True, "fictional": scn.fictional,
           "shifts": [{"label": scn.tags[t], "dir": "warmer" if v > 0 else "cooler"}
                      for t, v in sorted(g.get("drift", {}).get(iso, {}).items()) if abs(v) >= 0.2]}
    if "read_room" in g["skills"]:
        out["mood"] = "warmer than usual" if g["moods"].get(iso, 0) > 0.3 else "cooler than usual" if g["moods"].get(iso, 0) < -0.3 else "as usual"
    return out


def a_propose(scn, g, a):
    card = next((c for c in scn.cards if c["id"] == a.get("card")), None)
    if not card or card["id"] not in g["cards"]:
        raise GameError("That clause card isn't on the table.")
    if len(g["draft"]) >= R["draft_max"]:
        raise GameError("The draft is full. Strike or merge a clause first.")
    if all(t in {x for cl in g["draft"] for x in cl["tags"]} for t in card["tags"]):
        raise GameError("Everything that card commits countries to is already in the draft.")
    _spend(g, 1, 0 if g["respect"] >= 8 else R["propose_cost"])
    text = (a.get("text") or "").strip()[:400]
    g["cards"].remove(card["id"])
    cid = f"p{g['next_id']}"
    g["next_id"] += 1
    g["draft"].append({"id": cid, "text": text or card["text"], "tags": list(card["tags"]), "author": "you", "amended_by": [],
                       "card": card["id"], "own_words": bool(text)})
    _hist(scn, g, g["draft"][-1], "you", "proposed it")
    _log(g, "you", "You proposed a clause: " + (text or card["text"]), "action")
    return {"clause": cid}


def _hist(scn: Scenario, g: dict, c: dict, who: str, what: str, new_tags: list | None = None) -> None:
    """Record a change to a clause. When its commitments change, its first wording is kept (and marked as no longer
    matching), so the player can see what it said and what it says now."""
    name = "You" if who == "you" else ("The original draft" if who == "draft" else scn.member(who).name if scn.member(who) else who)
    c.setdefault("history", []).append({"when": _when(g), "who": who, "name": name, "what": what})
    if new_tags is not None:
        c.setdefault("orig_tags", list(c["tags"]))
        c["text_stale"] = sorted(new_tags) != sorted(c["orig_tags"])


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
        if any(add in cl["tags"] for cl in g["draft"]):
            raise GameError("Another clause already makes that commitment.")
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
    _hist(scn, g, c, "you", ("added: " + _lc(scn.tags[add]).rstrip(".") if add else "") + ("; " if add and remove else "") +
          ("removed: " + _lc(scn.tags[remove]).rstrip(".") if remove else ""), tags)
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


def _betray(scn, g, iso: str, why: str) -> None:
    """Breaking your word (8 Nov): the delegation turns hostile, its regional group cools, you lose Standing, and your
    name for broken promises makes every later deal dearer. A rival also ends any peace and comes at you."""
    g["trust"][iso] = -R["trust_max"]
    _sway(g, "you", iso, -0.5)
    reg = scn.member(iso).region
    for i in _region_members(scn, reg):
        if i != iso and i not in _others(g):
            _sway(g, "you", i, -0.1)
    g["respect"] = max(0, g["respect"] - 2)
    g.setdefault("rep", {})["broken"] = g.get("rep", {}).get("broken", 0) + 1
    (g.get("deal_votes") or {}).pop(iso, None)
    rv = next((r for r in g["rivals"] if r["iso3"] == iso), None)
    if rv:
        rv["truce"] = False
        rv["grudge"], rv["fury"] = 2, g.get("tick", 0) + 1
    _log(g, iso, f"Betrayal: {why} {scn.member(iso).name} won't forget it, and the room has noticed.", "warning", iso)


def _break_promises_if_changed(scn, g, clause, new_tags, actor: str = "you") -> None:
    """A clause you gave your word on is changed. Your own change is a betrayal; someone else's voids the promise."""
    old = set(clause["tags"])
    new = set(new_tags or [])
    for p in g["promises"]:
        if p["clause"] == clause["id"] and p["kept"] is None:
            if actor == "you":
                p["kept"] = False
                _betray(scn, g, p["iso3"], "you promised to back that clause, then changed it.")
            else:
                p["kept"] = "void"
    if actor != "you":
        return
    for p in g.get("pacts", []):
        if p["kept"] is None and p["tag"] in old and p["tag"] not in new:
            p["kept"] = False
            _betray(scn, g, p["iso3"], "you agreed not to stand against its clause, then cut it.")
    for rv in g["rivals"]:
        if rv.get("truce") and rv.get("truce_want") in old and rv.get("truce_want") not in new:
            _betray(scn, g, rv["iso3"], "you made peace on its wish, then cut it from the text.")


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
    if g["mandate"]["red"] in c["tags"]:
        _capital(scn, g, -2, CAPITAL_WHY["clause"])
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
    return {"signed": {"iso3": iso, "name": scn.member(iso).name, "role": role,
                       "sponsors": len(g["sponsors"]), "signatories": len(g["signatories"])}}


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
    g["ap_unused"] = g.get("ap_unused", 0) + max(0, g.get("ap", 0))      # actions left on the table
    if g.get("conv"):
        T.a_talk(scn, g, {"step": "follow", "choice": "close"})   # a conversation left open ends politely
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


def final_clause(g: dict) -> dict:
    """The draft as one text: every commitment in it."""
    return {"id": "final", "tags": list(dict.fromkeys(t for c in g["draft"] for t in c["tags"])), "author": "draft"}


def projection(scn: Scenario, g: dict) -> dict:
    """The vote on the whole draft as things stand, leaving out every delegation's hidden mood on the day: what the
    tug-of-war bar shows, and what rivals plan against."""
    final = final_clause(g)
    if not final["tags"]:
        return {"yes": 0, "no": 0, "abstain": len(scn.members), "passed": False, "votes": {}, "summary": "There is no draft yet."}
    st = {a: stance(scn, g, a, final) for a in ["you", *[r["iso3"] for r in g["rivals"]]]}
    word = {1: "yes", -1: "no", 0: "abstain"}
    votes = {}
    for m in scn.members:
        if m.iso3 == g["iso3"]:
            votes[m.iso3] = word[st["you"]]
        elif m.iso3 in st:
            votes[m.iso3] = word[st[m.iso3]]
        else:
            votes[m.iso3] = _deal_vote(scn, g, m.iso3, final, vote_of(scn, latent(scn, g, m.iso3, final, st, mood=False)))
    res = tally(scn.rule, votes, len(votes))
    return {"yes": res.yes, "no": res.no, "abstain": res.abstain, "passed": res.passed, "votes": votes, "summary": res.summary}


STYLE_WEIGHT = {"hawk": {"amend": 1.3, "strike": 1.3}, "broker": {"side": 1.6, "lobby": 1.15, "poach": 1.2},
                "spoiler": {"strike_you": 1.7}}


def _rival_options(scn: Scenario, g: dict, rv: dict, react: bool = False, poach: bool = True) -> list:
    """Every move a rival could make now, valued by how much it serves the rival's own instructions: get its wish into
    the text, get its red line out, and then push the vote the way it wants the whole text to go. Each option is
    (value, (kind, target), cost)."""
    me, want, block = rv["iso3"], rv["want"], rv["block"]
    w = STYLE_WEIGHT.get(rv.get("style", "hawk"), {})
    secured = set(g.get("secured", []))
    opts = []
    in_text = {t for c in g["draft"] for t in c["tags"]}
    if want not in in_text and len(g["draft"]) < R["draft_max"]:
        card = next((c for c in scn.cards if c["id"] in g["cards"] and want in c["tags"] and block not in c["tags"]), None)
        if card:
            opts.append((2.2, ("propose", card["id"]), 1))
    for c in g["draft"]:
        if rv.get("spare") in c["tags"]:
            continue                                         # it agreed to leave this one alone
        if block in c["tags"]:
            if len(c["tags"]) > 1:
                opts.append((2.0 * w.get("amend", 1), ("amend", c["id"]), 1))
            elif len(g["draft"]) > 1:
                opts.append((1.8 * w.get("strike", 1), ("strike", c["id"]), 2))
        elif c["author"] == "you" and want not in c["tags"] and "strike_you" in w and len(g["draft"]) > 1:
            opts.append((1.0 * w["strike_you"], ("strike", c["id"]), 2))
    # the battle: the clause carrying its red line (to vote it down clause by clause), or else the whole text
    final = next((c for c in g["draft"] if block in c["tags"]), None) or final_clause(g)
    mine = 0
    if final["tags"]:
        st = {a: stance(scn, g, a, final) for a in ["you", *[r["iso3"] for r in g["rivals"]]]}
        mine = st[me]
        if mine:
            edge = scn.c_yes if mine > 0 else scn.c_no
            for iso in scn.isos:
                if iso in _others(g) or g["sway"][me].get(iso, 0.0) >= R["sway_cap"]:
                    continue
                x = latent(scn, g, iso, final, st, mood=False)
                gap = (edge - x) * mine            # how far it must still move the rival's way (below zero: already there)
                if gap < -0.3 or gap > 1.2:
                    continue
                v = 1.0 - abs(gap - 0.15) / 1.4
                if iso in secured:
                    v *= 0.5
                if react and iso in g.get("last_touched", []):
                    v += 0.45
                opts.append((v * w.get("lobby", 1), ("lobby", iso), 2 if iso in secured else 1))
                yours = g["sway"]["you"].get(iso, 0.0)
                if poach and yours >= 0.3:
                    opts.append(((v + 0.3 * min(1.0, yours)) * 0.9 * w.get("poach", 1), ("poach", iso),
                                 R["poach_cost"] * (2 if iso in secured else 1)))
    regions = sorted({m.region for m in scn.members if m.region in REGIONS and g["endorse"].get(m.region) != me})
    if regions:
        reg = max(regions, key=lambda r: (sum(1 for i in _region_members(scn, r) if i not in _others(g)
                                              and 0 <= lean(scn, g, me, i) <= R["lean_min"] + 0.2), r))
        opts.append((0.75 * w.get("side", 1), ("side", reg), 3))
    if g["chapter"] == LENGTHS[g["length"]]["chapters"] and (
            len(rv["sponsors"]) < R["sponsors"] or len(rv["signatories"]) + len(rv["sponsors"]) < _signers_needed(scn)):
        taken = set(g["sponsors"]) | set(g["signatories"]) | set(rv["sponsors"]) | set(rv["signatories"])
        pool = sorted((i for i in scn.isos if i not in _others(g) and i not in taken and lean(scn, g, me, i) >= 0),
                      key=lambda i: (-lean(scn, g, me, i), i))
        if pool:
            opts.append((1.5, ("sign", pool[0]), 0))
    if not opts:     # nothing pressing: build goodwill where it is closest to tipping
        cands = sorted((abs(lean(scn, g, me, i) - 0.35), i) for i in scn.isos
                       if i not in _others(g) and g["sway"][me].get(i, 0.0) < R["sway_cap"])
        if cands:
            opts.append((0.2, ("lobby", cands[0][1]), 1))
    return sorted(opts, key=lambda o: (-o[0], o[1]))


def _target_name(scn: Scenario, g: dict, kind: str, target: str) -> str:
    if kind in ("amend", "strike"):
        n = next((i + 1 for i, c in enumerate(g["draft"]) if c["id"] == target), None)
        return f"clause {n}" if n else "a clause"
    if kind == "propose":
        return "a clause of its own"
    if kind == "side":
        return f"the {REGIONS.get(target, 'regional group')}"
    return scn.member(target).name if scn.member(target) else target


def _hostile(scn: Scenario, g: dict, kind: str, target: str) -> bool:
    """Whether a rival's move works against you: one your reserve answers."""
    if kind in ("lobby", "poach"):
        return target in g["sponsors"] or target in g["signatories"] or lean(scn, g, "you", target) > 0
    if kind in ("amend", "strike"):
        c = next((c for c in g["draft"] if c["id"] == target), None)
        return bool(c) and (c["author"] == "you" or g["mandate"]["must"] in c["tags"] or g["mandate"].get("also") in c["tags"])
    return False


def _rival_act(scn: Scenario, g: dict, rv: dict, kind: str, target: str, cost: int, step: float) -> bool:
    if not _rival_spend(rv, cost):
        return False
    me = rv["iso3"]
    name = scn.member(me).name
    if g.get("reserve") and _hostile(scn, g, kind, target):
        g["reserve"] -= 1
        g.setdefault("countered", []).append({"rival": me, "target": target, "tick": g.get("tick", 0)})
        _log(g, "you", f"Your reserve answered {name} at once: its move on {_target_name(scn, g, kind, target)} came to nothing.",
             "counter", target if scn.member(target) else None)
        g.setdefault("moved", {}).setdefault(me, []).append(target)
        return True
    if kind == "propose":
        card = next(c for c in scn.cards if c["id"] == target)
        g["cards"].remove(card["id"])
        cid = f"p{g['next_id']}"
        g["next_id"] += 1
        g["draft"].append({"id": cid, "text": card["text"], "tags": list(card["tags"]), "author": me, "amended_by": [], "card": card["id"]})
        _hist(scn, g, g["draft"][-1], me, "proposed it")
        _log(g, me, f"{name} proposed a clause: {card['text']}", "rival")
    elif kind == "amend":
        c = next(c for c in g["draft"] if c["id"] == target)
        new = [t for t in c["tags"] if t != rv["block"]]
        if c["author"] != me and not room_accepts(scn, g, c, new):
            _log(g, me, f"{name} tried to amend {_target_name(scn, g, kind, target)}; the working group refused.", "rival")
        else:
            _break_promises_if_changed(scn, g, c, new, actor=me)
            _hist(scn, g, c, me, "removed: " + _lc(scn.tags[rv["block"]]).rstrip("."), new)
            c["tags"] = new
            c["amended_by"].append(me)
            _log(g, me, f"{name} amended a clause to drop the part that {_lc(scn.tags[rv['block']]).rstrip('.')}.", "rival")
    elif kind == "strike":
        c = next(c for c in g["draft"] if c["id"] == target)
        yours = c["author"] == "you"
        if not room_accepts(scn, g, c, None):
            _log(g, me, f"{name} moved to strike {'your clause' if yours else 'a clause'}; the working group kept it.", "rival")
        else:
            g["draft"].remove(c)
            g["struck"].append({**c, "by": me})
            for p in g["promises"]:
                if p["clause"] == c["id"] and p["kept"] is None:
                    p["kept"] = "void"
            _log(g, me, f"{name} struck {'your clause' if yours else 'a clause'} from the draft.", "rival")
    elif kind == "lobby":
        _sway(g, me, target, step * (0.5 if target in g.get("secured", []) else 1))
        g["region_last"][scn.member(target).region] = me
        _log(g, me, f"{name} lobbied {scn.member(target).name}.", "rival", target)
    elif kind == "poach":
        cut = R["poach_step"] * (0.5 if target in g.get("secured", []) else 1)
        g["sway"]["you"][target] = round(max(0.0, g["sway"]["you"].get(target, 0.0) - cut), 4)
        _sway(g, me, target, cut / 2)
        _log(g, me, f"{name} won back ground with {scn.member(target).name}: your goodwill there fell.", "rival", target)
    elif kind == "side":
        for iso in _region_members(scn, target):
            if iso not in _others(g):
                _sway(g, me, iso, 0.12)
        g["region_last"][target] = me
        _log(g, me, f"{name} hosted a side event for the {REGIONS[target]}.", "rival")
    elif kind == "sign":
        role = "sponsor" if len(rv["sponsors"]) < R["sponsors"] and lean(scn, g, me, target) >= R["sponsor_lean"] else "signatory"
        rv["sponsors" if role == "sponsor" else "signatories"].append(target)
        _log(g, me, f"{scn.member(target).name} signed {name}'s draft as a {role}.", "rival", target)
    g.setdefault("moved", {}).setdefault(me, []).append(target)
    return True


def rivals_move(scn: Scenario, g: dict) -> None:
    """Each rival spends its actions on the best moves it can find for its own instructions. Easy rivals sometimes
    blunder; hard ones also go after the delegations you worked on last turn."""
    d = DIFFICULTIES[g["difficulty"]]
    plan = PLAN[g["difficulty"]]
    rng = _rng(g)
    cr = g.get("crisis") or {}
    g["moved"] = {}
    for rv in [r for r in g["rivals"] if not r.get("truce") and r.get("hold") != g.get("tick")]:
        extra = 1 if cr.get("id") == "partner" and cr.get("rival") == rv["iso3"] and cr.get("chapter") == g["chapter"] else 0
        extra += 1 if rv.get("fury") == g.get("tick") else 0          # a rival you've refused twice comes at you harder
        tried: set = set()
        for _ in range(d["ap"] + extra):
            opts = [o for o in _rival_options(scn, g, rv, react=plan["react"], poach=plan["poach"]) if o[1] not in tried]
            if plan["noise"] and rng.random() < plan["noise"]:
                rng.shuffle(opts)
            done = False
            for _v, (kind, target), cost in opts:
                if rv["influence"] >= cost:
                    tried.add((kind, target))
                    done = _rival_act(scn, g, rv, kind, target, cost, d["step"])
                    if done:
                        break
            if not done:
                break
    _check_claims(scn, g)


def _intentions(scn: Scenario, g: dict) -> None:
    """What each rival means to do next, as things stand: advisers can find this out (and the player can then change
    the rival's plans)."""
    plan = PLAN[g["difficulty"]]
    g["intent"] = {}
    for rv in [r for r in g["rivals"] if not r.get("truce")]:
        opts = [o for o in _rival_options(scn, g, rv, poach=plan["poach"]) if rv["influence"] + R["rival_income"] >= o[2]]
        if opts:
            alt = opts[1] if len(opts) > 1 else None
            g["intent"][rv["iso3"]] = {"kind": opts[0][1][0], "target": opts[0][1][1],
                                       "alt_kind": alt[1][0] if alt else None, "alt": alt[1][1] if alt else None}


# ---------------------------------------------------------------- upkeep and chapters

def _endorsements(scn: Scenario, g: dict) -> None:
    actors = ["you", *[r["iso3"] for r in g["rivals"]]]
    for reg in sorted({m.region for m in scn.members if m.region in REGIONS}):
        voters = [i for i in _region_members(scn, reg) if i not in _others(g)]
        if len(voters) < 2:
            continue
        cr = g.get("crisis") or {}
        lm = R["lean_min"] - (0.1 if cr.get("id") == "regional_summit" and cr.get("region") == reg and cr.get("chapter") == g["chapter"] else 0)
        counts = {a: sum(1 for i in voters if lean(scn, g, a, i) > lm and
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


def snapshot(scn: Scenario, g: dict, label: str) -> None:
    """Your standing at the end of a turn, for the debrief's graph."""
    free = [i for i in scn.isos if i not in _others(g)]
    g.setdefault("history", []).append({
        "at": label, "influence": g["influence"], "respect": g["respect"], "expertise": g["expertise"],
        "leaning": sum(1 for i in free if lean(scn, g, "you", i) > R["lean_min"]),
        "endorse": sum(1 for v in g["endorse"].values() if v == "you"), "of": len(free)})


def _upkeep(scn: Scenario, g: dict) -> None:
    _endorsements(scn, g)
    snapshot(scn, g, ("W" if g["length"] == "quick" else f"C{g['chapter']}") + f".{g['turn']}")
    mine = sum(1 for v in g["endorse"].values() if v == "you")
    g["influence"] += R["income"] + mine * R["endorse_income"]
    for rv in g["rivals"]:
        rv["influence"] += R["rival_income"] + (1 if g.get("approach") == "envoy" else 0) + sum(1 for v in g["endorse"].values() if v == rv["iso3"]) * R["endorse_income"]
    L = LENGTHS[g["length"]]
    g["offers"] = []
    if g["turn"] < turns_now(g):
        g["turn"] += 1
        _start_turn(scn, g)
        return
    _end_stage(scn, g)


# ---------------------------------------------------------------- the summit

def _open_summit(scn: Scenario, g: dict) -> None:
    g["phase"] = "summit"
    g["ap"] = 0
    g["event"] = None
    g["question"] = None
    if g["tabled_first"] is False:
        g["respect"] = max(0, g["respect"] - 1)
    SM.open_summit(scn, g)
    _log(g, "news", "The Summit opens: position statements, the draft read in full, a caucus, the amendments one by one, "
                    "then the final vote.", "event")


def s_final(scn, g, a):
    s = g["summit"]
    if s["step"] != "final":
        raise GameError("The final vote comes after the amendments and the final reading.")
    my_vote = a.get("vote")
    if my_vote not in VOTES:
        raise GameError("Cast your vote on the resolution: yes, no or abstain.")
    if not s.get("results"):
        s["results"] = SM._clause_results(scn, g)
    SM.settle_final(scn, g, my_vote)
    tags = list(dict.fromkeys(t for c in g["draft"] for t in c["tags"]))   # the text as amended (D-102)
    final = {"id": "final", "tags": tags, "author": "draft"}
    if tags:
        votes = votes_on(scn, g, final, my_vote=my_vote, favour_for=set(g["favours"]))
        res = tally(scn.rule, votes, len(votes))
        passed, summary, counts = res.passed, res.summary, {"yes": res.yes, "no": res.no, "abstain": res.abstain}
    else:
        votes, passed, summary, counts = {}, False, "No clauses were adopted, so there is no resolution to vote on.", {"yes": 0, "no": 0, "abstain": 0}
    s["final"] = {"tags": tags, "votes": votes, "passed": passed, "summary": summary, **counts, "my_vote": my_vote}
    must, red, also = g["mandate"]["must"], g["mandate"]["red"], g["mandate"].get("also")
    if tags and must in tags and red not in tags:
        if my_vote == "no":
            g["golden"] = "broke"
            g["respect"] = max(0, g["respect"] - R["golden_respect"])
            _log(g, "you", "You voted against a text that carried your capital's main aim. Half a loaf is better than none.", "warning")
        elif my_vote == "yes" and also not in tags:
            g["golden"] = "kept"
            g["respect"] = min(R["respect_max"], g["respect"] + 1)
            _log(g, "you", "You backed a text that wasn't everything you wanted. The room respects a delegate who takes progress.", "good")
    for iso, dv in (g.get("deal_votes") or {}).items():
        if tags and red_line(scn, iso, tags):
            _log(g, iso, f"{scn.member(iso).name} broke its deal with you: the text crossed its own red line.", "warning", iso)
    for adv in g.get("staff", []):
        cl = adv.get("claim") or {}
        if cl.get("vote") and votes.get(cl.get("iso")) == cl["vote"]:
            _xp(g, adv, f"Their forecast of {scn.member(cl['iso']).name}'s vote proved right.")
    snapshot(scn, g, "Summit")
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
    aims = got[0] or got[1]          # consensus around a text that carries none of your aims is someone else's success
    consensus = 0 if not passed else 3 if share >= 0.75 and mine_regions >= 2 and got[0] else         2 if share >= 0.65 and mine_regions >= 1 and aims else 1
    kept = [r["clause"] for r in s["results"] if r["passed"]]
    clauses = {c["id"]: c for c in g["draft"]}
    credit = [1.0 if clauses[c]["author"] == "you" else 0.5 if "you" in clauses[c]["amended_by"] else 0.0 for c in kept if c in clauses]
    own = sum(credit) / len(credit) if credit else 0.0
    own_kept = sum(1 for x in credit if x == 1.0)
    architect = 0 if not passed else 3 if own >= R["architect_gold"] and own_kept >= 3 and share >= 0.6 else \
        2 if own >= 0.4 and own_kept >= 2 else 1 if own >= 0.2 else 0          # the text bears your mark (9 Nov)
    st = s.get("statement") or {}
    if not passed and st.get("adopted"):
        sg = [must in st["tags"], also in st["tags"], red not in st["tags"]]
        mandate = max(mandate, 2 if sg[0] and sg[2] else 1 if sg[0] or sg[2] else 0)
        consensus = max(consensus, 2 if mine_regions >= 1 else 1)
        mine_tags = {t for c in g["draft"] if c["author"] == "you" for t in c["tags"]}
        architect = max(architect, 1 if mine_tags & set(st["tags"]) else 0)
    judged = [(iso, v) for iso, v in g["whip"].items() if iso in f["votes"]]
    right = sum(1 for iso, v in judged if f["votes"][iso] == v)
    for r in s.get("results", []):                         # each clause's column on the whip sheet
        for iso, v in g.get("sheet", {}).get(r["clause"], {}).items():
            if iso in r["votes"]:
                judged.append((iso, v))
                right += r["votes"][iso] == v
    acc = right / len(judged) if judged else 0.0
    need = min(5, max(3, len(scn.members) // 4))
    broken = sum(1 for p in g["promises"] if p["kept"] is False)
    kingmaker = 0 if len(judged) < need else 3 if acc >= 0.8 and broken == 0 and g["respect"] >= 7 else \
        2 if acc >= 0.65 and broken <= 1 and g["respect"] >= 5 else 1 if acc >= 0.5 else 0
    used, engaged = diligence(scn, g)
    ambassador = 3 if passed and used >= 0.9 and engaged >= 0.6 else 2 if used >= 0.75 and engaged >= 0.4 else \
        1 if used >= 0.5 or engaged >= 0.25 else 0
    paths = {"mandate": mandate, "consensus": consensus, "architect": architect, "kingmaker": kingmaker, "ambassador": ambassador}
    best = max(paths, key=lambda p: (paths[p], p == g["path"]))           # every game is graded on all four (9 Nov)
    return {"passed": passed, "statement": bool(st.get("adopted")), "paths": paths, "chosen": best, "grade": paths[best],
            "share_yes": round(share, 3), "own_text": round(own, 3), "whip_right": right, "whip_judged": len(judged),
            "broken_promises": broken, "kept_promises": sum(1 for p in g["promises"] if p["kept"] is True),
            "endorsements": mine_regions, "respect": g["respect"], "expertise": g["expertise"], "golden": g.get("golden"),
            "approach": g.get("approach", "diplomat")}


GRADES = {0: "No medal", 1: "Bronze", 2: "Silver", 3: "Gold"}

# ---------------------------------------------------------------- your staff (phase 8)

def _eff_stars(scn: Scenario, g: dict, adv: dict, iso: str) -> int:
    """How well an adviser reads a delegation: analysts read rivals best, regional experts their own group, and the
    Intelligence network skill lifts everyone by a star."""
    s = adv["stars"]
    rival = any(r["iso3"] == iso for r in g["rivals"])
    if adv["kind"] in ("analyst", "legal") and not rival:
        s -= 1
    if adv["kind"] == "regional" and not rival and scn.member(iso).region == adv.get("region"):
        s += 1
    if g.get("meeting") and not rival and scn.member(iso).region == g["meeting"]:
        s += 1                                                   # a group in session is easier to read
    if "rival_intel" in g["skills"]:
        s += 1
    return max(1, min(3, s))


def sync_skills(g: dict) -> list[str]:
    """Your skills are what your advisers' ranks bring (since 8 Nov 2026): returns any newly gained."""
    have = sorted({s for a in g.get("staff", []) for st, ss in K.STAFF_SKILLS.get(a["kind"], {}).items() if a["stars"] >= st for s in ss})
    new = [s for s in have if s not in g.get("skills", [])]
    g["skills"] = have
    return new


def _xp(g: dict, adv: dict, why: str) -> None:
    adv["xp"] += 1
    nxt = adv["stars"] + 1
    if nxt in PROMOTE and adv["xp"] >= PROMOTE[nxt]:
        adv["stars"] = nxt
        new = sync_skills(g)
        _log(g, "staff", f"{adv['name']} is promoted to {K.STAFF_RANKS[nxt]}. {why}" +
             (" New skill: " + ", ".join(K.SKILLS[s]["name"] for s in new) + "." if new else ""), "promote")
    else:
        _log(g, "staff", f"{adv['name']}: {why}", "staff")


def _check_claims(scn: Scenario, g: dict) -> None:
    """After the rivals move: an adviser whose warning about a rival proved right, or who warned you in time to act,
    gains experience."""
    tick = g.get("tick", 0)
    acted = set(g.get("last_touched", [])) | set(g.get("secured", []))
    blocked = {c["target"] for c in g.get("countered", []) if c.get("tick") == tick}
    for adv in g.get("staff", []):
        cl = adv.get("claim") or {}
        if not cl.get("rival") or not cl.get("right"):
            continue
        name = scn.member(cl["rival"]).name
        if cl["target"] in g.get("moved", {}).get(cl["rival"], []) or cl["target"] in blocked:
            _xp(g, adv, f"Their warning about {name} proved right.")
        elif cl["target"] in acted:
            _xp(g, adv, f"You acted on their warning about {name}.")


def _staff_reports(scn: Scenario, g: dict) -> None:
    """At the start of each turn every posted adviser reports on the delegation they study. One-star reports can be
    wrong, and say so; a report needs a full turn in post."""
    rng = _rng(g)
    rivals = {r["iso3"]: r for r in g["rivals"]}
    proj = projection(scn, g)["votes"]
    prev = g.get("proj_prev") or {}
    final = final_clause(g)
    verbs = {"lobby": "lobby", "poach": "try to win back", "amend": "amend", "strike": "move to strike", "propose": "propose",
             "side": "court", "sign": "sign up"}
    for adv in g.get("staff", []):
        adv["claim"] = None
        iso = adv.get("post")
        if not iso or g.get("tick", 0) <= adv.get("since", 0):
            continue
        s = _eff_stars(scn, g, adv, iso)
        right = s == 3 or rng.random() < ACCURACY[s]
        name = scn.member(iso).name
        if iso in rivals:
            rv = rivals[iso]
            it = g.get("intent", {}).get(iso)
            if not it:
                text = f"{name} is lying low: it has nothing in hand this turn."
            else:
                wrong = not right and it.get("alt")
                kind, target = (it["alt_kind"], it["alt"]) if wrong else (it["kind"], it["target"])
                where = _target_name(scn, g, kind, target)
                if s == 1:
                    m = scn.member(target)
                    text = (f"{name} is busy around the {REGIONS.get(m.region, 'room')}." if m
                            else f"{name} is working on the text.")
                elif s == 2:
                    text = f"{name} is going after {where}."
                else:
                    text = (f"{name} will {verbs.get(kind, 'move on')} {where}. It wants a clause that "
                            f"{_lc(scn.tags[rv['want']]).rstrip('.')}, and nothing that {_lc(scn.tags[rv['block']]).rstrip('.')}.")
                adv["claim"] = {"rival": iso, "target": target, "right": not wrong}
        else:
            mood = g["moods"].get(iso, 0.0)
            warm = mood > 0.3 if right else mood <= 0.3
            cool = mood < -0.3 if right else mood >= -0.3
            parts = [f"{name} seems {'warmer than usual' if warm else 'cooler than usual' if cool else 'much as usual'} today"]
            if s >= 2:
                tag = max(scn.tags, key=lambda t: (mu_of(scn, g, iso, [t]), t))
                parts.append(f"it most wants a clause that {_lc(scn.tags[tag]).rstrip('.')}")
                lt = T.listens_to(scn, g, iso)
                parts.append(f"pitch it {lt[0].lower()} and {lt[1].lower()}" if right else f"pitch it {lt[0].lower()}")
            if s >= 3:
                courted = max(g["rivals"], key=lambda r: g["sway"][r["iso3"]].get(iso, 0.0), default=None)
                if courted and g["sway"][courted["iso3"]].get(iso, 0.0) > 0.2:
                    parts.append(f"{scn.member(courted['iso3']).name} has been courting it")
                if final["tags"]:
                    v = vote_of(scn, latent(scn, g, iso, final))
                    parts.append(f"on the draft as it stands it would vote {v}")
                    adv["claim"] = {"iso": iso, "vote": v}
            text = "; ".join(parts) + "."
            if prev.get(iso) not in (None, "yes") and proj.get(iso) == "yes" and proj.get(g["iso3"]) == "yes":
                _xp(g, adv, f"Their work helped bring {name} round.")
        adv["report"] = {"text": text, "sure": K.SURE[s], "stars": s, "at": iso, "tick": g.get("tick", 0)}
        _log(g, "staff", f"{adv['name']} ({K.SURE[s]}): {text}", "staff", iso)
    waver = sorted(i for i, v in prev.items() if v == "yes" and proj.get(i) != "yes" and i not in _others(g) and i != g["iso3"])
    if waver and g.get("staff"):
        who = next((a for a in g["staff"] if a.get("post") == waver[0]), g["staff"][0])
        _log(g, "staff", f"{who['name']}: Ambassador, {scn.member(waver[0]).name} is wavering.", "worry", waver[0])
    g["proj_prev"] = proj


def a_hire(scn, g, a):
    kind = a.get("kind")
    if kind not in K.STAFF_KINDS:
        raise GameError("Choose an analyst, a regional expert or a legal adviser.")
    if len(g["staff"]) >= R["staff_max"]:
        raise GameError(f"Your mission has room for {R['staff_max']} advisers.")
    _spend(g, 0, R["hire_cost"])
    used = {x["name"] for x in g["staff"]}
    name = next(n for n in K.STAFF_NAMES if n not in used)
    n = max((int(x["id"][1:]) for x in g["staff"]), default=0) + 1
    g["staff"].append(_adviser(kind, name, 1, scn.member(g["iso3"]).region, n))
    sync_skills(g)
    _log(g, "you", f"You took on {name} as a {K.STAFF_KINDS[kind]['name'].lower()}.", "action")
    return {"hired": f"a{n}"}


def a_post(scn, g, a):
    adv = next((x for x in g["staff"] if x["id"] == a.get("adviser")), None)
    if not adv:
        raise GameError("Choose one of your advisers.")
    iso = a.get("iso3") or None
    if iso:
        if not scn.member(iso) or iso == g["iso3"]:
            raise GameError("Choose another delegation on the committee.")
        other = next((x for x in g["staff"] if x is not adv and x.get("post") == iso), None)
        if other:
            raise GameError(f"{other['name']} already studies {scn.member(iso).name}.")
    if iso == adv.get("post"):
        return {}
    adv.update(post=iso, since=g.get("tick", 0), report=None, claim=None)
    _log(g, "you", f"{adv['name']} now studies {scn.member(iso).name}." if iso else f"{adv['name']} is back at the mission.", "action", iso)
    return {}


def a_reserve(scn, g, a):
    if g.get("reserve"):
        raise GameError("You already have an action held in reserve.")
    _spend(g, 1, 0)
    g["reserve"] = 1
    _log(g, "you", "You held an action in reserve, to answer the first rival move against you.", "action")
    return {}


def a_secure(scn, g, a):
    iso = a.get("iso3")
    _country(scn, g, iso)
    if iso in g["secured"]:
        raise GameError(f"{scn.member(iso).name} is already secured.")
    if len(g["secured"]) >= R["secure_max"]:
        raise GameError(f"You can secure up to {R['secure_max']} delegations.")
    if g["trust"].get(iso, 0) < 1 or lean(scn, g, "you", iso) <= R["lean_min"]:
        raise GameError("Only a delegation that trusts you and leans your way will sign a commitment.")
    _spend(g, 1, R["secure_cost"])
    g["secured"].append(iso)
    _log(g, "you", f"{scn.member(iso).name} signed a commitment: rivals will find it twice as hard to move.", "action", iso)
    return {}


# ---------------------------------------------------------------- the golden rule and the rivals, in the debrief

def half_loaf(scn: Scenario, g: dict) -> dict:
    """The first rule of the UN: don't vote down progress because it isn't everything you wanted."""
    f = (g.get("summit") or {}).get("final") or {}
    tags = f.get("tags") or []
    m = g["mandate"]
    aims = [x for x in (m["must"], m.get("also")) if x]
    gained = [scn.tags[t] for t in aims if t in tags]
    missing = [scn.tags[t] for t in aims if t not in tags]
    red_in = m["red"] in tags
    passed = bool(f.get("passed"))
    if passed and gained:
        verdict = (f"The resolution carries {len(gained)} of your capital's {len(aims)} aims. "
                   + ("All of them: a complete success." if not missing else
                      "Not everything, but each of those is now the committee's policy: more than no resolution would have given you."))
    elif passed:
        verdict = "The resolution passed without your aims in it. Next time, get a clause of yours into the text early."
    elif gained and not red_in:
        verdict = "The text carried your capital's aims, but it failed: with no resolution, nothing changes for anyone."
    elif red_in:
        verdict = "The text crossed your red line, so voting it down was within your instructions."
    else:
        verdict = "Nothing was adopted."
    if (g.get("result") or {}).get("recalled"):
        verdict = "You were recalled for consultations before the summit: your capital lost confidence in what you were agreeing to."
    if g.get("golden") == "broke":
        verdict += " You voted against a text that carried your main aim. Half a loaf is better than none."
    elif g.get("golden") == "kept":
        verdict += " You backed a text that wasn't everything you wanted: that is how the UN makes progress."
    return {"gained": gained, "missing": missing, "red_in": red_in, "passed": passed, "my_vote": f.get("my_vote"),
            "golden": g.get("golden"), "verdict": verdict}


def rival_outcomes(scn: Scenario, g: dict) -> list[dict]:
    f = (g.get("summit") or {}).get("final") or {}
    tags = f.get("tags") or []
    passed = bool(f.get("passed"))
    out = []
    for rv in g["rivals"]:
        got, hit = rv["want"] in tags and passed, rv["block"] in tags and passed
        verdict = "made peace with you, and co-sponsored the merged text" if rv.get("truce") else ("got what it came for" if got and not hit else "won something, and lost something" if got else
                   "lost: its red line is in the resolution" if hit else "went home with nothing")
        out.append({"name": scn.member(rv["iso3"]).name, "style": K.RIVAL_STYLES[rv.get("style", "hawk")]["name"],
                    "want": scn.tags[rv["want"]], "block": scn.tags[rv["block"]], "won": got and not hit, "verdict": verdict})
    return out


# ---------------------------------------------------------------- the deal table and your capital (phase 9)

def _their_clause(scn: Scenario, g: dict, iso: str) -> dict | None:
    """The clause in the draft this delegation likes best: the one a promise to back would mean most to."""
    best = max(g["draft"], key=lambda c: (mu_of(scn, g, iso, c["tags"]), c["id"]), default=None)
    return best if best and mu_of(scn, g, iso, best["tags"]) >= 0.4 else None


def deal_terms(scn: Scenario, g: dict, iso: str) -> dict:
    """What a delegation makes of each item on the deal table: how much it values what you could give, what each
    thing you ask for would cost it, and how your capital would take each part. The page shows these numbers as a
    meter; a proposal is judged by the same numbers."""
    me, them = X.traits(g["iso3"]), X.traits(iso)
    asks = X.asks(iso, g["seed"])
    final = final_clause(g)
    st = {a: stance(scn, g, a, final) for a in ["you", *[r["iso3"] for r in g["rivals"]]]} if final["tags"] else {}
    x = latent(scn, g, iso, final, st, mood=False) if final["tags"] else 0.0
    red = bool(final["tags"]) and red_line(scn, iso, final["tags"])
    clause = _their_clause(scn, g, iso)
    give, cap = {}, {}
    if X.budget(g["iso3"]) - g.get("pledged", 0) > 0:
        give["funding"] = 2.0 + (1.5 if "funding" in asks else 0)
        cap["funding"] = 0
    give["trade"] = 1.5 + (1.5 if "trade" in asks else 0) + 0.25 * (me["size"] - 1)
    cap["trade"] = 0 if me["exporter"] else -1
    if len(g.get("candidacies", [])) < R["candidacy_max"] and iso not in g.get("candidacies", []):
        give["candidacy"] = 1.0 + (2.0 if "candidacy" in asks else 0)
        cap["candidacy"] = 0
    if clause and not any(p["iso3"] == iso and p["kept"] is None for p in g["promises"]):
        give["clause"] = round(1.5 + 0.5 * min(2.0, mu_of(scn, g, iso, clause["tags"])), 2)
        cap["clause"] = -3 if g["mandate"]["red"] in clause["tags"] else 0
    if g["influence"] >= 3:
        give["influence"] = 1.6 + (0.8 if them["low"] or them["aid"] else 0)
        cap["influence"] = 0
    if g["respect"] >= 2:
        give["standing"] = 1.8 + (0.6 if g["respect"] >= 6 else 0)
        cap["standing"] = 0
    get = {}
    if final["tags"] and not red:
        get["yes"] = round(max(0.5, (scn.c_yes - x) * 2.5 + 0.5), 2)
        if x < scn.c_no + 0.2:
            get["abstain"] = round(max(0.3, (scn.c_no - x) * 2.5 + 0.5), 2)
    ln = lean(scn, g, "you", iso)
    if ln >= 0 and iso not in g["sponsors"] and iso not in g["signatories"] and len(g["sponsors"]) < R["sponsors"]:
        get["sponsor"] = round(2.0 + max(0.0, R["sponsor_lean"] - ln) * 2, 2)
    get["influence"] = 2.0 if them["rich"] else 3.5
    if iso not in g.get("favours", []):
        get["favour"] = round(1.5 + max(0.0, -ln), 2)
    if g["respect"] < R["respect_max"]:
        get["standing"] = 2.0 if them["size"] >= 3 else 1.4
    if iso not in g.get("secured", []) and len(g.get("secured", [])) < R["secure_max"] and ln > R["lean_min"]:
        get["commit"] = 1.2
    if any(g.get("intent", {}).values()):
        get["intel"] = 1.0
    return {"asks": asks, "give": give, "get": get, "capital": cap, "bonus": round(0.5 * g["trust"].get(iso, 0), 2),
            "clause": clause["id"] if clause else None, "done": iso in g.get("dealt", []), "red_line": red}


def deal_verdict(score: float) -> str:
    return "delighted" if score >= 1.5 else "accept" if score >= 0 else "more" if score >= -1.5 else "refuse"


CAPITAL_WHY = {"trade": "You opened our market without asking us. Our producers are furious.",
               "clause": "You promised to back a clause that crosses our red line. That is not what we sent you to do."}


def _deal_vote(scn: Scenario, g: dict, iso: str, clause: dict, vote: str) -> str:
    """A delegation keeps its deal on the whole text, unless the text crosses its own red line."""
    dv = (g.get("deal_votes") or {}).get(iso)
    if not dv or clause.get("id") != "final" or red_line(scn, iso, clause["tags"]):
        return vote
    return "yes" if dv == "yes" else ("abstain" if vote == "no" else vote)


def _capital(scn: Scenario, g: dict, delta: int, why: str) -> None:
    """Your capital's view of you moves your Standing (one meter since 6 Nov 2026: the room's respect and your
    government's confidence together). A telegram says why; at zero you are recalled (see `apply`)."""
    before = g["respect"]
    g["respect"] = max(0, min(R["respect_max"], before + delta))
    g["capital"] = g["respect"]
    mood = "approve" if delta > 0 else "furious" if delta <= -2 else "grumble"
    _log(g, "capital", why, "telegram")
    g["log"][-1]["mood"] = mood
    if g["respect"] <= 0 < before:
        _recall(scn, g)
    elif 0 < g["respect"] <= 1 < before:
        _log(g, "capital", "One more step like that and you will be recalled for consultations.", "telegram")
        g["log"][-1]["mood"] = "furious"


def _recall(scn: Scenario, g: dict) -> None:
    if g["difficulty"] == "hard":
        _log(g, "capital", "You are recalled for consultations. A new ambassador will take your seat: your session ends here.", "telegram")
        g["log"][-1]["mood"] = "furious"
        g["phase"] = "done"
        g["result"] = {"passed": False, "statement": False, "recalled": True, "paths": {p: 0 for p in K.PATHS},
                       "chosen": g["path"], "grade": 0, "share_yes": 0.0, "own_text": 0.0, "whip_right": 0, "whip_judged": 0,
                       "broken_promises": sum(1 for p in g["promises"] if p["kept"] is False), "kept_promises": 0,
                       "endorsements": sum(1 for v in g["endorse"].values() if v == "you"), "respect": g["respect"],
                       "expertise": g["expertise"]}
    else:
        g["recall"] = 1
        g["respect"] = g["capital"] = max(g["respect"], 2)
        _log(g, "capital", "You are recalled for consultations: you'll spend your next turn in the capital, explaining yourself.", "telegram")
        g["log"][-1]["mood"] = "furious"


def _capital_chapter(scn: Scenario, g: dict, met: bool) -> None:
    """At the end of each chapter your capital judges your progress: the goal, and what's in the draft."""
    tags = {t for c in g["draft"] for t in c["tags"]}
    m = g["mandate"]
    delta, notes = (1, ["Good work: the breakthrough is made."]) if met else (-1, ["The deadline passed without a breakthrough."])
    if m["red"] in tags:
        delta -= 1
        notes.append("Our red line is in the draft. Get it out.")
    elif m["must"] in tags and met:
        notes.append("And our main aim is in the text.")
    elif m["must"] not in tags and g["chapter"] >= 2:
        delta -= 1
        notes.append("Where is our clause? Our main aim is not in the draft.")
    _capital(scn, g, max(-2, min(2, delta)), " ".join(notes))


# ---------------------------------------------------------------- stages, breakthroughs and a growing delegation (phase 11)

def stage_names(g: dict) -> dict:
    return K.STAGES_QUICK if g["length"] == "quick" else K.STAGES


def checklist(scn: Scenario, g: dict) -> list[dict]:
    """The current stage's breakthrough, item by item, as the Brief and the stage track show it."""
    mine = sum(1 for c in g["draft"] if c["author"] == "you")
    endorsed = sum(1 for r, v in g["endorse"].items() if v == "you" and (g["length"] == "quick" or r not in g.get("endorse_start", [])))
    need_groups = 2 if g["length"] == "full" else 1
    signers = len(g["sponsors"]) + len(g["signatories"])
    passes = projection(scn, g)["passed"]
    items = {
        1: [("Five clauses in the draft", len(g["draft"]) >= 5, f"{len(g['draft'])} of 5"),
            ("Two of them yours", mine >= 2, f"{mine} of 2"),
            ("Your capital's main aim in the text", g["mandate"]["must"] in {t for c in g["draft"] for t in c["tags"]},
             "yes" if g["mandate"]["must"] in {t for c in g["draft"] for t in c["tags"]} else "not yet"),
            ("The whole text would pass as it stands", passes, "yes" if passes else "not yet")],
        2: [(f"{'Two regional groups newly endorse' if need_groups == 2 else 'A regional group newly endorses'} your draft", endorsed >= need_groups,
             f"{endorsed} of {need_groups}")],
        3: [(f"{R['sponsors']} sponsors", len(g["sponsors"]) >= R["sponsors"], f"{len(g['sponsors'])} of {R['sponsors']}"),
            ("Enough sponsors and signatories to table it", signers >= _signers_needed(scn), f"{signers} of {_signers_needed(scn)}")],
    }
    stages = [1, 2, 3] if g["length"] == "quick" else [g["chapter"]]
    return [{"label": a, "done": b, "count": c} for s in stages for a, b, c in items[s]]


def _objective(scn: Scenario, g: dict) -> bool:
    return all(x["done"] for x in checklist(scn, g))


def _check_breakthrough(scn: Scenario, g: dict) -> bool:
    """The first time a stage's breakthrough is met it's recorded (and stays met): the player may move on at once."""
    if g["phase"] != "chapter" or g["turn"] < MIN_STAGE_TURNS or str(g["chapter"]) in g.setdefault("breakthroughs", {}) or not _objective(scn, g):
        return False
    g["breakthroughs"][str(g["chapter"])] = g["turn"]
    st = stage_names(g)[g["chapter"]]
    _log(g, "news", f"Breakthrough: {st['breakthrough']}. {st['unlocks']}", "breakthrough")
    return True


def ap_sources(scn: Scenario, g: dict) -> list[dict]:
    """Where this turn's actions come from, like resources and units in Civ: a bigger, more experienced, more respected
    delegation has more to do as the session nears its end. `next` says how to earn the next one."""
    stars = sum(a["stars"] for a in g.get("staff", []))
    xp, rs = g.get("expertise", 0), g["respect"]
    mine = sum(1 for v in g["endorse"].values() if v == "you")
    quick = g["length"] == "quick"
    stage_n = 0 if quick else {1: 0, 2: 1, 3: 2}.get(g["chapter"], 0)
    return [
        {"code": "base", "name": "Your delegation", "n": R["ap_base"], "next": None},
        {"code": "stage", "name": "Stage reached", "n": stage_n,
         "next": None if quick or stage_n >= 2 else ("+1 from Bloc meetings, +2 from Sponsors" if stage_n == 0 else "+2 from Sponsors")},
        {"code": "staff", "name": "Your staff", "n": stars // 4,
         "next": f"{4 - stars % 4} more adviser star{'s' if 4 - stars % 4 != 1 else ''} (hire or promote) for another"},
        {"code": "experience", "name": "Your staff's know-how", "n": (xp >= 5) + (xp >= 10),
         "next": "know-how 5 (read files, answer procedure)" if xp < 5 else "know-how 10" if xp < 10 else None},
        {"code": "respect", "name": "Standing", "n": (rs >= 5) + (rs >= 8),
         "next": "Standing 5" if rs < 5 else "Standing 8" if rs < 8 else None},
        {"code": "coalition", "name": "Coalition", "n": 1 if mine >= 2 else 0,
         "next": None if mine >= 2 else "two regional groups endorsing your draft"},
    ] + ([{"code": "approach", "name": "The Veteran's caution", "n": -1, "next": "it passes after your first three turns"}]
         if g.get("approach") == "veteran" and g["chapter"] == 1 and g["turn"] <= 3 else [])


def _meeting(scn: Scenario, g: dict) -> None:
    """In Bloc meetings (and in a Quick session) one regional group meets each turn, in turn."""
    g["meeting"] = None
    if not (g["length"] == "quick" or g["chapter"] == 2):
        return
    regions = sorted(r for r in {m.region for m in scn.members if m.region in REGIONS}
                     if sum(1 for i in _region_members(scn, r) if i not in _others(g)) >= 2)
    if not regions:
        return
    start = random.Random(f"{g['seed']}:meet").randrange(len(regions))
    reg = regions[(start + g["turn"] - 1) % len(regions)]
    g["meeting"] = reg
    _log(g, "news", f"The {REGIONS[reg]} meets this turn. You can attend.", "meeting")


def a_attend(scn, g, a):
    reg = g.get("meeting")
    if not reg:
        raise GameError("No regional group is meeting this turn.")
    if g.get("attended") == g.get("tick"):
        raise GameError(f"You've already attended the {REGIONS[reg]} this turn.")
    _spend(g, 1, R["attend_cost"])
    g["attended"] = g.get("tick")
    for iso in _region_members(scn, reg):
        if iso not in _others(g):
            _sway(g, "you", iso, R["attend_step"])
    g["region_last"][reg] = "you"
    _log(g, "you", f"You attended the meeting of the {REGIONS[reg]}.", "action")
    return {}


def a_overtime(scn, g, a):
    n = g.get("overtime", 0)
    if n >= len(R["overtime"]):
        raise GameError("Your staff can't work any later this turn.")
    _spend(g, 0, R["overtime"][n])
    g["overtime"] = n + 1
    g["ap"] += 1
    _log(g, "you", f"Your staff worked late: one more action for {R['overtime'][n]} Influence.", "action")
    return {}


def a_advance(scn, g, a):
    """Move on now: the breakthrough is met, and every turn left becomes momentum."""
    if str(g["chapter"]) not in g.get("breakthroughs", {}):
        raise GameError("Meet this stage's breakthrough first.")
    left = max(0, turns_now(g) - g["turn"])
    skipped = left * sum(x["n"] for x in ap_sources(scn, g)) + max(0, g.get("ap", 0))
    g["ap_given"] = g.get("ap_given", 0) + left * sum(x["n"] for x in ap_sources(scn, g))
    g["ap_unused"] = g.get("ap_unused", 0) + skipped                        # moving on early: time you didn't spend on the job
    g["respect"] = min(R["respect_max"], g["respect"] + R["momentum_respect"])
    g["influence"] += R["momentum_influence"] * left
    g["momentum"] = g.get("momentum", 0) + left
    _log(g, "you", f"You moved on with {left} turn{'s' if left != 1 else ''} in hand: +{R['momentum_respect']} Standing, "
                   f"+{R['momentum_influence'] * left} Influence. Rivals lose those turns too.", "good")
    g["offers"] = []
    _endorsements(scn, g)
    _end_stage(scn, g, early=True)
    return {"advanced": True, "turns_left": left}


def a_stay(scn, g, a):
    if str(g["chapter"]) not in g.get("breakthroughs", {}):
        raise GameError("There's no breakthrough to decide on yet.")
    g.setdefault("stayed", {})[str(g["chapter"])] = True
    return {}


def _end_stage(scn: Scenario, g: dict, early: bool = False) -> None:
    """A stage ends at its breakthrough (if you move on) or at its deadline. Missing the breakthrough costs Standing,
    and your capital judges the stage."""
    L = LENGTHS[g["length"]]
    met = str(g["chapter"]) in g.get("breakthroughs", {}) or _objective(scn, g)
    g["objectives"][str(g["chapter"])] = met
    if met:
        g["influence"] += R["objective_influence"]
    name = stage_names(g)[g["chapter"]]["name"]
    _log(g, "you", f"{name}: " + ("breakthrough made." if met else "the deadline passed without a breakthrough; the Chair moves on."),
         "objective")
    settle_bargains(scn, g)
    _capital_chapter(scn, g, met)
    if g["chapter"] in g.get("vows", []) and g["mandate"]["must"] not in {t for c in g["draft"] for t in c["tags"]}:
        _capital(scn, g, -2, "You told me you'd deliver our main aim this stage. You didn't.")
    if g["phase"] == "done":
        return
    if g["chapter"] < L["chapters"]:
        g["chapter"] += 1
        g["turn"] = 1
        _open_chapter(scn, g)
        _start_turn(scn, g)
        return
    g["tabled_first"] = bool(met) if g["length"] == "quick" or g["chapter"] == 3 else None
    _open_summit(scn, g)


from app.modules.sim.campaign import talks as T  # noqa: E402  (talks uses the engine's primitives above)
from app.modules.sim.campaign import visits as V  # noqa: E402
from app.modules.sim.campaign import summit as SM  # noqa: E402  (the Summit as the UN runs it, D-102)


def a_mark(scn, g, a):
    """The whip sheet: note how you think a delegation will vote on a clause (or on the final text). Free."""
    iso, col, vote = a.get("iso3"), a.get("clause") or "final", a.get("vote")
    if not scn.member(iso) or iso == g["iso3"]:
        raise GameError("Choose another delegation.")
    if vote not in (*VOTES, None, ""):
        raise GameError("Mark yes, no, abstain, or clear it.")
    if col == "final":
        if vote:
            g["whip"][iso] = vote
        else:
            g["whip"].pop(iso, None)
        return {}
    if not any(c["id"] == col for c in g["draft"]):
        raise GameError("That clause isn't in the draft.")
    sheet = g.setdefault("sheet", {}).setdefault(col, {})
    if vote:
        sheet[iso] = vote
    else:
        sheet.pop(iso, None)
    return {}

CHAPTER = {"lobby": T.a_lobby, "talk": T.a_talk, "read": a_read, "propose": a_propose, "amend": a_amend, "strike": a_strike, "promise": a_promise,
           "whip": a_whip, "sign": a_sign, "answer": a_answer,
           "divide": a_divide, "merge": a_merge, "abstain": a_abstain, "offer": a_offer,
           "hire": a_hire, "post": a_post, "reserve": a_reserve, "deal": T.a_deal, "compromise": T.a_compromise, "visit": V.a_visit, "mark": a_mark,
           "attend": a_attend, "advance": a_advance, "stay": a_stay, "end_turn": a_end_turn}
SUMMIT = {"speech": SM.s_speech, "proceed": SM.s_proceed, "caucus": SM.s_caucus, "table": SM.s_table, "debate": SM.s_debate,
          "amend_vote": SM.s_amend_vote, "final": s_final, "statement": s_statement, "post": a_post,
          "mark": a_mark}


# ---------------------------------------------------------------- the debrief (phase 6)

WORD = {2: "strongly for", 1: "for", 0: "undecided", -1: "against", -2: "strongly against"}


def debrief(scn: Scenario, g: dict) -> dict:
    """Why each delegation voted as it did on the final resolution, how much of that was your doing, and what to try
    next time. Every number here is the game's own: the model's position on the final text, the goodwill you and the
    rivals built, a regional group's endorsement, and the delegation's hidden mood on the day (the vote's real
    uncertainty)."""
    s = g.get("summit") or {}
    f = s.get("final") or {}
    tags = f.get("tags") or []
    res = g.get("result") or {}
    total = sum(res.get("paths", {}).values())
    out = {"countries": [], "turned": [], "lost": [], "tips": tips(scn, g), "clauses": [], "promises": [], "struck": [],
           "rank": rank(total), "points": total, "history": g.get("history", []), "moments": moments(scn, g)}
    draft = {c["id"]: c for c in g["draft"]}
    for r in s.get("results", []):
        c = draft.get(r["clause"], {})
        who = c.get("author", "draft")
        out["clauses"].append({"labels": [scn.tags[t] for t in r["tags"]], "passed": r["passed"], "summary": r["summary"],
                               "text": c.get("text", ""), "yes": r["yes"], "no": r["no"], "abstain": r["abstain"],
                               "owner": "you" if who == "you" else ("draft" if who == "draft" else "rival"),
                               "owner_name": "You" if who == "you" else ("The original draft" if who == "draft" else scn.member(who).name),
                               "amended": [("you" if a == "you" else scn.member(a).name) for a in c.get("amended_by", [])]})
    for pr in g["promises"]:
        out["promises"].append({"country": scn.member(pr["iso3"]).name, "kept": pr["kept"]})
    for c in g["struck"]:
        out["struck"].append({"labels": [scn.tags[t] for t in c["tags"]], "by": "you" if c["by"] == "you" else scn.member(c["by"]).name})
    out["half_loaf"] = half_loaf(scn, g)
    out["stages"] = {"made": sum(1 for v in g.get("objectives", {}).values() if v), "of": LENGTHS[g["length"]]["chapters"],
                     "momentum": g.get("momentum", 0)}
    out["capital"] = {"confidence": g["respect"], "of": R["respect_max"], "deals": g.get("deals", 0),
                      "recalled": bool((g.get("result") or {}).get("recalled"))}
    out["rivals"] = rival_outcomes(scn, g)
    out["ledger"] = T.ledger(scn, g)
    out["staff"] = [{"name": a["name"], "kind": K.STAFF_KINDS[a["kind"]]["name"], "stars": a["stars"], "xp": a["xp"]} for a in g.get("staff", [])]
    if not tags:
        return out
    final = {"id": "final", "tags": tags, "author": "draft"}
    st = {a: stance(scn, g, a, final) for a in ["you", *[r["iso3"] for r in g["rivals"]]]}
    st["you"] = {"yes": 1, "no": -1, "abstain": 0}[f.get("my_vote") or "abstain"]
    for m in scn.members:
        iso = m.iso3
        if iso == g["iso3"] or iso in st:
            continue
        mu, sigma = scn.dist(tags).get(iso, (0.0, 1.5))
        mood = sigma * g["moods"].get(iso, 0.0)
        yours = g["sway"]["you"].get(iso, 0.0) * st["you"]
        theirs = sum(g["sway"][r["iso3"]].get(iso, 0.0) * st[r["iso3"]] for r in g["rivals"])
        owner = g["endorse"].get(m.region)
        group = R["endorse_pull"] * st.get(owner, 0) if owner else 0.0
        group_yours = group if owner == "you" else 0.0
        actual = f["votes"].get(iso)
        without = vote_of(scn, mu + mood + theirs + (group - group_yours))
        pos = [scn.positions.get(iso, {}).get(t) for t in tags if scn.positions.get(iso, {}).get(t) is not None]
        stated = round(sum(pos) / len(pos)) if pos else None
        row = {"iso3": iso, "name": m.name, "vote": actual, "stated": WORD.get(stated) if stated is not None else "not recorded",
               "model": round(mu, 2), "mood": round(mood, 2), "yours": round(yours, 2), "rivals": round(theirs, 2),
               "group": round(group, 2), "group_owner": "you" if owner == "you" else (scn.member(owner).name if owner else None),
               "without_you": without, "turned": without != actual, "predicted": g["whip"].get(iso),
               "pledged": iso in g.get("pledges", []), "sources": scn.sources.get(iso, [])}
        row["right"] = None if row["predicted"] is None else row["predicted"] == actual
        out["countries"].append(row)
        if row["turned"]:
            better = {"no": 0, "abstain": 1, "yes": 2}
            (out["turned"] if (better[actual] - better[without]) * (st["you"] or 1) > 0 else out["lost"]).append(m.name)
    out["countries"].sort(key=lambda r: (not r["turned"], r["name"]))
    return out


RANKS = [(0, "Attaché"), (2, "Third Secretary"), (4, "Second Secretary"), (6, "First Secretary"), (8, "Counsellor"),
         (10, "Ambassador"), (12, "Special Envoy of the Secretary-General")]


def rank(points: int) -> dict:
    """A diplomatic rank from the four grades together (0 to 12), and how far it is to the next."""
    name, nxt = RANKS[0][1], None
    for i, (need, title) in enumerate(RANKS):
        if points >= need:
            name = title
            nxt = RANKS[i + 1] if i + 1 < len(RANKS) else None
    return {"name": name, "points": points, "next": nxt[1] if nxt else None, "to_next": (nxt[0] - points) if nxt else 0}


def moments(scn: Scenario, g: dict) -> list[dict]:
    """The session's turning points, from the record."""
    keep = []
    for e in g["log"]:
        t = e["text"]
        if e["kind"] == "endorse" and "your draft" in t:
            keep.append({"when": e["when"], "text": t, "kind": "good"})
        elif e["kind"] == "endorse":
            keep.append({"when": e["when"], "text": t, "kind": "bad"})
        elif e["kind"] == "objective":
            keep.append({"when": e["when"], "text": t, "kind": "good" if "met" in t else "bad"})
        elif e["kind"] == "warning" and "promise" in t:
            keep.append({"when": e["when"], "text": t, "kind": "bad"})
        elif e["kind"] == "rival" and "struck" in t and "kept it" not in t:
            keep.append({"when": e["when"], "text": t, "kind": "bad"})
        elif e["kind"] == "learn" and t.startswith("You unlocked"):
            keep.append({"when": e["when"], "text": t, "kind": "good"})
        elif e["kind"] == "vote":
            keep.append({"when": e["when"], "text": t, "kind": "good" if "adopted" in t.lower() or "agreed" in t else "bad"})
    return keep[-12:]


def tips(scn: Scenario, g: dict) -> list[dict]:
    """What would have earned a better grade on each path, from what actually happened."""
    r = g.get("result") or {}
    paths = r.get("paths", {})
    f = (g.get("summit") or {}).get("final") or {}
    tags = f.get("tags") or []
    must, also, red = g["mandate"]["must"], g["mandate"].get("also"), g["mandate"]["red"]
    out = []
    m = []
    if must not in tags:
        m.append(f"get “{scn.tags[must].lower()}” into a clause that passes")
    if also and also not in tags:
        m.append(f"also get “{scn.tags[also].lower()}” in")
    if red in tags:
        m.append(f"keep “{scn.tags[red].lower()}” out, by amending it away or voting its clause down")
    if not f.get("passed"):
        m.append("make sure the resolution as a whole passes")
    out.append({"path": "mandate", "grade": paths.get("mandate", 0), "next": m or ["nothing: every instruction was met"]})
    share, ends = r.get("share_yes", 0), r.get("endorsements", 0)
    c = []
    if not f.get("passed"):
        c.append("pass the resolution first")
    if share < 0.75:
        c.append(f"win more yes votes ({round(share * 100)}% voted yes; gold needs 75%)")
    if ends < 2:
        c.append(f"win the endorsement of more regional groups ({ends} now; gold needs 2): side events and lobbying in one group")
    out.append({"path": "consensus", "grade": paths.get("consensus", 0), "next": c or ["nothing: you had the room with you"]})
    own = r.get("own_text", 0)
    a = []
    if own < R["architect_gold"]:
        a.append(f"shape more of the final text ({round(own * 100)}% was yours or amended by you; gold needs half, with three clauses of your own)")
    if not f.get("passed"):
        a.append("your clauses only count in a resolution that passes")
    out.append({"path": "architect", "grade": paths.get("architect", 0), "next": a or ["nothing: the text was yours"]})
    k = []
    judged, right = r.get("whip_judged", 0), r.get("whip_right", 0)
    if judged < 4:
        k.append(f"predict more delegations' final votes ({judged} judged; at least {min(5, max(3, len(scn.members) // 4))} needed)")
    elif right / max(1, judged) < 0.8:
        k.append(f"read the room more closely ({right} of {judged} right; gold needs 80%): read files before predicting")
    if r.get("broken_promises"):
        k.append("keep every promise: vote yes on the clauses you promised to back")
    if r.get("respect", 0) < 7:
        k.append(f"build Standing ({r.get('respect', 0)} now; gold needs 7): answer procedure moments, keep promises, accept friendly amendments")
    out.append({"path": "kingmaker", "grade": paths.get("kingmaker", 0), "next": k or ["nothing: you read the room and kept your word"]})
    used, engaged = diligence(scn, g)
    am = []
    if used < 0.9:
        am.append(f"use your time: you left {round((1 - used) * 100)}% of your actions unspent (moving on early counts too)")
    if engaged < 0.6:
        am.append(f"talk to more of the room: you engaged {round(engaged * 100)}% of the delegations")
    out.append({"path": "ambassador", "grade": paths.get("ambassador", 0), "next": am or ["nothing: you did the job you're paid for"]})
    return out
