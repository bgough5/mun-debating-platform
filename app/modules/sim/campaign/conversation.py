"""The Session: talking with a delegation (Ben's playtest, 11 Nov 2026: talks were predictable and repetitive).

A conversation now runs like this:
1. greet (free): you go over, and they lead with what is on their mind right now, drawn from the game: a promise you
   broke, your aim being their red line, a rival courting them, a promise you owe them, a clause they dislike, or a
   commitment they want. They may open with your record with them.
2. your opening (spends the action): an argument (as before), a word on their concern, or a tone: empathise,
   challenge, bargain, flatter or warn. Each tone has a price or a risk.
3. their reply, and your follow-up: press, turn to another argument, change tone, ask where they stand, or leave it.
4. sometimes a third exchange: a talk going very well can be sealed (for a little Influence, they pledge), and one
   going badly can be repaired (for a little Influence) or left.

What they tell you at the end depends on how they feel about you and how they speak: a hostile or guarded delegation,
or a rival, keeps its counsel; a warm one tells you how it would vote and where it leans. Lines never repeat within a
game while unused ones remain (voices.pick). Pure functions of the game: seeded, so engine.apply stays pure.
"""
from __future__ import annotations

import random

from app.modules.sim.campaign import engine as E
from app.modules.sim.campaign import talks as T
from app.modules.sim.campaign import voices as VO

TONES = {
    "empathise": ("Empathise", "Acknowledge their position. Safe and warm, but it moves them little."),
    "challenge": ("Challenge them", "Push back hard. Lands with those already leaning your way or who like plain talk; backfires on the rest."),
    "bargain": ("Bargain", "Offer something from your mission. Reliable, but costs 2 Influence."),
    "flatter": ("Flatter", "Appeal to their standing. Formal and warm delegations like it; plain-speaking ones don't."),
    "warn": ("Warn them", "Tell them where the room is going. Moves them if the room really is with you; it always costs trust."),
}
BARGAIN_COST, SEAL_COST, REPAIR_COST = 2, 1, 1

# what they lead with (placeholders filled from the game; Fable writes these in each delegation's voice)
CONCERN = {
    "betrayed": ["You broke your word to us. Why should we listen now?", "We haven't forgotten what happened last time. Speak carefully.",
                 "My capital asked me not to talk to you at all. I'm here anyway. Make it worth it."],
    "redline": ["Your main aim is a line my government will not cross. Let's be honest about that.",
                "Before you start: what you want most is what we can't accept.", "We both know where we stand on your main aim."],
    "courted": ["{rival} was here an hour ago, with a generous offer.", "{rival} has been very attentive to us this week.",
                "I'll be frank: {rival} wants our vote too, and asks less of us."],
    "owed": ["You promised to back clause {n}. We're counting on it.", "Clause {n}, Ambassador. You gave us your word.",
             "We trust clause {n} still has your support?"],
    "dislike": ["Clause {n} troubles us. As it stands, it's hard for us to accept.", "Our capital has real doubts about clause {n}.",
                "I need to talk to you about clause {n}. It's a problem for us."],
    "want": ["What we'd really like to see is a clause that {label}.", "Our capital keeps asking for a clause that {label}.",
             "Give us a clause that {label}, and you'd find us much easier to work with."],
    "listening": ["We're listening, Ambassador.", "What can we do for you?", "You have our attention, for a few minutes."],
}
CALLBACK = {
    "kept": ["You kept your word to us before. That counts for something.", "You've been as good as your word with us."],
    "deal": ["We have our understanding, and we're keeping to it.", "Our arrangement stands, Ambassador."],
    "lied": ["Last time, what you told us turned out not to be true.", "We checked what you told us last time. It wasn't so."],
}
TONE_REPLY = {
    "empathise": {"good": ["Thank you. Not everyone here bothers to understand us.", "That's kind of you to say. It helps."],
                  "bad": ["Understanding is pleasant. It isn't a reason to vote.", "Kind words, Ambassador. We need more than that."]},
    "challenge": {"good": ["Fair. We needed someone to say it plainly.", "Hm. You may be right. Go on."],
                  "bad": ["I don't care for your tone, Ambassador.", "We won't be lectured. Not by you."]},
    "bargain": {"good": ["Now that is an offer we can take home.", "Interesting. That changes the arithmetic for us."],
                "bad": ["An offer, yes. Not enough of one."]},
    "flatter": {"good": ["You're very gracious. My government appreciates being heard.", "That is generous, and not untrue."],
                "bad": ["Please, Ambassador. Spare us the compliments.", "Flattery won't get you far with us."]},
    "warn": {"good": ["If the room is really moving, we'd rather not be left behind.", "Noted. We don't want to be on the wrong side of this."],
             "bad": ["Is that a threat? The room isn't where you think it is.", "We'll take our chances, thank you."]},
    "address": {"good": ["Thank you for taking that seriously. It matters to us.", "That goes a long way with us."],
                "bad": ["Words. We'll see what you actually do.", "I hear you. I'm not yet reassured."]},
}
WITHHOLD = ["We'd rather keep our own counsel on that.", "That's a matter for our capital, Ambassador.",
            "I'm not in a position to say. Not to you, not yet.", "You'll understand if I don't show you our cards."]
THIRD = {
    "warm": ["We could go further, if you could do something for us in return.", "There may be a way to make this firm between us."],
    "cold": ["I think this conversation has run its course.", "We seem to be getting nowhere, Ambassador."],
}


def _rng(g, iso, salt):
    return random.Random(f"{g['seed']}:conv:{g.get('tick', 0)}:{g.get('n', 0)}:{iso}:{salt}")


def _n(g, clause_id):
    return next((i + 1 for i, c in enumerate(g["draft"]) if c["id"] == clause_id), None)


def concern(scn, g, iso) -> dict:
    """What is on this delegation's mind right now, most pressing first."""
    if any(p["iso3"] == iso and p["kept"] is False for p in g["promises"]) or iso in {gr["iso3"] for gr in g.get("grievances", [])}:
        return {"kind": "betrayed"}
    if E.mu_of(scn, g, iso, [g["mandate"]["must"]]) <= E.R["redline"]:
        return {"kind": "redline"}
    rival = T._courted(scn, g, iso)
    if rival:
        return {"kind": "courted", "rival": scn.member(rival).name}
    owed = next((p for p in g["promises"] if p["iso3"] == iso and p["kept"] is None and _n(g, p["clause"])), None)
    if owed:
        return {"kind": "owed", "n": _n(g, owed["clause"])}
    worst = min(((E.mu_of(scn, g, iso, c["tags"]), c) for c in g["draft"] if c["tags"]), key=lambda x: x[0], default=None)
    if worst and worst[0] < -0.4:
        return {"kind": "dislike", "n": _n(g, worst[1]["id"])}
    have = set(E.final_clause(g)["tags"])
    wants = sorted(((E.mu_of(scn, g, iso, [t]), t) for t in scn.tags if t not in have), reverse=True)
    if wants and wants[0][0] > 0.6:
        return {"kind": "want", "label": E._lc(scn.tags[wants[0][1]]).rstrip(".")}
    return {"kind": "listening"}


def _callback(g, iso) -> str | None:
    if any(lie.get("iso3") == iso for lie in g.get("lies_found", [])):
        return "lied"
    if any(p["iso3"] == iso and p["kept"] is True for p in g["promises"]):
        return "kept"
    if iso in (g.get("deal_votes") or {}):
        return "deal"
    return None


def reveal(scn, g, iso) -> int:
    """How much they'll tell you: how they feel about you, how they speak, whether they're a rival, and whether one of
    your advisers knows them. 2 or more: everything; 1: how they'd vote; 0: how your case landed; below 0: nothing."""
    from app.modules.sim.campaign import visits as V
    level = V.relation(g, iso)
    reg = VO.voice(scn, g, iso)
    level += 1 if reg == "warm" else -1 if reg in ("guarded", "grave") else 0
    if any(r["iso3"] == iso for r in g["rivals"]):
        level -= 2
    if any(a.get("post") == iso for a in g.get("staff", [])):
        level += 1
    return level


def _line(g, key, options, rng):
    return VO.pick(g, key, options, rng)


def options(scn, g) -> list[dict]:
    cv = g["conv"]
    iso, stage = cv["iso3"], cv["stage"]
    known = set(T.listens_to(scn, g, iso))
    out = []
    if stage == "open":
        if cv["concern"]["kind"] != "listening":
            out.append({"code": "address", "group": "concern", "label": "Speak to their concern"})
        for k, a in T.ARGS.items():
            out.append({"code": "arg:" + k, "group": "argument", "label": a["name"], "what": a["what"],
                        "known": a["name"] in known, "used": T._used(g, iso, k) > 0})
        for k, (name, what) in TONES.items():
            out.append({"code": "tone:" + k, "group": "tone", "label": name, "what": what,
                        "cost": BARGAIN_COST if k == "bargain" else 0})
    elif stage == "reply":
        first = cv["moves"][0]
        out.append({"code": "press", "group": "move", "label": "Press the point"})
        for k, a in T.ARGS.items():
            if "arg:" + k != first:
                out.append({"code": "arg:" + k, "group": "argument", "label": "Turn to " + a["name"].lower(), "used": T._used(g, iso, k) > 0})
        for k, (name, what) in TONES.items():
            if "tone:" + k != first:
                out.append({"code": "tone:" + k, "group": "tone", "label": name, "what": what,
                            "cost": BARGAIN_COST if k == "bargain" else 0})
        out.append({"code": "ask", "group": "move", "label": "Ask where they stand"})
        out.append({"code": "close", "group": "move", "label": "Thank them and leave it there"})
    else:                                                       # the third exchange
        if cv["mood"] == "warm":
            out.append({"code": "seal", "group": "move", "label": f"Ask them to pledge their support ({SEAL_COST} Influence)", "cost": SEAL_COST})
        else:
            out.append({"code": "repair", "group": "move", "label": f"Try to repair it ({REPAIR_COST} Influence)", "cost": REPAIR_COST})
        out.append({"code": "close", "group": "move", "label": "Leave it there"})
    return out


def view(scn, g) -> dict | None:
    cv = g.get("conv")
    if not cv:
        return None
    if "stage" not in cv:                                       # a conversation from an older save
        cv.update(stage="reply", moves=["arg:" + cv["first"]], concern={"kind": "listening"}, qs=[0.5])
    first = cv["moves"][0] if cv["moves"] else None
    return {"iso3": cv["iso3"], "name": scn.member(cv["iso3"]).name, "stage": cv["stage"], "reply": cv["reply"],
            "concern": cv["concern"]["kind"], "said": cv.get("said"), "tone": cv.get("tone"),
            "first": first[4:] if first and first.startswith("arg:") else None,
            "first_name": T.ARGS[first[4:]]["name"] if first and first.startswith("arg:") else (cv.get("said") or ""),
            "options": options(scn, g)}


def greet(scn, g, iso) -> dict:
    E._country(scn, g, iso)
    if g.get("conv"):
        raise E.GameError("Finish the conversation you're in first.")
    c = concern(scn, g, iso)
    rng = _rng(g, iso, "greet")
    parts = []
    cb = _callback(g, iso)
    if cb:
        parts.append(_line(g, "callback:" + cb, CALLBACK[cb], rng))
    parts.append(_line(g, "concern:" + c["kind"], CONCERN[c["kind"]], rng).format(**{k: v for k, v in c.items() if k != "kind"}))
    g["conv"] = {"iso3": iso, "stage": "open", "concern": c, "reply": " ".join(parts), "moves": [], "qs": [],
                 "red": c["kind"] == "redline", "cost": 0, "trust": 0, "ask": False, "said": None}
    return {"conv": view(scn, g)}


def _move_q(scn, g, iso, code, cv) -> tuple[float, str, str | None]:
    """How well a move lands (q), what you did (for the log), and the tone of their reply ('good'/'bad' or None)."""
    from app.modules.sim.campaign import visits as V
    r = {k: x * T.REPEAT ** T._used(g, iso, k) for k, x in T.receptive(scn, g, iso).items()}
    reg = VO.voice(scn, g, iso)
    rel = V.relation(g, iso)
    if code.startswith("arg:") and code[4:] in T.ARGS:
        k = code[4:]
        return r[k], "made the case on " + T.ARGS[k]["name"].lower(), None
    if code == "address":
        q = 0.85 if rel >= 0 else 0.55
        return q, "spoke to their concern", "good" if q >= 0.8 else "bad"
    tone = code[5:] if code.startswith("tone:") else None
    if tone == "empathise":
        cv["trust"] += 1
        return 0.55, "showed you understood them", "good"
    if tone == "challenge":
        ok = E.lean(scn, g, "you", iso) > 0.2 or reg in ("blunt", "measured")
        if not ok:
            cv["trust"] -= 1
        return (1.05 if ok else 0.25), "challenged them", "good" if ok else "bad"
    if tone == "bargain":
        E._spend(g, 0, BARGAIN_COST)
        return 1.0, "made them an offer", "good"
    if tone == "flatter":
        q = 0.9 if reg in ("grave", "warm") else 0.3 if reg in ("blunt", "measured") else 0.6
        return q, "flattered them", "good" if q >= 0.6 else "bad"
    if tone == "warn":
        cv["trust"] -= 1
        p = E.projection(scn, g)
        cast = p["yes"] + p["no"]
        ok = cast > 0 and p["yes"] / cast >= 0.6               # the room really is with you
        return (1.0 if ok else 0.3), "warned them where the room was going", "good" if ok else "bad"
    raise E.GameError("Choose what to say.")


def follow(scn, g, a) -> dict:
    cv = g.get("conv")
    if not cv:
        raise E.GameError("You aren't in a conversation.")
    if "stage" not in cv:
        view(scn, g)
    iso, choice = cv["iso3"], a.get("choice") or "close"
    rng = _rng(g, iso, "follow" + str(len(cv["moves"])))
    if cv["stage"] == "open":
        if choice == "close":                                  # walked away before saying anything: nothing spent
            g["conv"] = None
            return {"talked": None, "left": True}
        cost = E.lobby_cost(scn, g, iso)
        E._spend(g, 1, cost)
        cv["cost"] = cost
        q, did, mood = _move_q(scn, g, iso, choice, cv)
        cv["moves"].append(choice)
        cv["qs"].append(q)
        cv["said"] = did
        if cv["red"]:
            cv["reply"] = VO.red_line(scn, g, iso, "open")
            cv["tone"] = "red"
        elif mood is None:                                     # an argument: their reaction in their own voice
            level = T._word(q)
            memory = T._memory(scn, g, iso, choice[4:])[0]      # "you've made that case to us before"
            cv["reply"] = memory + VO.react(scn, g, iso, level, rng)
            cv["tone"] = level
        else:
            key = choice[5:] if choice.startswith("tone:") else "address"
            cv["reply"] = _line(g, f"tone:{key}:{mood}", TONE_REPLY[key][mood], rng)
            cv["tone"] = "strong" if mood == "good" else "weak"
        cv["stage"] = "reply"
        return {"conv": view(scn, g)}
    if cv["stage"] == "reply":
        q1 = cv["qs"][0]
        if choice == "press":
            q = min(1.15, q1 * 1.2) if q1 >= 0.9 else q1 * 0.6
        elif choice == "ask":
            q, cv["ask"] = q1 * 0.6, True
        elif choice == "close":
            q = q1 * 0.75
        else:
            q2, _did, _mood = _move_q(scn, g, iso, choice, cv)
            q = (q1 + q2) / 2
            cv["moves"].append(choice)
        cv["qs"].append(q)
        if not cv["red"] and choice not in ("close", "ask") and (q >= 1.0 or q <= 0.3):
            cv["stage"], cv["mood"] = "third", "warm" if q >= 1.0 else "cold"
            cv["reply"] = _line(g, "third:" + cv["mood"], THIRD[cv["mood"]], rng)
            cv["tone"] = "strong" if cv["mood"] == "warm" else "weak"
            return {"conv": view(scn, g)}
        return _finish(scn, g, q, choice)
    q = cv["qs"][-1]                                           # the third exchange
    if choice == "seal" and cv.get("mood") == "warm":
        E._spend(g, 0, SEAL_COST)
        if iso not in g.setdefault("pledges", []):
            g["pledges"].append(iso)
        q = min(1.2, q + 0.1)
    elif choice == "repair" and cv.get("mood") == "cold":
        E._spend(g, 0, REPAIR_COST)
        cv["trust"] += 1
        q = max(q, 0.5)
    return _finish(scn, g, q, choice)


def _finish(scn, g, q, choice) -> dict:
    cv = g.pop("conv")
    g["conv"] = None
    iso = cv["iso3"]
    q += T._memory(scn, g, iso, cv["moves"][0][4:] if cv["moves"][0].startswith("arg:") else "")[1]
    args = [m[4:] for m in cv["moves"] if m.startswith("arg:")]
    g.setdefault("talked", {}).setdefault(iso, []).append({"args": args, "tones": [m[5:] for m in cv["moves"] if m.startswith("tone:")],
                                                           "q": round(q, 2), "tick": g.get("tick", 0)})
    tmax = E.R["trust_max"]
    g["trust"][iso] = max(-tmax, min(tmax, g["trust"].get(iso, 0) + cv["trust"]))
    mu = E.mu_of(scn, g, iso, [g["mandate"]["must"]])
    if cv["red"]:
        moved = E._sway(g, "you", iso, E.R["redline_step"])
        heard = VO.red_line(scn, g, iso, "close")
    else:
        moved = E._sway(g, "you", iso, E.R["pitch_step"] * (0.3 + 0.7 * q))
        heard = T._answer(scn, g, iso, q, mu)
    if q >= 0.5:
        for adv in g.get("staff", []):
            if adv.get("post") == iso:
                E._xp(g, adv, f"Their briefing helped your talk with {scn.member(iso).name}.")
    g["region_last"][scn.member(iso).region] = "you"
    how = {"press": "pressed the point", "ask": "asked where they stand", "close": "left it there", "seal": "asked for their pledge",
           "repair": "tried to repair it"}.get(choice, "changed tack")
    E._log(g, "you", f"You talked with {scn.member(iso).name}: you {cv['said']} and {how}.", "action", iso)
    out = {"heard": heard, "moved": round(moved, 2), "cost": cv["cost"], "red_line": bool(cv["red"]), "talked": iso,
           "how": how, "q": round(q, 2), "landed": {}, "pledged": choice == "seal"}
    level = reveal(scn, g, iso) + (1 if cv.get("ask") else 0)
    if level < 0:
        out["withheld"] = _line(g, "withhold", WITHHOLD, _rng(g, iso, "withhold"))
        return out
    r = T.receptive(scn, g, iso)
    out["landed"] = {k: T._word(r[k]) for k in args}
    open_stage = g["length"] == "quick" or g["chapter"] >= 2
    if level >= 1 and (open_stage or cv.get("ask")) and E.final_clause(g)["tags"]:
        rd = E.reading(scn, g, iso)                             # honest: firm, leaning or wavering (Fable, 11 Nov)
        out["would_vote"], out["would_sure"], out["would_says"] = rd["vote"], rd["sure"], E.reading_words(rd)["says"]
    if level >= 2:
        out["leans"] = {scn.member(rv["iso3"]).name: round(E.lean(scn, g, rv["iso3"], iso), 2) for rv in g["rivals"]}
    return out
