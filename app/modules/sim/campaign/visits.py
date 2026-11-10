"""The Session, phase 13 (D-101): delegates come to talk to you. One to three at the start of each turn, and now and
then right after a move of yours. Conversations cost no actions; some options cost Influence. What they say depends on
trust, Respect and what happened last turn:

- press: a rival wants its clause; agree (and it eases off you this turn), pay it to hold off, or refuse.
- ally:  a delegation that trusts you offers to work its regional group for you, or asks for a promise.
- ask:   a delegation asks where another stands. If you know (its file, an adviser posted there, your whip sheet),
         tell them, decline, or bluff; if you don't, guess, admit it, or bluff. A bluff can move it your way, but if
         it is found out (a chance each turn) you lose Respect and its trust.
- info:  a delegation offers intelligence for Influence.

The engine imports this module at the end of its definitions."""
from __future__ import annotations

import random

from app.modules.sim.campaign import content as K
from app.modules.sim.campaign import engine as E
from app.modules.sim.campaign import talks as T
from app.modules.sim.campaign import voices as VO


def _rng(g, salt):
    return random.Random(f"{g['seed']}:visit:{g.get('tick', 0)}:{g['n']}:{salt}")


def _free(scn, g):
    return [i for i in scn.isos if i not in E._others(g) and i != g["iso3"]]


def knows(g, iso) -> str | None:
    """How you know where a delegation stands, if you do."""
    if iso in g.get("read", []):
        return "its file"
    if any(a.get("post") == iso for a in g.get("staff", [])):
        return "your adviser"
    if iso in g.get("whip", {}):
        return "your whip sheet"
    return None


MAX_VISITORS = 4                                              # two to four a turn (Ben, 8 Nov: more, with consequences)
TIER = {"confront": 0, "capital": 0, "caucus": 0, "press": 1, "collect": 1, "ultimatum": 1, "old_sins": 1}


def _offer_visit(scn, g, o):
    """An offer at your door, as a visit: the delegate puts the deal to you in person."""
    terms = {"back": "You'd promise to vote yes on that clause at the summit.",
             "drop": "You'd propose that amendment; the working group must agree.",
             "favour": "You'd pay 2 Influence.", "trade": ""}[o["kind"]]
    return {"id": "v-" + o["id"], "kind": "offer", "iso3": o["iso3"], "offer": o["id"], "text": (o["text"] + " " + terms).strip(),
            "options": [{"code": "accept", "label": "Accept the deal", "cost": 0}, {"code": "refuse", "label": "Turn it down", "cost": 0}]}


def _label(scn, tag):
    return E._lc(scn.tags[tag]).rstrip(".")


def _make(scn, g, kind, iso, rng):
    name = scn.member(iso).name
    vid = f"v{g.get('tick', 0)}-{len(g.get('visits', []))}-{iso}"
    if kind == "press":
        rv = next(r for r in g["rivals"] if r["iso3"] == iso)
        angry = rv.get("grudge", 0)
        text = (f"{name}'s delegate takes you aside" + (", still smarting from last time" if angry else "") +
                f": “{'' if angry else VO.greet(scn, g, iso, 'press') + ' '}We need a clause that {_label(scn, rv['want'])}. Stand aside on it, and we'll ease off you this turn. " +
                ("This is the last time we ask nicely.”" if angry else "Or we can do this the hard way.”"))
        opts = [{"code": "agree", "label": "Agree: you won't vote against it", "cost": 0},
                {"code": "counter", "label": "Counter: only if they stop going after your own clause", "cost": 0},
                {"code": "hold", "label": "Ask them to hold off this turn", "cost": 2},
                {"code": "refuse", "label": "Refuse", "cost": 0}]
        return {"id": vid, "kind": kind, "iso3": iso, "text": text, "options": opts, "tag": rv["want"]}
    if kind == "ally":
        region = E.REGIONS.get(scn.member(iso).region, "its regional group")
        text = f"{name}'s delegate: “{VO.visit(scn, g, iso, 'ally', region=region)}”"
        opts = [{"code": "back", "label": f"Back them: they work the {region}", "cost": 2},
                {"code": "promise", "label": "Promise to back their clause", "cost": 0},
                {"code": "decline", "label": "Thank them, not now", "cost": 0}]
        return {"id": vid, "kind": kind, "iso3": iso, "text": text, "options": opts}
    if kind == "ask":
        others = [i for i in scn.isos if i not in (iso, g["iso3"])]
        about = rng.choice(others)
        text = f"{name}'s delegate, quietly: “{VO.visit(scn, g, iso, 'ask', about=scn.member(about).name)}”"
        aname = scn.member(about).name
        src = knows(g, about)
        if src:
            final = E.final_clause(g)
            truth = E.projection(scn, g)["votes"].get(about, "abstain") if final["tags"] else "abstain"
            word = {"yes": "is backing your draft", "no": "is against your draft", "abstain": "is undecided on your draft"}[truth]
            opts = [{"code": "truth", "label": f"Tell them what you know ({src}): {aname} {word}", "cost": 0},
                    {"code": "lie", "label": f"Bluff: tell them {aname} is backing your draft", "cost": 0},
                    {"code": "decline", "label": "Say you can't speak for others", "cost": 0}]
        else:
            opts = [{"code": "guess", "label": f"Give your best guess about {aname}", "cost": 0},
                    {"code": "dunno", "label": "Admit you don't know", "cost": 0},
                    {"code": "lie", "label": f"Bluff: tell them {aname} is backing your draft", "cost": 0}]
        return {"id": vid, "kind": kind, "iso3": iso, "text": text, "options": opts, "about": about}
    rv = next((r for r in g["rivals"] if not r.get("truce")), None)
    text = f"{name}'s delegate: “{VO.visit(scn, g, iso, 'info', rival=scn.member(rv['iso3']).name if rv else 'the others')}”"
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
            g.setdefault("grievances", []).append({"iso3": lie["iso3"], "kind": "lie", "about": lie["about"]})
    g["visitors"] = 0
    if g["chapter"] == 1 and g["turn"] == 1:                 # the very first turn is yours alone
        g["offers"] = []
        return
    rng = _rng(g, "start")
    g["visits"].extend(_extra(scn, g, rng))
    if g.get("offers"):                                       # a delegation with a deal comes to see you (one a turn)
        g["visits"].append(_offer_visit(scn, g, rng.choice(g["offers"])))
    n = 1 + (g["respect"] >= 5) + (any(v >= 2 for v in g["trust"].values()))
    seen = set()
    for k in range(min(3, n)):
        pick = _pick(scn, g, rng)
        if pick and (pick[1], pick[0]) not in seen:
            seen.add((pick[1], pick[0]))
            g["visits"].append(_make(scn, g, pick[0], pick[1], rng))
    rng.shuffle(g["visits"])                                   # who gets through: your capital and the caucus first, then
    g["visits"].sort(key=lambda x: TIER.get(x["kind"], 2))     # rivals pressing, offers and promises, then the rest
    g["visits"].extend(_more(scn, g, rng))
    rng.shuffle(g["visits"])
    g["visits"].sort(key=lambda x: TIER.get(x["kind"], 2))
    most = rng.choice([2, 3, 3, 4]) + (1 if g.get("approach") == "envoy" else 0)
    if g.get("question"):                                     # the President's question is this turn's interruption (Fable, 9c)
        most = min(most, 2)
    g["visits"] = g["visits"][:max(most, sum(TIER.get(x["kind"]) == 0 for x in g["visits"]))]
    shown = {x.get("offer") for x in g["visits"]}
    g["offers"] = [o for o in g.get("offers", []) if o["id"] in shown]
    confront(scn, g)                                          # a lie that came out: they come first, outside the cap
    g["visitors"] = len(g["visits"])


def confront(scn, g):
    """A delegation you lied to or broke your word with comes to call you to account (Ben, 10 Nov): you hear how they
    took it, and choose how to answer. Apologising costs Influence and mends a little; explaining is free but may make it
    worse; standing by it costs nothing with them, and cools their region a little more. Returns the first new visit."""
    first = None
    for gr in g.pop("grievances", []) or []:
        iso = gr["iso3"]
        if iso == g["iso3"] or any(v.get("kind") == "confront" and v["iso3"] == iso for v in g.get("visits", [])):
            continue
        name = scn.member(iso).name
        if gr["kind"] == "lie":
            said = (f"{name}'s delegate, coldly: “You told us {scn.member(gr['about']).name} was backing your draft. It wasn't. "
                    "We passed that on to our capital, and we look foolish.”")
        else:
            said = (f"{name}'s delegate is waiting for you, and doesn't sit down: “You gave us your word, and you broke it. "
                    "My capital wants to know why it should ever deal with you again.”")
        v = {"id": f"v{g.get('tick', 0)}-confront-{iso}", "kind": "confront", "iso3": iso, "text": said,
             "options": [{"code": "apologise", "label": "Apologise, and make amends (2 Influence)", "cost": 2},
                         {"code": "explain", "label": "Explain the pressure you were under", "cost": 0},
                         {"code": "stand", "label": "Stand by what you did", "cost": 0}]}
        g.setdefault("visits", []).insert(0, v)
        first = first or v["id"]
    return first


def _answer_confront(scn, g, v, c, out):
    iso, name = v["iso3"], scn.member(v["iso3"]).name
    tmax = E.R["trust_max"]
    if c == "apologise":
        g["trust"][iso] = min(tmax, g["trust"].get(iso, 0) + 1)
        E._sway(g, "you", iso, 0.15)
        _rep(g, "honest")
        out["reply"] = "“We accept your apology, and what comes with it. Don't make us regret it.”"
        E._log(g, "you", f"You apologised to {name} and made amends.", "action", iso)
    elif c == "explain":
        r = g.get("rep", {})
        p = 0.6 if r.get("honest", 0) > r.get("bluff", 0) else 0.35
        if _rng(g, "confront" + iso).random() < p:
            g["trust"][iso] = min(tmax, g["trust"].get(iso, 0) + 1)
            out["reply"] = "“We know what pressure feels like in this building. Once, Ambassador. Only once.”"
            E._log(g, "you", f"You explained yourself to {name}. They accepted it, this once.", "action", iso)
        else:
            E._sway(g, "you", iso, -0.1)
            out["reply"] = "“Excuses. We expected better from you.”"
            E._log(g, "you", f"You explained yourself to {name}. They weren't convinced.", "warning", iso)
    else:
        _rep(g, "hard")
        for i in E._region_members(scn, scn.member(iso).region):
            if i != iso and i not in E._others(g) and i != g["iso3"]:
                E._sway(g, "you", i, -0.05)
        out["reply"] = "“Then we know exactly where we stand with you. So will our neighbours.”"
        E._log(g, "you", f"You stood by what you did. {name} has told its regional group.", "warning", iso)
    return out


def after_move(scn, g, action):
    """Now and then, a delegate approaches right after one of your moves (often the one you just worked on)."""
    rng = _rng(g, "move")
    if rng.random() >= 0.22 or g.get("visitors", 0) >= MAX_VISITORS + (1 if g.get("approach") == "envoy" else 0) or (g["chapter"] == 1 and g["turn"] == 1):
        return None
    pick = _pick(scn, g, rng, near=action.get("iso3"))
    if not pick:
        return None
    v = _make(scn, g, pick[0], pick[1], rng)
    g.setdefault("visits", []).append(v)
    g["visitors"] = g.get("visitors", 0) + 1
    return v["id"]


def a_visit(scn, g, a):
    v = next((x for x in g.get("visits", []) if x["id"] == a.get("id")), None)
    if not v:
        raise E.GameError("That conversation is over.")
    opt = next((o for o in v["options"] if o["code"] == a.get("choice")), None)
    if not opt:
        raise E.GameError("Choose what to say.")
    if opt["cost"] or opt.get("ap"):
        E._spend(g, opt.get("ap", 0), opt["cost"])
    g["visits"].remove(v)
    iso, name, c = v["iso3"], scn.member(v["iso3"]).name, opt["code"]
    if not v.get("who") and iso != g["iso3"] and iso not in g.setdefault("engaged", []):
        g["engaged"].append(iso)                                  # talking to a visitor engages them too
    out = {"said": c}
    nxt = _follow_up(scn, g, v, c)
    if nxt:                                                   # the conversation goes on: their reply, and your next answer
        g["visits"].insert(0, nxt)
        out["continues"] = nxt["id"]
        return out
    if v["kind"] == "press":
        rv = next(r for r in g["rivals"] if r["iso3"] == iso)
        if c in ("agree_both", "pay_both"):
            g.setdefault("pacts", []).append({"iso3": iso, "tag": v["tag"], "kept": None})
            rv["spare"] = g["mandate"]["must"]
            rv["grudge"] = 0
            _rep(g, "honest")
            E._log(g, "you", f"You and {name} agreed to stand aside on each other's clause.", "action", iso)
        elif c == "agree":
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
        elif c == "guess":
            guess = E.vote_of(scn, E.lean(scn, g, "you", about) + _rng(g, v["id"]).gauss(0, 0.6))
            out["reply"] = "\u201c" + VO.reply(scn, g, iso, "right" if guess == truth else "off") + "\u201d"
            if guess != truth:
                g["trust"][iso] = max(-E.R["trust_max"], g["trust"][iso] - 1)
            E._log(g, "you", f"You gave {name} your best guess about {scn.member(about).name}.", "action", iso)
        elif c == "dunno":
            _rep(g, "honest")
            g["trust"][iso] = min(E.R["trust_max"], g["trust"][iso] + 1)
            out["reply"] = "\u201c" + VO.reply(scn, g, iso, "honest") + "\u201d"
            E._log(g, "you", f"You told {name} you don't know where {scn.member(about).name} stands.", "action", iso)
        elif c == "lie":
            _rep(g, "bluff")
            E._sway(g, "you", iso, 0.3)
            if truth != "yes":
                g.setdefault("lies", []).append({"iso3": iso, "about": about})
            E._log(g, "you", f"You told {name} that {scn.member(about).name} is backing your draft.", "action", iso)
    elif v["kind"] == "confront":
        out = _answer_confront(scn, g, v, c, out)
    elif v["kind"] in MORE:
        out = answer_new(scn, g, v, c, out)
    elif v["kind"] == "offer":
        if not any(o["id"] == v["offer"] for o in g.get("offers", [])):
            out["reply"] = "“We've moved on, Ambassador.”"     # the offer lapsed
        else:
            out.update(E.a_offer(scn, g, {"id": v["offer"], "answer": "accept" if c == "accept" else "refuse"}))
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
            if not any(o["code"] == choice for o in v["options"]):
                choice = v["options"][0]["code"]
        elif v["kind"] == "ally":
            choice = "back" if g["influence"] >= 6 else "decline"
        elif v["kind"] == "ask":
            choice = "truth" if any(o["code"] == "truth" for o in v["options"]) else "dunno"
        elif v["kind"] in ("caucus", "capital", "media", "collect"):
            choice = v["options"][0]["code"]
        elif v["kind"] == "persuade":
            choice = rng.choice(v["options"])["code"]
        elif v["kind"] == "confront":
            choice = "apologise" if g["influence"] >= 4 else "explain"
        else:
            choice = "decline"
        yield {"do": "visit", "id": v["id"], "choice": choice}


# ---------------------------------------------------------------- more conversations (Ben's picks, phase 13)
# Reputation (delegates remember you), answering with your pitch arguments, the caucus team talk, your capital
# calling, the press, and follow-ups on promises.

FEEL = {2: "Close", 1: "Warm", 0: "Neutral", -1: "Cool", -2: "Hostile"}


def relation(g, iso) -> int:
    """One relationship with each delegation (trust and how far you've won it over, together): -2 to 2."""
    rel = g["trust"].get(iso, 0) + 2 * g["sway"]["you"].get(iso, 0.0)
    return 2 if rel >= 3 else 1 if rel >= 1 else 0 if rel > -1 else -1 if rel > -3 else -2


def feeling(g, iso) -> str:
    return FEEL[relation(g, iso)]


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
                    "options": [{"code": "vow", "label": "“Yes, Minister. I'll deliver.”", "cost": 0},
                                {"code": "resources", "label": "Ask for more resources", "cost": 0},
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
                    "text": f"{scn.member(p['iso3']).name}'s delegate: “{VO.visit(scn, g, p['iso3'], 'collect', n=n)}”",
                    "options": [{"code": "reassure", "label": "“You have my word.”", "cost": 0},
                                {"code": "ask", "label": "“And I'm counting on your yes in return.”", "cost": 0}]})
    waver = [i for i in _free(scn, g) if abs(E.lean(scn, g, "you", i) - E.R["lean_min"]) < 0.25]
    if waver and rng.random() < 0.5:
        iso = rng.choice(waver)
        out.append({"id": f"v{g.get('tick', 0)}-persuade-{iso}", "kind": "persuade", "iso3": iso,
                    "text": f"{scn.member(iso).name}'s delegate is on the fence: “{VO.visit(scn, g, iso, 'persuade')}”",
                    "options": [{"code": k, "label": T.ARGS[k]["name"], "cost": 0} for k in T.ARGS]})
    return out


# what a delegate says after your caucus speech: by the speech you gave and how it landed with them. Each delegation now
# says it in its own register (`voices.caucus`); this shared bank is no longer used by the game.
CAUCUS_LINES = {
    "rally": {"pleased": ["That is the language we came here for.", "Well said. Our people would cheer that.", "Now that is a cause worth standing behind."],
              "unmoved": ["Fine words. We'll want to see the text.", "Inspiring, perhaps. It doesn't change our instructions.", "A good speech. Speeches don't vote."],
              "annoyed": ["Grand words don't pay for anything.", "We've heard a lot of big pictures this week.", "Spare us the poetry, Ambassador."]},
    "reassure": {"pleased": ["Practical. Thank you for listening to us.", "That answers what our capital asked.", "Calm and sensible. We can work with that."],
                 "unmoved": ["Reasonable enough. We'll see.", "Noted. Our concerns are elsewhere.", "Sensible, but it isn't what keeps our minister awake."],
                 "annoyed": ["You're telling us not to worry. We worry.", "That was a lot of reassurance and no substance.", "Too careful by half."]},
    "demand": {"pleased": ["Straight talk. We respect that.", "Firm. Good: we know where you stand.", "That is how serious delegations speak."],
               "unmoved": ["You'll need more than a demand.", "We heard you. We haven't decided.", "Strong words. Let's see the votes."],
               "annoyed": ["We don't take orders in this room.", "Is that a threat, Ambassador?", "My government won't be lectured."]},
}


def answer_more(scn, g, v, c, out):
    iso, name = v["iso3"], scn.member(v["iso3"]).name
    if v["kind"] == "caucus":
        reactions = {}
        for i in v["members"]:
            ln = E.lean(scn, g, "you", i)
            # each delegation hears the speech through what it listens to (talks.receptive, from its country's traits):
            # rallying speaks to values and solidarity, reassurance to economics and the rules, a demand to power
            r = T.receptive(scn, g, i)
            fit = {"rally": max(r["values"], r["region"]), "reassure": max(r["interest"], r["precedent"]), "demand": r["security"]}[c]
            mult = 0.5 + 0.75 * fit                                     # 1.25 when it lands, 0.6 when it barely does
            rel = relation(g, i)
            rng = random.Random(f"{g['seed']}:caucus:{g.get('tick', 0)}:{i}")
            if c == "demand":                                          # a demand lands only with friends who respect power
                d = 0.2 * mult if ln > 0.3 and rel >= 0 else -0.1 * (1.6 - fit) - (0.05 if rel < 0 else 0)
            else:
                d = ({"rally": 0.15 if ln > 0 else 0.03, "reassure": 0.1 if abs(ln) < 0.5 else 0.03}[c]) * mult
            d += rng.uniform(-0.025, 0.025)                            # the person in the seat, not only the country
            E._sway(g, "you", i, d)
            how = "pleased" if d >= 0.1 else "unmoved" if d > 0 else "annoyed"
            reactions[i] = {"name": scn.member(i).name, "feeling": feeling(g, i), "reaction": how,
                            "said": VO.caucus(scn, g, i, c, how, rng)}
        out["reactions"] = reactions
        E._log(g, "you", f"You addressed the {E.REGIONS.get(g.get('meeting'), 'regional')} caucus.", "action")
    elif v["kind"] == "capital":
        if c == "vow":
            E._capital(scn, g, 1, "Good. We're counting on you.")
            g.setdefault("vows", []).append(g["chapter"])
        elif c == "resources":
            g["influence"] += 3
            E._capital(scn, g, -1, "Very well. Don't make us regret it.")
        elif c == "time":
            if g["chapter"] in g.get("vows", []):
                g["vows"].remove(g["chapter"])
            E._capital(scn, g, -1, "Very well. But we expect results.")
        elif c == "manage":
            E._log(g, "capital", "Your Minister: \u201cGood. Carry on.\u201d", "telegram")
        else:
            E._log(g, "capital", "Your Minister listens. “Understood. Do what you can.”", "telegram")
    elif v["kind"] == "media":
        cl = next((x for x in g["draft"] if x["id"] == v["clause"]), None)
        if c == "open":                                        # candour earns Standing, and shows your hand (10 Nov)
            g["respect"] = min(E.R["respect_max"], g["respect"] + 1)
            if cl:
                for i in _free(scn, g):
                    if E.mu_of(scn, g, i, cl["tags"]) < 0:
                        E._sway(g, "you", i, -0.05)
        elif c == "firm" and cl:
            for i in _free(scn, g):
                E._sway(g, "you", i, 0.08 if E.mu_of(scn, g, i, cl["tags"]) > 0 else -0.04)
        if c == "walk":
            g["respect"] = max(0, g["respect"] - 1)
        E._log(g, "you", "You spoke to the press" + (": openly." if c == "open" else ": firmly." if c == "firm" else ": and walked away." if c == "walk" else ": no comment."), "action")
    elif v["kind"] == "collect":
        if c == "reassure":                                    # your word, sworn again: worth more, and dearer to break
            g["trust"][iso] = min(E.R["trust_max"], g["trust"][iso] + 1)
            _rep(g, "honest")
            for p in g["promises"]:
                if p["iso3"] == iso and p["kept"] is None:
                    p["sworn"] = True
        elif c == "insist":
            fond = E.lean(scn, g, "you", iso) > 0.2
            if fond:
                g.setdefault("deal_votes", {})[iso] = "yes"
                E._log(g, iso, f"{scn.member(iso).name} agreed: a yes for a yes.", "action", iso)
            else:
                g["trust"][iso] = max(-E.R["trust_max"], g["trust"][iso] - 1)
                E._log(g, iso, f"{scn.member(iso).name} took offence at being asked.", "warning", iso)
            _rep(g, "hard")
    elif v["kind"] == "persuade":
        r = T.receptive(scn, g, iso)
        E._sway(g, "you", iso, 0.3 * r[c])
        out["landed"] = "strong" if r[c] == T.STRONG else "some" if r[c] == T.SOME else "weak"
        E._log(g, "you", f"You made the case to {name}: {T.ARGS[c]['name'].lower()} " +
               ("landed." if r[c] == T.STRONG else "partly landed." if r[c] == T.SOME else "fell flat."), "action", iso)
    return out


def _follow_up(scn, g, v, c):
    """Two- or three-exchange conversations: the other side replies, and you answer again."""
    step = v.get("step", 1)
    name = "Your Foreign Minister" if v.get("who") == "minister" else "The journalist" if v.get("who") == "press" else scn.member(v["iso3"]).name
    base = {k: v[k] for k in v if k not in ("id", "text", "options", "step")}
    base["id"] = v["id"] + f"-{step + 1}"
    base["step"] = step + 1
    if v["kind"] == "press" and c == "counter" and step == 1:
        rv = next(r for r in g["rivals"] if r["iso3"] == v["iso3"])
        style = rv.get("style", "hawk")
        if style == "broker":
            base["text"] = f"{name}: \u201cA fair trade. We stand aside on yours, you stand aside on ours. Agreed?\u201d"
            base["options"] = [{"code": "agree_both", "label": "Agreed: shake on it", "cost": 0}, {"code": "refuse", "label": "On reflection, no", "cost": 0}]
        elif style == "spoiler":
            base["text"] = f"{name}: \u201cWe'll leave your clause alone, for a price.\u201d"
            base["options"] = [{"code": "pay_both", "label": "Pay their price", "cost": 2}, {"code": "refuse", "label": "Refuse", "cost": 0}]
        else:
            base["text"] = f"{name}: \u201cOut of the question. Our clause, or nothing.\u201d"
            base["options"] = [{"code": "agree", "label": "Then you won't vote against it", "cost": 0}, {"code": "refuse", "label": "Then nothing", "cost": 0}]
        return base
    if v["kind"] == "media" and c == "evasive" and step == 1:
        base["text"] = "The journalist: \u201cSo that's a no? Our readers will draw their own conclusions.\u201d"
        base["options"] = [{"code": "firm", "label": "Make a firm statement after all", "cost": 0},
                           {"code": "open", "label": "Explain your position openly", "cost": 0},
                           {"code": "walk", "label": "Walk away", "cost": 0}]
        return base
    if v["kind"] == "capital" and c == "explain" and step == 1:
        base["text"] = "Your Foreign Minister: \u201cI understand. Then tell me what you need.\u201d"
        base["options"] = [{"code": "resources", "label": "More resources", "cost": 0},
                           {"code": "time", "label": "More time: release me from this stage's promise", "cost": 0},
                           {"code": "manage", "label": "Nothing. I'll manage.", "cost": 0}]
        return base
    if v["kind"] == "collect" and c == "ask" and step == 1:
        base["text"] = f"{name}'s delegate pauses: \u201cA yes from us on the whole text, in return? That's a bigger ask.\u201d"
        base["options"] = [{"code": "insist", "label": "Insist: a yes for a yes", "cost": 0}, {"code": "reassure", "label": "Let it go: you have my word", "cost": 0}]
        return base
    return None


def likeness(iso: str) -> str:
    """A delegate's look, the same every game: skin tone, hair, glasses, and a tie or scarf. Respectful variety only:
    no national costume. Built from a hash of the country code, so it never encodes a stereotype about a country."""
    n = sum((i + 7) * ord(ch) for i, ch in enumerate(iso))
    look = "dl-gf" if (n // 17) % 2 else "dl-gm"
    parts = [f"dl-k{n % 7}", f"dl-h{(n // 7) % 8}", f"dl-w{NATURAL[(n // 56) % len(NATURAL)]}", "dl-e1" if (n // 392) % 3 == 0 else "",
             f"dl-t{(n // 11) % 4}", f"dl-j{(n // 13) % 6}", look, f"dl-f{(n // 19) % 4}" if look == "dl-gm" else ""]
    return " ".join(x for x in parts if x)


NATURAL = [0, 1, 3, 4, 5, 6, 2]                 # hair colours a delegate may have: black, browns, auburn, ginger, blonde, grey


# ---------------------------------------------------------------- more conversations (Ben, 8 Nov 2026)
# Each has a consequence that carries forward: a refused ultimatum comes back as a hostile amendment at the Summit
# (g["threats"]); a confidence broken turns its source against you; a bluff or a betrayal comes back in the press.

MORE = ("ultimatum", "bargain", "mediate", "leak", "old_sins", "olive", "staff")


def _more(scn, g, rng) -> list[dict]:
    out, tick = [], g.get("tick", 0)
    free = _free(scn, g)
    others = E._others(g)
    # an ultimatum: a rival demands you drop part of a clause, or it will table a hostile amendment at the Summit
    for rv in g["rivals"]:
        if rv.get("truce") or rng.random() > 0.3:
            continue
        c = next((c for c in g["draft"] if rv["block"] in c["tags"] and rv["block"] != g["mandate"]["red"]), None)
        if c and not any(t["iso3"] == rv["iso3"] for t in g.get("threats", [])):
            n = g["draft"].index(c) + 1
            out.append({"id": f"v{tick}-ult-{rv['iso3']}", "kind": "ultimatum", "iso3": rv["iso3"], "clause": c["id"], "tag": rv["block"],
                        "text": f"{scn.member(rv['iso3']).name}'s delegate, coldly: \u201cTake out the part of clause {n} that "
                                f"{_label(scn, rv['block'])}, or we table an amendment against it at the Summit, and we will win.\u201d",
                        "options": [{"code": "yield", "label": "Agree to take it out", "cost": 0},
                                    {"code": "call", "label": "Call their bluff", "cost": 0},
                                    {"code": "talk", "label": "Offer to talk it over (1 action)", "cost": 0, "ap": 1}]})
            break
    # a bloc bargain: a group's coordinator offers its endorsement for a commitment its members want
    regs = sorted({scn.member(i).region for i in free if scn.member(i).region in E.REGIONS})
    if regs and rng.random() < 0.3:
        reg = rng.choice(regs)
        mem = [i for i in E._region_members(scn, reg) if i not in others and i != g["iso3"]]
        have = {t for c in g["draft"] for t in c["tags"]}
        want = max((t for t in scn.tags if t not in have and t != g["mandate"]["red"]),
                   key=lambda t: sum(E.mu_of(scn, g, i, [t]) for i in mem), default=None)
        if mem and want and g["endorse"].get(reg) != "you" and sum(E.mu_of(scn, g, i, [want]) for i in mem) > 0:
            coord = max(mem, key=lambda i: (len(i), i))
            out.append({"id": f"v{tick}-bargain-{reg}", "kind": "bargain", "iso3": coord, "region": reg, "tag": want,
                        "text": f"The coordinator of the {E.REGIONS[reg]}: \u201cPut a clause in the draft that {_label(scn, want)}, "
                                "and our group will stand behind your draft.\u201d",
                        "options": [{"code": "accept", "label": "Agree: you'll table it", "cost": 0},
                                    {"code": "refuse", "label": "Decline politely", "cost": 0}]})
    # mediation: two delegations in a dispute ask you to settle it
    if len(free) >= 4 and rng.random() < 0.25:
        a, b = rng.sample(free, 2)
        out.append({"id": f"v{tick}-mediate-{a}-{b}", "kind": "mediate", "iso3": a, "other": b,
                    "text": f"{scn.member(a).name} and {scn.member(b).name} have fallen out over the wording of the draft, "
                            "and both look to you.",
                    "options": [{"code": "side_a", "label": f"Back {scn.member(a).name}", "cost": 0},
                                {"code": "side_b", "label": f"Back {scn.member(b).name}", "cost": 0},
                                {"code": "mediate", "label": "Bring them together (1 action)", "cost": 0, "ap": 1}]})
    # a leak: a delegate tells you a rival's plan, in confidence
    plan = next(((k, x) for k, x in g.get("intent", {}).items() if x), None)
    if plan and free and rng.random() < 0.3:
        src = rng.choice(free)
        out.append({"id": f"v{tick}-leak-{src}", "kind": "leak", "iso3": src, "rival": plan[0],
                    "text": f"{scn.member(src).name}'s delegate, quietly: \u201c" + VO.visit(
                        scn, g, src, "leak", rival=scn.member(plan[0]).name,
                        target=E._target_name(scn, g, plan[1]["kind"], plan[1]["target"])) + "\u201d",
                    "options": [{"code": "keep", "label": "Thank them, and keep it in confidence", "cost": 0},
                                {"code": "expose", "label": "Expose the plan in the room", "cost": 0}]})
    # old sins: a betrayal or a bluff that came out reaches the press
    sins = g.get("rep", {}).get("broken", 0) + sum(1 for x in g["log"][-12:] if "misled" in x.get("text", ""))
    if sins and g.get("sins_asked", 0) < sins and rng.random() < 0.5:
        g["sins_asked"] = g.get("sins_asked", 0) + 1
        out.append({"id": f"v{tick}-sins", "kind": "old_sins", "iso3": g["iso3"], "who": "press",
                    "text": "A journalist: \u201cIs it true you broke your word to another delegation? The corridors are talking.\u201d",
                    "options": [{"code": "apologise", "label": "Admit it and apologise", "cost": 0},
                                {"code": "deny", "label": "Deny it", "cost": 0},
                                {"code": "evasive", "label": "No comment", "cost": 0}]})
    # an olive branch: a cool delegation offers to soften, for your backing
    cool = [i for i in free if relation(g, i) <= -1]
    if cool and rng.random() < 0.3:
        iso = rng.choice(cool)
        cl = E._their_clause(scn, g, iso)
        if cl:
            n = g["draft"].index(cl) + 1
            out.append({"id": f"v{tick}-olive-{iso}", "kind": "olive", "iso3": iso, "clause": cl["id"],
                        "text": f"{scn.member(iso).name}'s delegate: \u201c{VO.visit(scn, g, iso, 'olive', n=n)}\u201d",
                        "options": [{"code": "accept", "label": "Shake on it", "cost": 0},
                                    {"code": "refuse", "label": "Not today", "cost": 0}]})
    # your own staff: an adviser asks to be posted where their expertise fits
    idle = [x for x in g.get("staff", []) if not x.get("post")]
    if idle and free and not T.locked(g, "post") and rng.random() < 0.35:     # not before Staff is open (Ben, 10 Nov)
        adv = idle[0]
        target = (rng.choice(g["rivals"])["iso3"] if adv["kind"] == "analyst" and g["rivals"] else rng.choice(free))
        out.append({"id": f"v{tick}-staff-{adv['id']}", "kind": "staff", "iso3": g["iso3"], "who": "staff", "adviser": adv["id"], "target": target,
                    "text": f"{adv['name']}, your {K.STAFF_KINDS[adv['kind']]['name'].lower()}: \u201cAmbassador, post me to "
                            f"{scn.member(target).name}. I know that delegation, and I'd learn a great deal.\u201d",
                    "options": [{"code": "post", "label": f"Post them to {scn.member(target).name} (travel: {E.R['post_cost']} Influence)", "cost": E.R["post_cost"]},
                                {"code": "not_now", "label": "Not now", "cost": 0}]})
    return out


def answer_new(scn, g, v, c, out):
    iso, name = v["iso3"], scn.member(v["iso3"]).name
    k = v["kind"]
    if k == "ultimatum":
        rv = next(r for r in g["rivals"] if r["iso3"] == iso)
        cl = next((x for x in g["draft"] if x["id"] == v["clause"]), None)
        if c == "yield" and cl and v["tag"] in cl["tags"]:
            new = [t for t in cl["tags"] if t != v["tag"]]
            E._break_promises_if_changed(scn, g, cl, new)
            E._hist(scn, g, cl, "you", f"removed under pressure from {name}: " + E._lc(scn.tags[v["tag"]]).rstrip("."), new or None)
            if new:
                cl["tags"] = new
            else:
                g["draft"].remove(cl)
            rv["grudge"] = 0
            _rep(g, "honest")
            E._log(g, "you", f"You gave way to {name}'s ultimatum.", "action", iso)
            out["reply"] = "\u201cA wise choice, Ambassador.\u201d"
        elif c == "talk":
            rv["grudge"] = max(0, rv.get("grudge", 0) - 1)
            rv["hold"] = g.get("tick", 0) + 1
            E._log(g, "you", f"You talked {name} down from its ultimatum, for now.", "action", iso)
            out["reply"] = "\u201cVery well. We'll hold off. For now.\u201d"
        else:
            g.setdefault("threats", []).append({"iso3": iso, "tag": v["tag"]})
            rv["grudge"] = rv.get("grudge", 0) + 1
            _rep(g, "hard")
            E._log(g, iso, f"You called {name}'s bluff. It will table an amendment at the Summit.", "warning", iso)
            out["reply"] = "\u201cThen we'll see you at the Summit.\u201d"
    elif k == "bargain":
        mem = [i for i in E._region_members(scn, v["region"]) if i not in E._others(g) and i != g["iso3"]]
        if c == "accept":
            g.setdefault("bargains", []).append({"region": v["region"], "tag": v["tag"], "iso3": iso, "kept": None})
            for i in mem:
                E._sway(g, "you", i, 0.15)
            E._log(g, "you", f"You agreed with the {E.REGIONS[v['region']]}: a clause that {_label(scn, v['tag'])}, for its support.", "action", iso)
            out["reply"] = "\u201cTable it, and you'll have us.\u201d"
        else:
            for i in mem:
                E._sway(g, "you", i, -0.05)
    elif k == "mediate":
        a, b = iso, v["other"]
        if c == "side_a":
            E._sway(g, "you", a, 0.3)
            E._sway(g, "you", b, -0.3)
        elif c == "side_b":
            E._sway(g, "you", b, 0.3)
            E._sway(g, "you", a, -0.3)
        else:
            E._sway(g, "you", a, 0.2)
            E._sway(g, "you", b, 0.2)
            _rep(g, "honest")
        E._log(g, "you", {"side_a": f"You backed {name}.", "side_b": f"You backed {scn.member(b).name}.",
                          "mediate": f"You brought {name} and {scn.member(b).name} together."}[c], "action", iso)
    elif k == "leak":
        rv = next((r for r in g["rivals"] if r["iso3"] == v["rival"]), None)
        if c == "keep":
            g["trust"][iso] = min(E.R["trust_max"], g["trust"].get(iso, 0) + 1)
            E._log(g, iso, f"{name} trusted you with a rival's plan.", "intel", v["rival"])
        else:
            g.get("intent", {})[v["rival"]] = None                  # the plan is blown
            g["trust"][iso] = max(-E.R["trust_max"], g["trust"].get(iso, 0) - 2)
            E._sway(g, "you", iso, -0.3)
            if rv:
                rv["grudge"] = rv.get("grudge", 0) + 1
            E._log(g, "you", f"You exposed {scn.member(v['rival']).name}'s plan. {name} knows who gave it away.", "warning", iso)
    elif k == "old_sins":
        if c == "apologise":
            g["respect"] = max(0, g["respect"] - 1)
            _rep(g, "honest")
            out["reply"] = "\u201cThat's a rare thing to hear in this building.\u201d"
        elif c == "deny":
            if _rng(g, "deny").random() < 0.5:
                g["respect"] = max(0, g["respect"] - 2)
                _rep(g, "bluff")
                out["reply"] = "\u201cWe have it from three delegations, Ambassador.\u201d"
            else:
                out["reply"] = "\u201cIf you say so.\u201d"
        else:
            g["respect"] = max(0, g["respect"] - 1)
        E._log(g, "you", "The press asked about your broken word.", "action")
    elif k == "olive":
        if c == "accept":
            g["promises"].append({"iso3": iso, "clause": v["clause"], "kept": None})
            g.setdefault("deal_votes", {})[iso] = "abstain"
            g["trust"][iso] = min(E.R["trust_max"], max(0, g["trust"].get(iso, 0)) + 1)
            E._log(g, "you", f"You made peace with {name}: you back its clause, it abstains on your draft.", "action", iso)
            out["reply"] = "\u201cThen we have an understanding.\u201d"
    elif k == "staff":
        adv = next((x for x in g.get("staff", []) if x["id"] == v["adviser"]), None)
        if adv and c == "post":
            E._move_adviser(scn, g, adv, v["target"], paid=True)    # the travel (paid as the answer's cost), and who they leave
            E._xp(g, adv, f"{adv['name']} got the posting they asked for.")    # keen: they learn faster
            E._log(g, "staff", f"{adv['name']} is now studying {scn.member(v['target']).name}.", "staff")
        elif adv:
            adv["xp"] = max(0, adv["xp"] - 1)
            E._log(g, "staff", f"{adv['name']} is disappointed.", "staff")
    return out
