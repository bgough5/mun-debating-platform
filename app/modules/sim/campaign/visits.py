"""The Session, phase 13 (D-101): delegates come to talk to you. One to three at the start of each turn, and now and
then right after a move of yours. Conversations cost no actions; some options cost Influence. What they say depends on
trust, Respect and what happened last turn:

- press: a rival wants its clause; agree (and it eases off you this turn), pay it to hold off, or refuse.
- ally:  a delegation that trusts you offers to work its regional group for you, or asks for a promise.
- ask:   a delegation asks where another stands. Tell the truth, decline, or lie: a lie can move it your way, but if
         it is found out (a chance each turn) you lose Respect and its trust.
- info:  a delegation offers intelligence for Influence.

The engine imports this module at the end of its definitions."""
from __future__ import annotations

import random

from app.modules.sim.campaign import engine as E
from app.modules.sim.campaign import talks as T


def _rng(g, salt):
    return random.Random(f"{g['seed']}:visit:{g.get('tick', 0)}:{g['n']}:{salt}")


def _free(scn, g):
    return [i for i in scn.isos if i not in E._others(g) and i != g["iso3"]]


def _label(scn, tag):
    return E._lc(scn.tags[tag]).rstrip(".")


def _make(scn, g, kind, iso, rng):
    name = scn.member(iso).name
    vid = f"v{g.get('tick', 0)}-{len(g.get('visits', []))}-{iso}"
    if kind == "press":
        rv = next(r for r in g["rivals"] if r["iso3"] == iso)
        angry = rv.get("grudge", 0)
        text = (f"{name}'s delegate takes you aside" + (", still smarting from last time" if angry else "") +
                f": “We need a clause that {_label(scn, rv['want'])}. Stand aside on it, and we'll ease off you this turn. " +
                ("This is the last time we ask nicely.”" if angry else "Or we can do this the hard way.”"))
        opts = [{"code": "agree", "label": "Agree: you won't vote against it", "cost": 0},
                {"code": "hold", "label": "Ask them to hold off this turn", "cost": 2},
                {"code": "refuse", "label": "Refuse", "cost": 0}]
        return {"id": vid, "kind": kind, "iso3": iso, "text": text, "options": opts, "tag": rv["want"]}
    if kind == "ally":
        region = E.REGIONS.get(scn.member(iso).region, "its regional group")
        text = (f"{name}'s delegate: “We're with you. Put something behind it and we'll work the {region} for you. "
                f"Or just tell us you'll stand by the clause we care about.”")
        opts = [{"code": "back", "label": f"Back them: they work the {region}", "cost": 2},
                {"code": "promise", "label": "Promise to back their clause", "cost": 0},
                {"code": "decline", "label": "Thank them, not now", "cost": 0}]
        return {"id": vid, "kind": kind, "iso3": iso, "text": text, "options": opts}
    if kind == "ask":
        others = [i for i in scn.isos if i not in (iso, g["iso3"])]
        about = rng.choice(others)
        text = (f"{name}'s delegate, quietly: “Where does {scn.member(about).name} stand on your draft? "
                f"We'd rather not be the last to know.”")
        opts = [{"code": "truth", "label": "Tell them the truth", "cost": 0},
                {"code": "lie", "label": f"Tell them {scn.member(about).name} is backing your draft", "cost": 0},
                {"code": "decline", "label": "Say you can't speak for others", "cost": 0}]
        return {"id": vid, "kind": kind, "iso3": iso, "text": text, "options": opts, "about": about}
    rv = next((r for r in g["rivals"] if not r.get("truce")), None)
    text = (f"{name}'s delegate: “We hear things. For a little support, we'll tell you what "
            f"{scn.member(rv['iso3']).name if rv else 'the others'} is planning next.”")
    opts = [{"code": "pay", "label": "Pay for the intelligence", "cost": 1}, {"code": "decline", "label": "Decline", "cost": 0}]
    return {"id": vid, "kind": "info", "iso3": iso, "text": text, "options": opts, "about": rv["iso3"] if rv else None}


def _pick(scn, g, rng, near=None):
    """Who comes, and why: a rival with a stake, a delegation that trusts you, or any delegation curious or selling."""
    kinds = []
    rivals = [r for r in g["rivals"] if not r.get("truce")]
    tags = {t for c in g["draft"] for t in c["tags"]}
    pressing = [r for r in rivals if r["want"] not in tags and r["want"] != g["mandate"]["red"]
                and not any(p["iso3"] == r["iso3"] and p["kept"] is None for p in g.get("pacts", []))]
    friends = [i for i in _free(scn, g) if g["trust"].get(i, 0) >= 1]
    free = _free(scn, g)
    if pressing:
        kinds.append(("press", pressing[rng.randrange(len(pressing))]["iso3"], 3))
    if friends:
        kinds.append(("ally", near if near in friends else rng.choice(friends), 2 + (g["respect"] >= 5) + min(2, g.get("rep", {}).get("honest", 0) // 2)))
    if len(free) >= 2:
        kinds.append(("ask", near if near in free else rng.choice(free), 2))
    if free and rivals:
        kinds.append(("info", rng.choice(free), 1))
    if not kinds:
        return None
    total = sum(w for _, _, w in kinds)
    x = rng.uniform(0, total)
    for kind, iso, w in kinds:
        x -= w
        if x <= 0:
            return kind, iso
    return kinds[-1][:2]


def turn_start(scn, g):
    """Lapse last turn's visits, settle lies that come out, then one to three delegates come to call."""
    g["visits"] = []
    for lie in list(g.get("lies", [])):
        if _rng(g, "lie" + lie["iso3"]).random() < 0.35:
            g["lies"].remove(lie)
            g["respect"] = max(0, g["respect"] - 1)
            g["trust"][lie["iso3"]] = max(-E.R["trust_max"], g["trust"].get(lie["iso3"], 0) - 2)
            E._sway(g, "you", lie["iso3"], -0.3)
            E._log(g, lie["iso3"], f"{scn.member(lie['iso3']).name} found out you misled them about {scn.member(lie['about']).name}. "
                                   "They trust you less, and the room has noticed.", "warning", lie["iso3"])
    rng = _rng(g, "start")
    g["visits"].extend(_extra(scn, g, rng))
    n = 1 + (g["respect"] >= 5) + (any(v >= 2 for v in g["trust"].values()))
    seen = set()
    for k in range(min(3, n)):
        pick = _pick(scn, g, rng)
        if pick and (pick[1], pick[0]) not in seen:
            seen.add((pick[1], pick[0]))
            g["visits"].append(_make(scn, g, pick[0], pick[1], rng))


def after_move(scn, g, action):
    """Now and then, a delegate approaches right after one of your moves (often the one you just worked on)."""
    rng = _rng(g, "move")
    if rng.random() >= 0.22 or len(g.get("visits", [])) >= 4:
        return None
    pick = _pick(scn, g, rng, near=action.get("iso3"))
    if not pick:
        return None
    v = _make(scn, g, pick[0], pick[1], rng)
    g.setdefault("visits", []).append(v)
    return v["id"]


def a_visit(scn, g, a):
    v = next((x for x in g.get("visits", []) if x["id"] == a.get("id")), None)
    if not v:
        raise E.GameError("That conversation is over.")
    opt = next((o for o in v["options"] if o["code"] == a.get("choice")), None)
    if not opt:
        raise E.GameError("Choose what to say.")
    if opt["cost"]:
        E._spend(g, 0, opt["cost"])
    g["visits"].remove(v)
    iso, name, c = v["iso3"], scn.member(v["iso3"]).name, opt["code"]
    out = {"said": c}
    if v["kind"] == "press":
        rv = next(r for r in g["rivals"] if r["iso3"] == iso)
        if c == "agree":
            g.setdefault("pacts", []).append({"iso3": iso, "tag": v["tag"], "kept": None})
            rv["hold"] = g.get("tick", 0) + 1
            rv["grudge"] = 0
            _rep(g, "honest")
            E._log(g, "you", f"You told {name} you won't vote against a clause that {_label(scn, v['tag'])}. It eases off you this turn.", "action", iso)
        elif c == "hold":
            rv["hold"] = g.get("tick", 0) + 1
            E._log(g, "you", f"You paid {name} to hold off this turn.", "action", iso)
        else:
            rv["grudge"] = rv.get("grudge", 0) + 1
            if rv["grudge"] >= 2:
                rv["fury"] = g.get("tick", 0) + 1
            _rep(g, "hard")
            E._log(g, "you", f"You turned {name} down." + (" It will come at you harder next turn." if rv["grudge"] >= 2 else ""), "action", iso)
    elif v["kind"] == "ally":
        if c == "back":
            for i in E._region_members(scn, scn.member(iso).region):
                if i not in E._others(g) and i != g["iso3"]:
                    E._sway(g, "you", i, 0.12)
            E._log(g, iso, f"{name} worked its regional group for you.", "action", iso)
        elif c == "promise":
            cl = E._their_clause(scn, g, iso)
            if cl and not any(p["iso3"] == iso and p["kept"] is None for p in g["promises"]):
                g["promises"].append({"iso3": iso, "clause": cl["id"], "kept": None})
                g["trust"][iso] = min(E.R["trust_max"], g["trust"][iso] + 1)
                E._log(g, "you", f"You promised {name} to back its clause.", "action", iso)
                if g["mandate"]["red"] in cl["tags"]:
                    E._capital(scn, g, -2, E.CAPITAL_WHY["clause"])
    elif v["kind"] == "ask":
        about = v["about"]
        final = E.final_clause(g)
        truth = E.projection(scn, g)["votes"].get(about, "abstain") if final["tags"] else "abstain"
        if c == "truth":
            _rep(g, "honest")
            g["trust"][iso] = min(E.R["trust_max"], g["trust"][iso] + 1)
            out["truth"] = truth
            E._log(g, "you", f"You told {name} honestly: {scn.member(about).name} would vote {truth}.", "action", iso)
        elif c == "lie":
            _rep(g, "bluff")
            E._sway(g, "you", iso, 0.3)
            if truth != "yes":
                g.setdefault("lies", []).append({"iso3": iso, "about": about})
            E._log(g, "you", f"You told {name} that {scn.member(about).name} is backing your draft.", "action", iso)
    elif v["kind"] in ("caucus", "capital", "media", "collect", "persuade"):
        out = answer_more(scn, g, v, c, out)
    elif v["kind"] == "info" and c == "pay":
        it = g.get("intent", {}).get(v.get("about")) if v.get("about") else None
        if it:
            E._log(g, iso, f"{name} tells you: {scn.member(v['about']).name} will go after "
                           f"{E._target_name(scn, g, it['kind'], it['target'])} next.", "intel", v["about"])
        else:
            E._log(g, iso, f"{name} tells you: {scn.member(v['about']).name if v.get('about') else 'nobody'} has nothing planned.", "intel")
    return out


def bot_answer(g, rng, competent):
    for v in list(g.get("visits", [])):
        if not competent:
            yield {"do": "visit", "id": v["id"], "choice": rng.choice(v["options"])["code"]}
            continue
        if v["kind"] == "press":
            choice = "refuse" if v["tag"] in (g["mandate"]["red"],) else "agree"
        elif v["kind"] == "ally":
            choice = "back" if g["influence"] >= 6 else "decline"
        elif v["kind"] == "ask":
            choice = "truth"
        elif v["kind"] in ("caucus", "capital", "media", "collect"):
            choice = v["options"][0]["code"]
        elif v["kind"] == "persuade":
            choice = rng.choice(v["options"])["code"]
        else:
            choice = "decline"
        yield {"do": "visit", "id": v["id"], "choice": choice}


# ---------------------------------------------------------------- more conversations (Ben's picks, phase 13)
# Reputation (delegates remember you), answering with your pitch arguments, the caucus team talk, your capital
# calling, the press, and follow-ups on promises.

FEEL = {2: "Close", 1: "Warm", 0: "Neutral", -1: "Cool", -2: "Hostile"}


def feeling(g, iso) -> str:
    rel = g["trust"].get(iso, 0) + 2 * g["sway"]["you"].get(iso, 0.0)
    return FEEL[2 if rel >= 3 else 1 if rel >= 1 else 0 if rel > -1 else -1 if rel > -3 else -2]


def reputation(g) -> str | None:
    r = g.get("rep", {})
    best = max(("honest", "hard", "bluff"), key=lambda k: (r.get(k, 0), k))
    if r.get(best, 0) < 2:
        return None
    return {"honest": "an honest broker", "hard": "a hard bargainer", "bluff": "known to bluff"}[best]


def _rep(g, k):
    g.setdefault("rep", {})[k] = g.setdefault("rep", {}).get(k, 0) + 1


def _extra(scn, g, rng):
    """Visits Ben added: a caucus when a group meets, the capital's call, the press, follow-ups, a wavering delegate."""
    out = []
    if g.get("meeting") and not any(v["kind"] == "caucus" for v in g.get("visits", [])):
        members = [i for i in E._region_members(scn, g["meeting"]) if i not in E._others(g) and i != g["iso3"]]
        if members:
            coord = max(members, key=lambda i: (len(i), i))
            out.append({"id": f"v{g.get('tick', 0)}-caucus", "kind": "caucus", "iso3": coord, "members": members,
                        "text": f"The {E.REGIONS[g['meeting']]} is in caucus, and its members have asked you in to address them. "
                                "How will you speak to the room?",
                        "options": [{"code": "rally", "label": "Rally them: passion and the big picture", "cost": 0},
                                    {"code": "reassure", "label": "Reassure them: calm, practical, listening", "cost": 0},
                                    {"code": "demand", "label": "Demand their support: firm, no promises", "cost": 0}]})
    if g["turn"] == 2 and str(g["chapter"]) not in g.get("called", {}):
        g.setdefault("called", {})[str(g["chapter"])] = True
        must = _label(scn, g["mandate"]["must"])
        out.append({"id": f"v{g.get('tick', 0)}-capital", "kind": "capital", "iso3": g["iso3"], "who": "minister",
                    "text": f"Your Foreign Minister is on the line: “Ambassador, we need a clause that {must} by the end of this stage. Can you deliver?”",
                    "options": [{"code": "vow", "label": "“Yes, Minister.” (their confidence now; a failure costs more)", "cost": 0},
                                {"code": "resources", "label": "Ask for more resources (+3 Influence, a little confidence)", "cost": 0},
                                {"code": "explain", "label": "Explain the difficulties honestly", "cost": 0}]})
    if rng.random() < 0.25 and g["draft"]:
        c = rng.choice(g["draft"])
        n = g["draft"].index(c) + 1
        out.append({"id": f"v{g.get('tick', 0)}-press", "kind": "media", "iso3": g["iso3"], "who": "press", "clause": c["id"],
                    "text": f"A journalist catches you in the corridor: “Where does {scn.member(g['iso3']).name} stand on clause {n}? Our readers want a straight answer.”",
                    "options": [{"code": "open", "label": "Answer openly and fully", "cost": 0},
                                {"code": "firm", "label": "Make a firm statement for your position", "cost": 0},
                                {"code": "evasive", "label": "No comment", "cost": 0}]})
    owed = [p for p in g["promises"] if p["kept"] is None and p["iso3"] not in g.get("reminded", [])]
    if owed and rng.random() < 0.5:
        p = rng.choice(owed)
        g.setdefault("reminded", []).append(p["iso3"])
        n = next((i + 1 for i, c in enumerate(g["draft"]) if c["id"] == p["clause"]), None)
        out.append({"id": f"v{g.get('tick', 0)}-collect-{p['iso3']}", "kind": "collect", "iso3": p["iso3"],
                    "text": f"{scn.member(p['iso3']).name}'s delegate: “You promised to back clause {n}. We're counting on you at the vote.”",
                    "options": [{"code": "reassure", "label": "“You have my word.”", "cost": 0},
                                {"code": "ask", "label": "“And I'm counting on your yes in return.”", "cost": 0}]})
    waver = [i for i in _free(scn, g) if abs(E.lean(scn, g, "you", i) - E.R["lean_min"]) < 0.25]
    if waver and rng.random() < 0.5:
        iso = rng.choice(waver)
        out.append({"id": f"v{g.get('tick', 0)}-persuade-{iso}", "kind": "persuade", "iso3": iso,
                    "text": f"{scn.member(iso).name}'s delegate is on the fence: “Convince me. Why should my government back your draft?”",
                    "options": [{"code": k, "label": T.ARGS[k]["name"], "cost": 0} for k in T.ARGS]})
    return out


def answer_more(scn, g, v, c, out):
    iso, name = v["iso3"], scn.member(v["iso3"]).name
    if v["kind"] == "caucus":
        reactions = {}
        for i in v["members"]:
            ln = E.lean(scn, g, "you", i)
            d = ({"rally": 0.15 if ln > 0 else 0.03, "reassure": 0.1 if abs(ln) < 0.5 else 0.03,
                  "demand": 0.2 if ln > 0.3 else -0.1}[c])
            E._sway(g, "you", i, d)
            reactions[i] = {"name": scn.member(i).name, "feeling": feeling(g, i),
                            "reaction": "pleased" if d >= 0.1 else "unmoved" if d > 0 else "annoyed"}
        out["reactions"] = reactions
        E._log(g, "you", f"You addressed the {E.REGIONS.get(g.get('meeting'), 'regional')} caucus.", "action")
    elif v["kind"] == "capital":
        if c == "vow":
            E._capital(scn, g, 1, "Good. We're counting on you.")
            g.setdefault("vows", []).append(g["chapter"])
        elif c == "resources":
            g["influence"] += 3
            E._capital(scn, g, -1, "Very well. Don't make us regret it.")
        else:
            E._log(g, "capital", "Your Minister listens. “Understood. Do what you can.”", "telegram")
    elif v["kind"] == "media":
        cl = next((x for x in g["draft"] if x["id"] == v["clause"]), None)
        if c == "open":
            g["respect"] = min(E.R["respect_max"], g["respect"] + 1)
        elif c == "firm" and cl:
            for i in _free(scn, g):
                E._sway(g, "you", i, 0.08 if E.mu_of(scn, g, i, cl["tags"]) > 0 else -0.04)
        E._log(g, "you", "You spoke to the press" + (": openly." if c == "open" else ": firmly." if c == "firm" else ": no comment."), "action")
    elif v["kind"] == "collect":
        if c == "reassure":
            g["trust"][iso] = min(E.R["trust_max"], g["trust"][iso] + 1)
            _rep(g, "honest")
        else:
            E._sway(g, "you", iso, 0.15)
            _rep(g, "hard")
    elif v["kind"] == "persuade":
        r = T.receptive(scn, g, iso)
        E._sway(g, "you", iso, 0.3 * r[c])
        out["landed"] = "strong" if r[c] == T.STRONG else "some" if r[c] == T.SOME else "weak"
        E._log(g, "you", f"You made the case to {name}: {T.ARGS[c]['name'].lower()} " +
               ("landed." if r[c] == T.STRONG else "partly landed." if r[c] == T.SOME else "fell flat."), "action", iso)
    return out
