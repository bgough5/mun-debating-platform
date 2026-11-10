"""The Summit as the UN runs it (Ben, 8 Nov 2026; D-102).

Six steps: position statements -> the draft read in full -> a caucus (moderated or unmoderated) -> amendments, one at a
time, each an edit of the draft that is debated and then voted on -> the final draft read with its changes -> the final
vote by roll call. There are no clause-by-clause votes: as in the General Assembly, the text is amended and then voted
as a whole.

Rules that keep it the climax and not a loop:
- Amendments come from real motives: a rival's red line or wish; a delegation whose own red line is in the text; a
  supporter softening a clause that would fail. At most one per rival, one or two from the rest, five in all, plus the
  ultimatums you refused (g["threats"]) and up to two of your own.
- Once a matter is settled it is closed (`closed`): a commitment added, removed or voted down, a clause struck, a
  clause's verb changed. Nobody can raise it again, so no delegation re-tables the same idea amendment after amendment.
- A point of order succeeds only on a real procedural ground: an amendment that would bring back what the working
  group already struck. Otherwise the Chair rules against you.

The engine imports this module at the end (after its primitives), like talks and visits; import the engine first.
"""
from __future__ import annotations

from app.modules.sim.campaign import content as K
from app.modules.sim.campaign import engine as E

STEPS = ("statements", "reading", "caucus", "amendments", "final_reading", "final")
MAX_AMENDMENTS = 5
MY_AMENDMENTS = 2
LADDER = ["Invites", "Encourages", "Calls upon", "Urges", "Strongly urges"]   # an operative verb, weakest to strongest
BASE = {"Invites": 0, "Encourages": 1, "Welcomes": 1, "Recommends": 1, "Calls upon": 2, "Calls on": 2, "Requests": 2, "Asks": 2,
        "Urges": 3, "Decides": 4, "Strongly urges": 4}


# ---------------------------------------------------------------- opening

def open_summit(scn, g: dict) -> None:
    """Called when the last stage ends: the statements are drafted before the player speaks."""
    g["summit"] = {"step": "statements", "statements": _statements(scn, g), "speech": None, "caucus": None,
                   "queue": [], "cur": None, "stage": None, "debate": None, "done": [], "closed": [], "mine": 0,
                   "po_used": False, "results": [], "final": None, "tracked": [], "my_votes": {}}


def _ensure(scn, g: dict) -> dict:
    """A game saved during the old clause-by-clause summit restarts the new one from the top."""
    s = g["summit"]
    if "closed" not in s and s.get("step") in ("speech", "clause"):
        open_summit(scn, g)
    return g["summit"]


def _view_of(scn, g, iso: str) -> int:
    """How a delegation feels about the draft as it stands: +1 for, -1 against, 0 undecided."""
    final = E.final_clause(g)
    if not final["tags"]:
        return 0
    v = E.vote_of(scn, E.latent(scn, g, iso, final, mood=False))
    return 1 if v == "yes" else -1 if v == "no" else 0


def _statements(scn, g: dict) -> list[dict]:
    """The rivals and the two strongest voices for and against open the debate. Each statement shows where they stand."""
    out = []
    final = E.final_clause(g)
    say = E.VO.statement                                     # each delegation takes the floor in its own register
    for rv in g["rivals"]:
        name = scn.member(rv["iso3"]).name
        if rv.get("truce"):
            out.append({"iso3": rv["iso3"], "name": name, "view": 1,
                        "text": say(scn, g, rv["iso3"], "truce")})
        elif rv["block"] in final["tags"]:
            out.append({"iso3": rv["iso3"], "name": name, "view": -1,
                        "text": say(scn, g, rv["iso3"], "against", x=E._lc(scn.tags[rv['block']]).rstrip('.'))})
        else:
            out.append({"iso3": rv["iso3"], "name": name, "view": 0,
                        "text": say(scn, g, rv["iso3"], "wait", x=E._lc(scn.tags[rv['want']]).rstrip('.'))})
    free = [i for i in scn.isos if i not in E._others(g) and i != g["iso3"]]
    if final["tags"] and free:
        xs = sorted(free, key=lambda i: E.latent(scn, g, i, final, mood=False))
        lo, hi = xs[0], xs[-1]
        out.append({"iso3": hi, "name": scn.member(hi).name, "view": _view_of(scn, g, hi),
                    "text": say(scn, g, hi, "for")})
        if lo != hi:
            out.append({"iso3": lo, "name": scn.member(lo).name, "view": _view_of(scn, g, lo),
                        "text": say(scn, g, lo, "toofar")})
    return out


def s_speech(scn, g, a):
    """Step 1: your position statement (firm rallies your friends, open earns Standing, bridge reaches the undecided)."""
    s = _ensure(scn, g)
    if s["step"] != "statements":
        raise E.GameError("The position statements are over.")
    st = a.get("stance")
    if st not in E.STANCES:
        raise E.GameError("Choose a stance: firm, open or bridge.")
    must = g["mandate"]["must"]
    for iso in scn.isos:
        if iso in E._others(g):
            continue
        mu = scn.dist([must]).get(iso, (0, 1))[0]
        if st == "firm":
            E._sway(g, "you", iso, 0.15 if mu >= 0.4 else -0.05 if mu <= -0.4 else 0)
        elif st == "bridge" and abs(mu) < 0.4:
            E._sway(g, "you", iso, 0.15)
    if st == "open":
        g["respect"] = min(E.R["respect_max"], g["respect"] + 1)
    s["speech"], s["step"] = st, "reading"
    E._log(g, "you", f"You gave a {st} position statement.", "action")
    return {}


def s_proceed(scn, g, a):
    """The President moves the committee on: after the draft is read, and after the final draft is read."""
    s = _ensure(scn, g)
    if s["step"] == "reading":
        s["step"] = "caucus"
    elif s["step"] == "final_reading":
        s["step"] = "final"
        s["results"] = _clause_results(scn, g)
    else:
        raise E.GameError("The President isn't waiting for anything just now.")
    return {}


# ---------------------------------------------------------------- the caucus

def caucus_topics(scn, g) -> list[str]:
    have = {t for c in g["draft"] for t in c["tags"]}
    m = g["mandate"]
    return sorted(have | {m["must"]} | ({m["also"]} if m.get("also") else set()))


def _my_view(g, tag) -> int:
    m = g["mandate"]
    return 1 if tag in (m["must"], m.get("also")) else -1 if tag == m["red"] else 0


def s_caucus(scn, g, a):
    """Step 3. Moderated: you choose a topic and speak in the speakers' list; delegations that share your view on it
    move your way, and each rival speaks too. Unmoderated: a quick word with two delegations on the floor, while each
    rival works one of its own."""
    s = _ensure(scn, g)
    if s["step"] != "caucus":
        raise E.GameError("The committee isn't in caucus.")
    kind = a.get("kind")
    speakers = []
    free = [i for i in scn.isos if i not in E._others(g) and i != g["iso3"]]
    if kind == "moderated":
        tag = a.get("tag")
        if tag not in caucus_topics(scn, g):
            raise E.GameError("Choose a topic for the moderated caucus.")
        view = _my_view(g, tag) or (1 if any(tag in c["tags"] and c["author"] == "you" for c in g["draft"]) else 0)
        moved = 0
        for iso in free:
            mu = E.mu_of(scn, g, iso, [tag])
            if view and mu * view > 0.4:
                E._sway(g, "you", iso, 0.12)
                moved += 1
        speakers.append({"iso3": g["iso3"], "name": scn.member(g["iso3"]).name,
                         "text": f"You spoke on a clause that {E._lc(scn.tags[tag]).rstrip('.')}: " +
                                 (f"{moved} delegation{'s' if moved != 1 else ''} came your way." if moved else
                                  "the room listened politely, but it isn't a topic you can win them on.")})
        for rv in [r for r in g["rivals"] if not r.get("truce")]:
            t = rv["block"] if rv["block"] in {x for c in g["draft"] for x in c["tags"]} else rv["want"]
            for iso in free:
                if E.mu_of(scn, g, iso, [t]) * (-1 if t == rv["block"] else 1) > 0.4:
                    E._sway(g, rv["iso3"], iso, 0.08)
            speakers.append({"iso3": rv["iso3"], "name": scn.member(rv["iso3"]).name,
                             "text": f"spoke {'against' if t == rv['block'] else 'for'} a clause that {E._lc(scn.tags[t]).rstrip('.')}."})
        s["caucus"] = {"kind": "moderated", "tag": tag, "speakers": speakers}
    elif kind == "unmoderated":
        isos = [i for i in dict.fromkeys(a.get("iso3") or []) if i in free][:2]
        if not isos:
            raise E.GameError("Choose one or two delegations to work on the floor.")
        for iso in isos:
            E._sway(g, "you", iso, 0.2)
            speakers.append({"iso3": iso, "name": scn.member(iso).name, "text": "You had a quiet word on the floor."})
        rng = E._rng(g)
        for rv in [r for r in g["rivals"] if not r.get("truce")]:
            pick = [i for i in free if i not in isos]
            if pick:
                iso = rng.choice(pick)
                E._sway(g, rv["iso3"], iso, 0.2)
                speakers.append({"iso3": rv["iso3"], "name": scn.member(rv["iso3"]).name, "text": f"worked {scn.member(iso).name} on the floor."})
        s["caucus"] = {"kind": "unmoderated", "isos": isos, "speakers": speakers}
    else:
        raise E.GameError("Move for a moderated or an unmoderated caucus.")
    s["step"] = "amendments"
    s["queue"] = _table_amendments(scn, g)
    _next(scn, g)
    E._log(g, "you", f"You moved for {'a moderated' if kind == 'moderated' else 'an unmoderated'} caucus.", "action")
    return {"caucus": s["caucus"]}


# ---------------------------------------------------------------- amendments

def _key(am: dict) -> str:
    """The matter an amendment raises: once settled, it is closed."""
    if am["kind"] in ("add", "remove"):
        return "tag:" + am["tag"]
    if am["kind"] == "strike":
        return "strike:" + am["clause"]
    return "force:" + am["clause"]


def _lead(c: dict) -> tuple[str | None, int]:
    """A clause's own operative verb and its rung on the ladder (Calls upon if it opens with no known verb)."""
    for v in sorted(BASE, key=len, reverse=True):
        if c["text"].startswith(v):
            return v, BASE[v]
    return None, 2


def rung(c: dict) -> int:
    return _lead(c)[1] + c.get("force", 0)


def read_as(c: dict) -> str:
    """A clause as it now reads: a softened or strengthened clause opens with its new verb."""
    if not c.get("force"):
        return c["text"]
    v, base = _lead(c)
    new = LADDER[max(0, min(4, base + c["force"]))]
    if v:
        return new + c["text"][len(v):]
    return f"{new}: {c['text'][0].lower()}{c['text'][1:]}"


def _new_id(g) -> str:
    s = g["summit"]
    s["seq"] = s.get("seq", 0) + 1
    return f"am{s['seq']}"


def _describe(scn, g, am: dict) -> str:
    """An amendment as an edit of the draft, as delegates would read it."""
    c = next((x for x in g["draft"] if x["id"] == am["clause"]), None)
    n = (g["draft"].index(c) + 1) if c else "?"
    if am["kind"] == "strike":
        return f"Strike operative clause {n} in its entirety."
    if am["kind"] == "remove":
        return f"In clause {n}, delete the words committing states to: {E._lc(scn.tags[am['tag']]).rstrip('.')}."
    if am["kind"] == "add":
        return f"Add to clause {n} a new sub-clause: “(a) {scn.tags[am['tag']].rstrip('.')};”"
    r = rung(c) if c else 2
    old, new = LADDER[max(0, min(4, r))], LADDER[max(0, min(4, r + (1 if am["kind"] == "strengthen" else -1)))]
    return f"In clause {n}, replace “{old}” with “{new}”."


def _valid(g, am: dict) -> bool:
    s = g["summit"]
    c = next((x for x in g["draft"] if x["id"] == am["clause"]), None)
    if not c or _key(am) in s["closed"]:
        return False
    if am["kind"] == "remove":
        return am["tag"] in c["tags"]
    if am["kind"] == "add":
        return am["tag"] not in {t for x in g["draft"] for t in x["tags"]} and len(c["tags"]) < 3
    if am["kind"] in ("soften", "strengthen"):
        f = c.get("force", 0) + (1 if am["kind"] == "strengthen" else -1)
        return -1 <= f <= 1 and 0 <= _lead(c)[1] + f <= 4
    return True


def _out_of_order(g, am: dict) -> bool:
    """A real procedural ground: the amendment brings back a commitment the working group already struck."""
    struck = {t for c in g.get("struck", []) for t in c.get("tags", [])}
    have = {t for c in g["draft"] for t in c["tags"]}
    return am["kind"] == "add" and am["tag"] in struck and am["tag"] not in have


def _table_amendments(scn, g) -> list[dict]:
    """Who moves which amendment, and why. Rivals first (a refused ultimatum heads the list), then delegations whose
    own red line is in the text, then supporters softening a clause that would fail."""
    s = g["summit"]
    out, seen, movers = [], set(), set()

    def push(am):
        if am["by"] in movers:                                # each delegation moves one amendment at most
            return False
        am = {**am, "id": _new_id(g)}
        if _valid(g, am) and _key(am) not in seen:
            seen.add(_key(am))
            movers.add(am["by"])
            out.append(am)
            return True
        return False

    threats = {t["iso3"]: t["tag"] for t in g.get("threats", [])}
    for rv in [r for r in g["rivals"] if not r.get("truce")]:
        by = rv["iso3"]
        block = threats.get(by, rv["block"])
        c = next((c for c in g["draft"] if block in c["tags"]), None)
        if c and push({"by": by, "kind": "remove" if len(c["tags"]) > 1 else "strike", "clause": c["id"], "tag": block,
                       "threat": by in threats}):
            continue
        host = next((c for c in g["draft"] if c["author"] == by and len(c["tags"]) < 3), None) or \
            next((c for c in g["draft"] if len(c["tags"]) < 3 and c["author"] != "you"), None)
        if host and push({"by": by, "kind": "add", "clause": host["id"], "tag": rv["want"]}):
            continue
        mine = next((c for c in g["draft"] if c["author"] == "you" and g["mandate"]["must"] in c["tags"]), None)
        if mine and rv.get("style") == "spoiler":
            push({"by": by, "kind": "soften", "clause": mine["id"]})
    # the rest of the room: a delegation whose own red line is in the text moves to cut it, and a supporter of a clause
    # that would fail moves to soften it. Only contested amendments come forward (the vote is genuinely in doubt).
    free = [i for i in scn.isos if i not in E._others(g) and i != g["iso3"]]
    cands = []
    for c in g["draft"]:
        for t in c["tags"]:
            worst = min(free, key=lambda i: E.mu_of(scn, g, i, [t]), default=None)
            if worst and E.mu_of(scn, g, worst, [t]) <= E.R["redline"]:
                cands.append({"by": worst, "kind": "remove" if len(c["tags"]) > 1 else "strike", "clause": c["id"], "tag": t})
        margin = _margin(scn, g, c)
        fan = max(free, key=lambda i: E.mu_of(scn, g, i, c["tags"]), default=None)
        if fan and E.mu_of(scn, g, fan, c["tags"]) >= 0.8:
            if margin <= 0:
                cands.append({"by": fan, "kind": "soften", "clause": c["id"]})        # save a clause that would fail
            elif margin >= 6:
                cands.append({"by": fan, "kind": "strengthen", "clause": c["id"]})    # press a clause that is safe
    have = {t for c in g["draft"] for t in c["tags"]}
    hosts = [c for c in g["draft"] if len(c["tags"]) < 3]
    for t in scn.tags:                                        # a commitment missing from the text that someone wants
        if t in have or not hosts:
            continue
        champ = max(free, key=lambda i: E.mu_of(scn, g, i, [t]), default=None)
        if champ and E.mu_of(scn, g, champ, [t]) >= 1.0:
            cands.append({"by": champ, "kind": "add", "clause": hosts[0]["id"], "tag": t})
    scored = []
    for am in cands:
        if not _valid(g, {**am, "id": "x"}):
            continue
        v = amendment_votes(scn, g, {**am, "id": "x"}, "abstain")
        yes, no = sum(x == "yes" for x in v.values()), sum(x == "no" for x in v.values())
        if yes >= no - 3:
            scored.append((abs(yes - no), am))
    rest = 0
    for _, am in sorted(scored, key=lambda x: x[0]):
        if rest >= 3 or len(out) >= MAX_AMENDMENTS:
            break
        if push(am):
            rest += 1
    order = {"strike": 0, "remove": 1, "add": 2, "soften": 3, "strengthen": 4}
    ids = [c["id"] for c in g["draft"]]
    out.sort(key=lambda am: (not am.get("threat"), order[am["kind"]], ids.index(am["clause"]) if am["clause"] in ids else 99))
    return out[:MAX_AMENDMENTS + len(threats)]


def _margin(scn, g, c) -> int:
    """A clause's projected margin (yes minus no) as things stand: below zero, it would fail."""
    votes = E.votes_on(scn, g, c)
    return sum(v == "yes" for v in votes.values()) - sum(v == "no" for v in votes.values())


def amendment_options(scn, g) -> list[dict]:
    """What you could table yourself: take your red line out, put your aims in, strike or soften others' text,
    strengthen your own."""
    s = g["summit"]
    if s.get("step") != "amendments" or s.get("mine", 0) >= MY_AMENDMENTS:
        return []
    m = g["mandate"]
    have = {t for c in g["draft"] for t in c["tags"]}
    opts = []
    for c in g["draft"]:
        if m["red"] in c["tags"]:
            opts.append({"kind": "remove" if len(c["tags"]) > 1 else "strike", "clause": c["id"], "tag": m["red"]})
        if c["author"] not in ("you", "draft") and m["must"] not in c["tags"]:
            opts.append({"kind": "strike", "clause": c["id"]})
        opts.append({"kind": "strengthen" if c["author"] == "you" else "soften", "clause": c["id"]})
    for t in (m["must"], m.get("also")):
        if t and t not in have:
            host = next((c for c in g["draft"] if c["author"] == "you" and len(c["tags"]) < 3), None) or \
                next((c for c in g["draft"] if len(c["tags"]) < 3), None)
            if host:
                opts.append({"kind": "add", "clause": host["id"], "tag": t})
    out, seen = [], set()
    for o in opts:
        am = {"by": "you", **o, "tag": o.get("tag")}
        if _valid(g, am) and _key(am) not in seen and not any(_key(q) == _key(am) for q in s["queue"]):
            seen.add(_key(am))
            out.append({**o, "text": _describe(scn, g, am)})
    return out[:6]


def s_table(scn, g, a):
    """Table one of your own amendments; it joins the end of the list."""
    s = _ensure(scn, g)
    if s["step"] != "amendments":
        raise E.GameError("Amendments are tabled during the amendments.")
    if s.get("mine", 0) >= MY_AMENDMENTS:
        raise E.GameError(f"You may table {MY_AMENDMENTS} amendments at the Summit.")
    pick = next((o for o in amendment_options(scn, g) if o["kind"] == a.get("kind") and o["clause"] == a.get("clause")
                 and o.get("tag") == a.get("tag")), None)
    if not pick:
        raise E.GameError("That amendment isn't in order now.")
    am = {"by": "you", "kind": pick["kind"], "clause": pick["clause"], "tag": pick.get("tag"), "id": _new_id(g)}
    s["queue"].append(am)
    s["mine"] = s.get("mine", 0) + 1
    E._log(g, "you", "You tabled an amendment: " + _describe(scn, g, am), "action")
    if not s.get("cur"):
        _next(scn, g)
    return {"tabled": am["id"]}


def _next(scn, g) -> None:
    """Bring the next amendment that is still in order to the floor, or move to the final reading."""
    s = g["summit"]
    s["cur"], s["stage"], s["debate"] = None, None, None
    while s["queue"]:
        am = s["queue"].pop(0)
        if _valid(g, am):
            s["cur"], s["stage"] = am, "debate"
            return
    if s["step"] == "amendments":
        s["step"] = "final_reading"


def _trial(g, am: dict) -> dict | None:
    """The clause as the amendment would leave it (None if struck)."""
    c = next(x for x in g["draft"] if x["id"] == am["clause"])
    if am["kind"] == "strike" or (am["kind"] == "remove" and c["tags"] == [am["tag"]]):
        return None
    if am["kind"] == "remove":
        return {**c, "tags": [t for t in c["tags"] if t != am["tag"]]}
    if am["kind"] == "add":
        return {**c, "tags": c["tags"] + [am["tag"]]}
    return {**c, "force": c.get("force", 0) + (1 if am["kind"] == "strengthen" else -1)}


def _pref(scn, g, iso, clause) -> float:
    """How much a delegation wants a clause (the mid-point of yes and no if there is no clause)."""
    if clause is None:
        return (scn.c_yes + scn.c_no) / 2
    return E.latent(scn, g, iso, clause, mood=False)


def _my_side(g, am: dict) -> int:
    """Whether the amendment helps your instructions: +1 helps, -1 hurts, 0 neither."""
    m = g["mandate"]
    c = next((x for x in g["draft"] if x["id"] == am["clause"]), {"tags": [], "author": ""})
    if am["kind"] == "add":
        return 1 if am["tag"] in (m["must"], m.get("also")) else -1 if am["tag"] == m["red"] else 0
    if am["kind"] in ("remove", "strike"):
        cut = [am["tag"]] if am["kind"] == "remove" else c["tags"]
        if m["red"] in cut:
            return 1
        return -1 if (m["must"] in cut or m.get("also") in cut or c.get("author") == "you") else 0
    good = m["must"] in c["tags"] or c.get("author") == "you"
    return (1 if good else -1) * (1 if am["kind"] == "strengthen" else -1) if (good or m["red"] in c["tags"]) else 0


def amendment_votes(scn, g, am: dict, my_vote: str, favour: set | None = None) -> dict:
    """Each delegation votes for an amendment if it prefers the clause as amended, against if it prefers it as it is.
    Rivals and you vote by your interests; a delegation that owes you a favour votes with you."""
    c = next(x for x in g["draft"] if x["id"] == am["clause"])
    trial = _trial(g, am)
    out = {}
    for m in scn.members:
        iso = m.iso3
        if iso == g["iso3"]:
            out[iso] = my_vote
            continue
        rv = next((r for r in g["rivals"] if r["iso3"] == iso), None)
        if rv:
            if am["by"] == iso:
                out[iso] = "yes"
                continue
            want = (am["kind"] == "add" and am["tag"] == rv["want"]) or (am["kind"] in ("remove", "strike") and
                   (am.get("tag") == rv["block"] or rv["block"] in c["tags"]))
            hurt = (am["kind"] == "add" and am["tag"] == rv["block"]) or (am["kind"] in ("remove", "strike") and rv["want"] in c["tags"])
            out[iso] = "yes" if want else "no" if hurt else ("yes" if rv.get("truce") and am["by"] == "you" else "abstain")
            continue
        if am["by"] == iso:
            out[iso] = "yes"
            continue
        if favour and iso in favour:
            out[iso] = my_vote
            continue
        d = _pref(scn, g, iso, trial) - _pref(scn, g, iso, c)
        d += 0.25 * g["sway"]["you"].get(iso, 0.0) * {"yes": 1, "no": -1, "abstain": 0}[my_vote]   # your goodwill carries your vote
        out[iso] = "yes" if d > 0.12 else "no" if d < -0.12 else "abstain"
    return out


def s_debate(scn, g, a):
    """The debate on the amendment before the committee. The mover speaks for it; an opponent speaks against. You may
    speak for or against, raise a point of order, claim a right of reply, accept it as friendly (your own clause),
    or stay silent. Then it goes to the vote."""
    s = _ensure(scn, g)
    am = s.get("cur")
    if s["step"] != "amendments" or not am or s["stage"] != "debate":
        raise E.GameError("There's no amendment being debated.")
    choice = a.get("choice", "silent")
    c = next(x for x in g["draft"] if x["id"] == am["clause"])
    trial = _trial(g, am)
    free = [i for i in scn.isos if i not in E._others(g) and i != g["iso3"]]
    out = {"amendment": am["id"]}
    speeches = []
    mover = scn.member(am["by"]).name if am["by"] != "you" else "You"
    speeches.append({"who": am["by"], "name": mover, "side": "for"})
    if choice == "point_of_order":
        if "point_of_order" not in g["skills"]:
            raise E.GameError("A point of order needs the skill (a senior legal adviser brings it).")
        if s["po_used"]:
            raise E.GameError("You've already raised your point of order at this Summit.")
        s["po_used"] = True
        if _out_of_order(g, am):
            s["closed"].append(_key(am))
            s["done"].append({**am, "result": "out of order", "text": _describe(scn, g, am)})
            g["respect"] = min(E.R["respect_max"], g["respect"] + 1)
            E._log(g, "you", "Point of order: the Chair rules the amendment out of order. The working group struck that commitment.", "good")
            out["ruled"] = "out of order"
            _next(scn, g)
            return out
        g["respect"] = max(0, g["respect"] - 1)
        E._log(g, "you", "Point of order: the Chair rules against you. The amendment is in order.", "warning")
        out["ruled"] = "in order"
    if choice == "accept":
        if c["author"] != "you" or _my_side(g, am) < 0:
            raise E.GameError("Only a clause's sponsor can accept an amendment as friendly, and not one that cuts its own aims.")
        s["done"].append({**am, "result": "accepted as friendly", "text": _describe(scn, g, am)})
        _apply(scn, g, am, adopted_by="friendly")
        g["respect"] = min(E.R["respect_max"], g["respect"] + 1)
        if am["by"] != "you":
            g["trust"][am["by"]] = min(E.R["trust_max"], g["trust"].get(am["by"], 0) + 1)
        E._log(g, "you", "You accepted the amendment as friendly: it is adopted without a vote.", "good")
        out["accepted"] = True
        _next(scn, g)
        return out
    if choice in ("for", "against"):
        side = 1 if choice == "for" else -1
        for iso in free:
            d = _pref(scn, g, iso, trial) - _pref(scn, g, iso, c)
            if d * side > 0.1:
                E._sway(g, "you", iso, 0.08)
        speeches.append({"who": "you", "name": "You", "side": choice})
    replied = False
    if choice == "reply":
        if am["by"] == "you" or c["author"] != "you":
            raise E.GameError("A right of reply answers an attack on your own text.")
        if g["respect"] < E.R["reply_respect"]:
            raise E.GameError(f"The Chair grants a right of reply to delegates with Standing {E.R['reply_respect']} or more.")
        replied = True
        speeches.append({"who": "you", "name": "You", "side": "reply"})
        E._log(g, "you", f"You exercised your right of reply to {mover}.", "action")
    if am["by"] != "you" and not replied:                    # the mover's speech carries the waverers
        for iso in free:
            if abs(_pref(scn, g, iso, c) - (scn.c_yes + scn.c_no) / 2) < 0.6:
                E._sway(g, am["by"], iso, 0.06) if am["by"] in g["sway"] else None
    against = next((r["iso3"] for r in g["rivals"] if r["iso3"] != am["by"] and amendment_votes(scn, g, am, "abstain").get(r["iso3"]) == "no"), None)
    if against and choice != "against":
        speeches.append({"who": against, "name": scn.member(against).name, "side": "against"})
    s["debate"] = {"choice": choice, "speeches": speeches}
    s["stage"] = "vote"
    return out


def s_amend_vote(scn, g, a):
    """The vote on the amendment. A last offer (Influence) moves the nearest waverer; a favour owed votes with you."""
    s = _ensure(scn, g)
    am = s.get("cur")
    if s["step"] != "amendments" or not am or s["stage"] != "vote":
        raise E.GameError("There's no amendment to vote on.")
    my_vote = a.get("vote")
    if my_vote not in E.VOTES:
        raise E.GameError("Vote on the amendment: yes, no or abstain.")
    favour = set()
    if a.get("extra") == "favour":
        if not g["favours"]:
            raise E.GameError("No one owes you a favour.")
        favour = {g["favours"].pop(0)}
    elif a.get("extra") == "offer":
        E._spend(g, 0, E.R["offer_cost"])
        want = {"yes": "yes", "no": "no"}.get(my_vote)
        if want:
            trial_votes = amendment_votes(scn, g, am, my_vote)
            cands = [i for i, v in trial_votes.items() if v != want and i not in E._others(g) and i != g["iso3"]]
            if cands:
                c = next(x for x in g["draft"] if x["id"] == am["clause"])
                iso = min(cands, key=lambda i: abs(_pref(scn, g, i, _trial(g, am)) - _pref(scn, g, i, c)))
                favour.add(iso)
    had = {"favours": len(g["favours"]) + (1 if a.get("extra") == "favour" else 0),
           "influence": g["influence"] + (E.R["offer_cost"] if a.get("extra") == "offer" else 0)}
    votes = amendment_votes(scn, g, am, my_vote, favour)
    res = E.tally(scn.rule, votes, len(votes))
    text = _describe(scn, g, am)                              # as it reads before the edit
    side = _my_side(g, am) if am["by"] != "you" else 1
    _settle_word(scn, g, am, my_vote)
    if res.passed:
        _apply(scn, g, am, adopted_by="vote")
    s["closed"].append(_key(am))
    s["done"].append({**am, "result": "adopted" if res.passed else "rejected", "text": text, "my_vote": my_vote,
                      "yes": res.yes, "no": res.no, "abstain": res.abstain, "side": side, "extra": a.get("extra"),
                      "spoke": (s.get("debate") or {}).get("choice"), "had": had,
                      "veto": bool(scn.rule.veto) and any(votes.get(p) == "no" for p in scn.rule.veto)})
    s["my_votes"][am["id"]] = my_vote
    who = "your" if am["by"] == "you" else scn.member(am["by"]).name + "'s"
    E._log(g, "news", f"The amendment ({who}) is {'adopted' if res.passed else 'rejected'}: {res.summary}.", "vote")
    _next(scn, g)
    return {"passed": res.passed, "summary": res.summary, "votes": votes, "amendment": "adopted" if res.passed else "rejected"}


def _settle_word(scn, g, am, my_vote) -> None:
    """Voting for an amendment that cuts what you promised (a clause, a pact, a peace) is a betrayal."""
    if my_vote != "yes" or am["kind"] not in ("remove", "strike"):
        return
    c = next(x for x in g["draft"] if x["id"] == am["clause"])
    cut = set(c["tags"]) if am["kind"] == "strike" or c["tags"] == [am["tag"]] else {am["tag"]}
    for p in g["promises"]:
        if p["clause"] == c["id"] and p["kept"] is None:
            p["kept"] = False
            E._betray(scn, g, p["iso3"], "you promised to back that clause, then voted to cut it.")
    for p in g.get("pacts", []):
        if p["kept"] is None and p["tag"] in cut:
            p["kept"] = False
            E._betray(scn, g, p["iso3"], "you agreed not to stand against its clause, then voted to cut it.")
    for rv in g["rivals"]:
        if rv.get("truce") and rv.get("truce_want") in cut:
            E._betray(scn, g, rv["iso3"], "you made peace on its wish, then voted to cut it.")


def _apply(scn, g, am, adopted_by: str) -> None:
    """Make the edit, record it as a tracked change, and close the matter."""
    s = g["summit"]
    c = next(x for x in g["draft"] if x["id"] == am["clause"])
    by = am["by"]
    before = list(c["tags"])
    text = _describe(scn, g, am)                              # as it reads before the edit
    if am["kind"] == "strike" or (am["kind"] == "remove" and c["tags"] == [am["tag"]]):
        E._break_promises_if_changed(scn, g, c, None, actor=by)
        g["draft"].remove(c)
        g.setdefault("struck", []).append({**c, "by": by})
    elif am["kind"] == "remove":
        new = [t for t in c["tags"] if t != am["tag"]]
        E._break_promises_if_changed(scn, g, c, new, actor=by)
        E._hist(scn, g, c, by, "amended at the Summit: removed " + E._lc(scn.tags[am["tag"]]).rstrip("."), new)
        c["tags"] = new
    elif am["kind"] == "add":
        E._hist(scn, g, c, by, "amended at the Summit: added " + E._lc(scn.tags[am["tag"]]).rstrip("."), c["tags"] + [am["tag"]])
        c["tags"] = c["tags"] + [am["tag"]]
    else:
        c["force"] = c.get("force", 0) + (1 if am["kind"] == "strengthen" else -1)
    if by != "you" and by not in c.get("amended_by", []) and c in g["draft"]:
        c.setdefault("amended_by", []).append(by)
    if by == "you" and c in g["draft"] and c["author"] != "you" and "you" not in c.get("amended_by", []):
        c.setdefault("amended_by", []).append("you")
    s["tracked"].append({"clause": am["clause"], "kind": am["kind"], "tag": am.get("tag"), "by": by, "how": adopted_by,
                         "text": text, "before": before})


def _clause_results(scn, g) -> list[dict]:
    """How each delegation would vote on each clause as finally amended (it scores the whip sheet's clause columns)."""
    out = []
    for c in g["draft"]:
        votes = E.votes_on(scn, g, c)
        res = E.tally(scn.rule, votes, len(votes))
        out.append({"clause": c["id"], "tags": list(c["tags"]), "passed": True, "yes": res.yes, "no": res.no,
                    "abstain": res.abstain, "votes": votes, "summary": res.summary})
    return out


def settle_final(scn, g, my_vote: str) -> None:
    """At the final vote: a promise is kept if its clause is in the text and you vote for it; void if others struck it."""
    ids = {c["id"] for c in g["draft"]}
    for p in g["promises"]:
        if p["kept"] is None:
            if p["clause"] not in ids:
                p["kept"] = "void"
            else:
                p["kept"] = my_vote == "yes"
                if p["kept"]:
                    g["respect"] = min(E.R["respect_max"], g["respect"] + 1)
                else:
                    g["trust"][p["iso3"]] = max(-E.R["trust_max"], g["trust"][p["iso3"]] - 2)
                    g["respect"] = max(0, g["respect"] - 1)
    tags = {t for c in g["draft"] for t in c["tags"]}
    for pa in g.get("pacts", []):
        if pa["kept"] is None:
            pa["kept"] = True if pa["tag"] in tags or my_vote != "no" else False


def replay(scn, g) -> dict | None:
    """The Summit, replayed: what happened at each step, the numbers, and what you could have done better."""
    s = g.get("summit")
    if not s or "closed" not in s:
        return None
    names = {m.iso3: m.name for m in scn.members}
    who = lambda x: "You" if x == "you" else names.get(x, x)
    steps, lessons = [], []
    steps.append({"kind": "statement", "text": f"You gave a {s.get('speech') or 'short'} position statement."})
    cu = s.get("caucus") or {}
    if cu.get("kind") == "moderated":
        steps.append({"kind": "caucus", "text": f"You moved for a moderated caucus on a clause that {E._lc(scn.tags[cu['tag']]).rstrip('.')}."})
        if _my_view(g, cu["tag"]) == 0:
            lessons.append("Your caucus topic wasn't one of your instructions: a topic you hold a view on moves the room your way.")
    elif cu.get("kind") == "unmoderated":
        steps.append({"kind": "caucus", "text": "You moved for an unmoderated caucus and worked " + " and ".join(names.get(i, i) for i in cu.get("isos", [])) + " on the floor."})
    won = lost = with_room = 0
    for d in s.get("done", []):
        res = d["result"]
        mine = d.get("my_vote")
        margin = d.get("yes", 0) - d.get("no", 0)
        line = {"kind": "amendment", "by": who(d["by"]), "text": d["text"], "result": res, "my_vote": mine,
                "yes": d.get("yes"), "no": d.get("no"), "abstain": d.get("abstain"), "spoke": d.get("spoke")}
        steps.append(line)
        side = d.get("side", 0)
        good = (res in ("adopted", "accepted as friendly")) == (side > 0) if side else None
        if good is True:
            won += 1
        elif good is False:
            lost += 1
        if mine and res in ("adopted", "rejected"):
            with_room += (mine == "yes") == (res == "adopted")
        if good is False and res in ("adopted", "rejected") and abs(margin) <= 2 and not d.get("veto"):
            had = d.get("had", {})
            if had.get("favours") and d.get("extra") != "favour":
                lessons.append(f"\u201c{d['text']}\u201d went against you by {abs(margin) or 'a tie'}{' vote' if abs(margin) == 1 else ' votes' if margin else ''}, "
                               "while someone still owed you a favour. Calling it in could have turned it.")
            elif had.get("influence", 0) >= E.R["offer_cost"] and d.get("extra") != "offer":
                lessons.append(f"\u201c{d['text']}\u201d went against you narrowly, with Influence still in hand: a last offer could have turned it.")
            if d.get("spoke") == "silent":
                lessons.append(f"You stayed silent on \u201c{d['text']}\u201d, and it went against you by a little. A speech moves waverers.")
        if good is False and d.get("veto"):
            lessons.append(f"\u201c{d['text']}\u201d fell to a permanent member's no. In the Council, win the permanent members before the vote.")
    f = s.get("final") or {}
    stats = {"amendments": len(s.get("done", [])), "won": won, "lost": lost, "with_room": with_room,
             "yours": sum(1 for d in s.get("done", []) if d["by"] == "you"), "changes": len(s.get("tracked", [])),
             "final": {"yes": f.get("yes"), "no": f.get("no"), "abstain": f.get("abstain"), "passed": f.get("passed")}}
    if not stats["yours"]:
        lessons.append("You tabled no amendments of your own: two are allowed, and they're how you put your aims in late.")
    if f and not f.get("passed") and f.get("yes", 0) >= (f.get("no", 0) or 0) - 2:
        lessons.append("The final vote was close. One more delegation won over before the Summit would have carried it.")
    return {"steps": steps, "stats": stats, "lessons": lessons[:5]}
