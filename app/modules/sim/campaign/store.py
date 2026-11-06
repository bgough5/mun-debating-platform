"""Keeping The Session's games (D-101), and what the game page is shown.

- **Signed-in students:** each campaign is a row in `campaign_save`, readable only by that student. Moves update
  the row directly; the change log gets a one-line note per move, not a copy of the whole game (a game is tens of
  kilobytes and a session is hundreds of moves).
- **Guests:** nothing is stored. The game lives in the browser. The server signs each state it returns (an HMAC
  with a key kept in `app_setting`), and only accepts a state back with a valid signature, so a guest can't edit
  their way to a win.
- **Scenarios:** read once per pack and kept for the life of the process. Every campaign uses the pack's shared
  hidden committee (the one guest Quick vote uses, D-099), which nothing in a campaign ever changes.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import threading

from app.db import SYSTEM, one, rows, scalar
from app.errors import UserError
from app.modules.mun.worldmap import REGIONS
from app.modules.sim.campaign import content as K
from app.modules.sim.campaign import econ as X
from app.modules.sim.campaign import engine as E
from app.modules.sim.campaign import talks as T
from app.modules.sim.campaign import visits as VI
from app.modules.sim.campaign.scenario import Scenario, load, rebind
from app.util import now_iso

_SCN: dict[str, Scenario] = {}
LOCK = threading.RLock()        # a scenario reads through one connection at a time
MAX_STATE = 400_000             # bytes: a guest state larger than this is refused


def scenario(db, conn, code: str) -> Scenario:
    """The scenario for a pack, installed the first time (as the shared guest committee) and then cached."""
    from app.modules.mun.packfile import available
    from app.modules.sim import play
    if code not in {p["code"] for p in available()}:
        raise UserError("That scenario isn't available.", 404)
    with LOCK:
        cid = scalar(conn, "SELECT id FROM committee WHERE guest_pack = ? AND deleted_at IS NULL ORDER BY id LIMIT 1", (code,))
        if not cid:
            with db.write(SYSTEM) as w:
                cid = play.guest_committee(w, code)
        scn = _SCN.get(code)
        if scn is None or scn.committee_id != cid:
            scn = _SCN[code] = load(conn, cid, code)
        return rebind(scn, conn)


def forget() -> None:
    """Drop cached scenarios (after a restore or a pack edit)."""
    with LOCK:
        _SCN.clear()


# ---------------------------------------------------------------- guests: signed states

def _key(db) -> bytes:
    with db.read() as conn:
        k = scalar(conn, "SELECT value FROM app_setting WHERE key = 'campaign_key'")
    if not k:
        with db.write(SYSTEM) as w:
            k = scalar(w.conn, "SELECT value FROM app_setting WHERE key = 'campaign_key'")
            if not k:
                k = secrets.token_hex(32)
                w.conn.execute("INSERT INTO app_setting (key, value) VALUES ('campaign_key', ?)", (k,))
    return bytes.fromhex(k)


def _norm(x):
    """Numbers as a browser keeps them: JavaScript writes 0.0 as 0, so whole numbers are signed as integers."""
    if isinstance(x, float):
        return int(x) if x.is_integer() else round(x, 6)
    if isinstance(x, dict):
        return {k: _norm(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_norm(v) for v in x]
    return x


def _canon(state: dict) -> bytes:
    return json.dumps(_norm(state), sort_keys=True, separators=(",", ":")).encode()


def sign(db, state: dict) -> str:
    return hmac.new(_key(db), _canon(state), hashlib.sha256).hexdigest()


def verify(db, state, sig) -> dict:
    if not isinstance(state, dict) or not isinstance(sig, str) or len(_canon(state)) > MAX_STATE:
        raise UserError("That game can't be loaded. Start a new session.", 400)
    if not hmac.compare_digest(sign(db, state), sig):
        raise UserError("That game has been changed outside the platform, so it can't continue. Start a new session.", 400)
    return state


# ---------------------------------------------------------------- signed-in students: saved campaigns

def save_new(w, student_id: int, g: dict) -> int:
    t = now_iso()
    return w.insert("campaign_save", {"student_id": student_id, "pack": g["pack"], "iso3": g["iso3"], "length": g["length"],
                                      "difficulty": g["difficulty"], "path": g["path"], "phase": g["phase"], "chapter": g["chapter"],
                                      "grade": None, "state_json": json.dumps(g), "created_at": t, "updated_at": t})


def save_move(w, save_id: int, g: dict, action: dict) -> None:
    grade = g["result"]["grade"] if g.get("result") else None
    w.conn.execute("UPDATE campaign_save SET state_json = ?, phase = ?, chapter = ?, grade = ?, updated_at = ? WHERE id = ?",
                   (json.dumps(g), g["phase"], g["chapter"], grade, now_iso(), save_id))
    w.log("campaign_save", save_id, "move", None, {"do": action.get("do"), "phase": g["phase"], "chapter": g["chapter"]})


def mine(conn, save_id: int, student_id: int) -> dict:
    r = one(conn, "SELECT * FROM campaign_save WHERE id = ? AND deleted_at IS NULL", (save_id,))
    if not r:
        raise UserError("That session doesn't exist.", 404)
    if r["student_id"] != student_id:
        raise UserError("That session belongs to someone else.", 403)
    return {**r, "state": json.loads(r["state_json"])}


def my_saves(conn, student_id: int) -> list[dict]:
    from app.modules.mun.packfile import available
    titles = {p["code"]: p["title"] for p in available()}
    out = []
    for r in rows(conn, "SELECT id, pack, iso3, length, difficulty, path, phase, chapter, grade, updated_at FROM campaign_save "
                        "WHERE student_id = ? AND deleted_at IS NULL ORDER BY updated_at DESC LIMIT 20", (student_id,)):
        c = one(conn, "SELECT name FROM country WHERE iso3 = ?", (r["iso3"],))
        out.append({**r, "title": titles.get(r["pack"], r["pack"]), "country": c["name"] if c else r["iso3"],
                    "where": "Finished" if r["phase"] == "done" else ("The Summit" if r["phase"] == "summit" else f"Chapter {r['chapter']}"),
                    "medal": E.GRADES.get(r["grade"]) if r["grade"] is not None else None})
    return out


# ---------------------------------------------------------------- setup: what the new-session screens offer

def scenario_cards() -> list[dict]:
    from app.modules.mun.packfile import available
    types = {"sc": "Security Council", "ga_plenary": "General Assembly", "ga_third": "GA Third Committee"}
    out = []
    for p in available():
        lvl = K.SCENARIO_LEVEL.get(p["code"], "standard")
        out.append({"code": p["code"], "title": p["title"], "summary": p.get("summary", ""), "type": types.get(p.get("type"), ""),
                    "fictional": bool(p.get("fictional")), "level": lvl, "level_name": K.LEVEL_NAMES[lvl]})
    order = {"beginner": 0, "standard": 1, "expert": 2}
    return sorted(out, key=lambda c: (order[c["level"]], c["title"]))


def country_choices(scn: Scenario) -> list[dict]:
    """Every seat, with how hard it is to play: how many delegations share your main instruction."""
    out = []
    for m in scn.members:
        mand = E.mandate_for(scn, m.iso3)
        friends = sum(1 for o in scn.members if o.iso3 != m.iso3 and (scn.positions.get(o.iso3, {}).get(mand["must"]) or 0) >= 1)
        share = friends / max(1, len(scn.members) - 1)
        hard = "Easier" if share >= 0.5 else "Harder" if share < 0.25 else "Balanced"
        out.append({"iso3": m.iso3, "name": m.name, "region": REGIONS.get(m.region, ""), "p5": m.p5, "seat": hard,
                    "allies": friends, "veto": m.iso3 in scn.rule.veto})
    return sorted(out, key=lambda c: c["name"])


# ---------------------------------------------------------------- what the game page shows

def _name(scn: Scenario, g: dict, actor: str) -> str:
    if actor in ("you", g["iso3"]):
        return "You"
    if actor == "draft":
        return "Original draft"
    m = scn.member(actor)
    return m.name if m else actor


def view(scn: Scenario, g: dict) -> dict:
    tags = scn.tags
    L = E.LENGTHS[g["length"]]
    q = next((x for x in K.QUESTIONS if x["id"] == g.get("question")), None)
    final = {"id": "final", "tags": list(dict.fromkeys(t for c in g["draft"] for t in c["tags"])), "author": "draft"}
    chapters = g["phase"] == "chapter"
    tokens = {}
    open_promise = {pr["iso3"] for pr in g["promises"] if pr["kept"] is None}
    for iso in scn.isos:
        m = scn.member(iso)
        base = {"name": m.name, "p5": m.p5, "veto": iso in scn.rule.veto, "region": REGIONS.get(m.region, ""), "group": m.group, "rcode": m.region}
        if iso == g["iso3"]:
            tokens[iso] = {**base, "you": True, "dossier": X.profile(iso)}
            continue
        rival = any(r["iso3"] == iso for r in g["rivals"])
        t = {**base, "rival": rival, "trust": g["trust"].get(iso, 0), "lean": round(E.lean(scn, g, "you", iso), 2),
             "sway": round(g["sway"]["you"].get(iso, 0.0), 2), "read": iso in g["read"],
             "signed": "sponsor" if iso in g["sponsors"] else "signatory" if iso in g["signatories"] else None,
             "pledged": iso in g.get("pledges", []), "favour": iso in g["favours"], "promised": iso in open_promise,
             "predicted": g["whip"].get(iso), "secured": iso in g.get("secured", []),
             "studied_by": next((a["name"] for a in g.get("staff", []) if a.get("post") == iso), None),
             "sphere": _sphere(scn, g, iso),
             "est": None if rival or not final["tags"] else E._deal_vote(scn, g, iso, final, E.vote_of(scn, E.latent(scn, g, iso, final, mood=False))),
             "deal_vote": (g.get("deal_votes") or {}).get(iso)}
        t["dossier"] = X.profile(iso)
        t["relation"] = VI.relation(g, iso)
        t["talked"] = sorted({x for h in g.get("talked", {}).get(iso, []) for x in h["args"]})
        t["commitments"] = [c["what"] for c in T.ledger(scn, g, iso)]
        if iso in g["read"]:
            t["listens_to"] = T.listens_to(scn, g, iso)
        if rival and chapters:
            rv = next(r for r in g["rivals"] if r["iso3"] == iso)
            t["truce"] = bool(rv.get("truce"))
            t["peace_terms"] = list(T.compromise_terms(scn, g, rv)) if not rv.get("truce") else []
        if not rival and chapters:
            t["deal"] = E.deal_terms(scn, g, iso)
            t["lobby_cost"] = E.lobby_cost(scn, g, iso)
            t["promise_on"] = [c["id"] for c in g["draft"] if E.mu_of(scn, g, iso, c["tags"]) >= 0.4]
        if iso in g["read"]:
            t["file"] = E.country_file(scn, g, iso)
        tokens[iso] = t
    draft = []
    for c in g["draft"]:
        draft.append({"id": c["id"], "text": c["text"], "tags": [{"code": t, "label": tags[t]} for t in c["tags"]],
                      "author": _name(scn, g, c["author"]), "mine": c["author"] == "you",
                      "amended_by": [_name(scn, g, a) for a in c["amended_by"]], "stance": E.stance(scn, g, "you", c),
                      "own_words": bool(c.get("own_words")), "history": c.get("history", []), "stale": bool(c.get("text_stale")),
                      "now": ", ".join(E._lc(tags[t]).rstrip(".") for t in c["tags"]),
                      "chance": E.chance(scn, g, c, runs=200)["p_pass"] if chapters else None})
    regions = []
    for code, name in REGIONS.items():
        members = [i for i in scn.isos if scn.member(i).region == code]
        if not members:
            continue
        voters = [i for i in members if i not in E._others(g)]
        owner = g["endorse"].get(code)
        regions.append({"code": code, "name": name, "members": members, "owner": owner, "owner_name": _name(scn, g, owner) if owner else None,
                        "leaning": sum(1 for i in voters if E.lean(scn, g, "you", i) > E.R["lean_min"]), "voters": len(voters)})
    skills = [{"code": k, **v, "have": k in g["skills"],
               "can": k not in g["skills"] and g["xp"] >= K.SKILL_COST and (not v["needs"] or v["needs"] in g["skills"])}
              for k, v in K.SKILLS.items()]
    blocs = sorted({m.group for m in scn.members if m.group})
    last = g["chapter"] == E.LENGTHS[g["length"]]["chapters"]
    return {
        "v": E.VERSION, "pack": g["pack"], "title": scn.title, "fictional": scn.fictional, "phase": g["phase"],
        "chapter": g["chapter"], "turn": g["turn"], "chapters": L["chapters"], "turns": E.turns_now(g) if g["phase"] == "chapter" else L["turns"],
        "chapter_name": E.stage_names(g).get(g["chapter"], {}).get("name", ""),
        "goal": E.stage_names(g).get(g["chapter"], {}).get("goal", ""),
        "stage": _stage(scn, g), "stage_track": [{"n": n, "name": v["name"]} for n, v in E.stage_names(g).items()],
        "ap_sources": E.ap_sources(scn, g) if g["phase"] == "chapter" else [],
        "meeting": {"code": g["meeting"], "name": REGIONS[g["meeting"]], "attended": g.get("attended") == g.get("tick")}
                   if g.get("meeting") and g["phase"] == "chapter" else None,
        "rooms": _rooms(scn, g) if g["phase"] == "chapter" and (g["length"] == "quick" or g["chapter"] >= 2) else [],
        "race": _race(scn, g) if g["phase"] == "chapter" and (g["length"] == "quick" or g["chapter"] >= 3) else [],
        "ap": g["ap"], "influence": g["influence"], "respect": g["respect"], "expertise": g["expertise"], "xp": g["xp"],
        "you": {"iso3": g["iso3"], "name": scn.member(g["iso3"]).name},
        "mandate": {k: {"code": v, "label": tags[v]} for k, v in g["mandate"].items()},
        "path": {"code": g["path"], **K.PATHS[g["path"]]}, "difficulty": g["difficulty"], "length": g["length"],
        "rivals": [{"iso3": r["iso3"], "name": scn.member(r["iso3"]).name, "style": r.get("style", "hawk"), "truce": bool(r.get("truce")),
                    "style_name": K.RIVAL_STYLES[r.get("style", "hawk")]["name"], "style_what": K.RIVAL_STYLES[r.get("style", "hawk")]["what"],
                    **({"want": tags[r["want"]], "block": tags[r["block"]]} if "rival_intel" in g["skills"] else {})} for r in g["rivals"]],
        "crisis": g.get("crisis"), "offers": [{**o, "name": scn.member(o["iso3"]).name} for o in g.get("offers", [])] if chapters else [],
        "deals": g.get("deals", 0),
        "staff": [{**{k: a[k] for k in ("id", "name", "kind", "stars", "xp", "post")}, "kind_name": K.STAFF_KINDS[a["kind"]]["name"],
                   "what": K.STAFF_KINDS[a["kind"]]["what"], "rank": K.STAFF_RANKS[a["stars"]],
                   "next_star": E.PROMOTE.get(a["stars"] + 1), "post_name": scn.member(a["post"]).name if a.get("post") else None,
                   "report": a.get("report"), "starts": a.get("post") and g.get("tick", 0) <= a.get("since", 0)} for a in g.get("staff", [])],
        "staff_kinds": [{"code": k, **v} for k, v in K.STAFF_KINDS.items()],
        "reserve": g.get("reserve", 0), "secured": len(g.get("secured", [])),
        "agreements": T.ledger(scn, g) if chapters else [],
        "conv": T.conv_view(scn, g) if chapters else None,
        "budget": {"total": X.budget(g["iso3"]), "used": g.get("pledged", 0)},
        "deal_ready": g.get("deal_tick") != g.get("tick"), "deal_items": {"give": K.DEAL_GIVE, "get": K.DEAL_GET},
        "talks": T.talks_view(scn, g),
        "visits": [{**x, "name": {"minister": "Your Foreign Minister", "press": "A journalist"}.get(x.get("who"), scn.member(x["iso3"]).name),
                    "face": VI.likeness(x["iso3"]), "step": x.get("step", 1), "feeling": None if x.get("who") else VI.feeling(g, x["iso3"]),
                    "room": [{"iso3": i, "name": scn.member(i).name, "feeling": VI.feeling(g, i), "face": VI.likeness(i)} for i in x.get("members", [])]}
                   for x in g.get("visits", [])] if chapters else [],
        "reputation": VI.reputation(g),
        "sheet": {**g.get("sheet", {}), "final": g["whip"]}, "powers": _powers(scn, g),
        "in_draft": sorted({t for c in g["draft"] for t in c["tags"]}), "args": T.ARGS, "unlock": {k: T.locked(g, k) for k in T.UNLOCK},
        "tug": _tug(scn, g),
        "event": g.get("event"), "question": {"ask": q["ask"], "options": q["options"]} if q else None,
        "draft": draft, "cards": [c for c in scn.cards if c["id"] in g["cards"]],
        "endorse": {REGIONS.get(r, r): _name(scn, g, a) for r, a in g["endorse"].items()},
        "tokens": tokens, "log": g["log"][-14:], "skills": g["skills"], "objectives": g["objectives"],
        "sponsors": len(g["sponsors"]), "signatories": len(g["signatories"]), "signers_needed": E._signers_needed(scn),
        "summit": _summit_view(scn, g), "result": g.get("result"), "tags": tags,
        "debrief": E.debrief(scn, g) if g["phase"] == "done" else None,
        "veto": sorted(scn.rule.veto), "rule": scn.rule.name,
        "regions": regions, "skill_list": skills, "skill_cost": K.SKILL_COST, "blocs": blocs, "last_chapter": last,
        "costs": {"propose": 0 if g["respect"] >= 8 else E.R["propose_cost"], "amend": 0 if "friendly" in g["skills"] else E.R["amend_cost"],
                  "strike": E.R["strike_cost"], "side_event": E.R["side_event_cost"], "abstain": E.R["abstain_cost"],
                  "draft_max": E.R["draft_max"], "sponsors": E.R["sponsors"], "favour_trust": E.R["favour_trust"],
                  "hire": E.R["hire_cost"], "staff_max": E.R["staff_max"], "secure": E.R["secure_cost"], "secure_max": E.R["secure_max"],
                  "reply_respect": E.R["reply_respect"], "deal_ap": E.R["deal_ap"], "deal_funding": E.R["deal_funding"],
                  "candidacy_max": E.R["candidacy_max"]},
        "draft_ok": {"clauses": len(g["draft"]), "mine": sum(1 for c in g["draft"] if c["author"] == "you")},
    }


def _stage(scn: Scenario, g: dict) -> dict | None:
    if g["phase"] != "chapter":
        return None
    st = E.stage_names(g)[g["chapter"]]
    made = str(g["chapter"]) in g.get("breakthroughs", {})
    left = max(0, E.turns_now(g) - g["turn"])
    return {**st, "n": g["chapter"], "of": E.LENGTHS[g["length"]]["chapters"], "checklist": E.checklist(scn, g), "made": made,
            "stayed": bool(g.get("stayed", {}).get(str(g["chapter"]))), "turns_left": left, "deadline": E.turns_now(g),
            "momentum": {"respect": E.R["momentum_respect"], "influence": E.R["momentum_influence"] * left}}


def _rooms(scn: Scenario, g: dict) -> list[dict]:
    """Each regional group's meeting room: its members and where they lean, its coordinator, what an endorsement needs."""
    out = []
    for code, name in REGIONS.items():
        members = [i for i in scn.isos if scn.member(i).region == code]
        voters = [i for i in members if i not in E._others(g)]
        if not voters:
            continue
        rows = []
        for iso in members:
            if iso == g["iso3"]:
                rows.append({"iso3": iso, "name": scn.member(iso).name, "side": "self"})
                continue
            if any(r["iso3"] == iso for r in g["rivals"]):
                rows.append({"iso3": iso, "name": scn.member(iso).name, "side": "rival-self"})
                continue
            mine = E.lean(scn, g, "you", iso)
            best = max(g["rivals"], key=lambda r: E.lean(scn, g, r["iso3"], iso), default=None)
            theirs = E.lean(scn, g, best["iso3"], iso) if best else -9
            side = "you" if mine > E.R["lean_min"] and mine >= theirs else "rival" if theirs > E.R["lean_min"] else "undecided"
            rows.append({"iso3": iso, "name": scn.member(iso).name, "side": side, "rival": scn.member(best["iso3"]).name if side == "rival" else None})
        big = max(members, key=lambda i: ((X.data()["countries"].get(i, {}).get("gdp") or [0])[0], i))
        courting = sorted({scn.member(r["iso3"]).name for r in g["rivals"] if g["region_last"].get(code) == r["iso3"]
                           or sum(g["sway"][r["iso3"]].get(i, 0.0) for i in voters) > 0.3})
        out.append({"code": code, "name": name, "members": rows, "coordinator": scn.member(big).name,
                    "needed": len(voters) // 2 + 1, "yours": sum(1 for r in rows if r["side"] == "you"),
                    "owner": _name(scn, g, g["endorse"][code]) if g["endorse"].get(code) else None,
                    "owner_you": g["endorse"].get(code) == "you", "meeting": g.get("meeting") == code, "courting": courting})
    return out


def _race(scn: Scenario, g: dict) -> list[dict]:
    """The clerk's sign-up sheets: yours beside each rival's, filling with flags."""
    rows = [{"who": "You", "you": True, "sponsors": g["sponsors"], "signatories": g["signatories"]}]
    rows += [{"who": scn.member(r["iso3"]).name, "you": False, "sponsors": r["sponsors"], "signatories": r["signatories"]} for r in g["rivals"]]
    for r in rows:
        r["sponsor_names"] = [scn.member(i).name for i in r["sponsors"]]
        r["signatory_names"] = [scn.member(i).name for i in r["signatories"]]
        r["tabled"] = len(r["sponsors"]) >= E.R["sponsors"] and len(r["sponsors"]) + len(r["signatories"]) >= E._signers_needed(scn)
    return [{**r, "need_sponsors": E.R["sponsors"], "need_total": E._signers_needed(scn)} for r in rows]


def _powers(scn: Scenario, g: dict) -> list[dict]:
    """Who is strong: you and each rival, by Influence, endorsements, sponsors, how much of the draft is theirs, and how
    busy they were last turn."""
    out = []
    n = max(1, len(g["draft"]))
    for who in ["you", *[r["iso3"] for r in g["rivals"]]]:
        rv = None if who == "you" else next(r for r in g["rivals"] if r["iso3"] == who)
        own = sum(1.0 if c["author"] == who else 0.5 if who in c.get("amended_by", []) else 0.0 for c in g["draft"])
        out.append({"who": who, "name": "You" if who == "you" else scn.member(who).name,
                    "style": None if who == "you" else K.RIVAL_STYLES[rv.get("style", "hawk")]["name"],
                    "influence": g["influence"] if who == "you" else rv["influence"],
                    "endorsements": sum(1 for v in g["endorse"].values() if v == who),
                    "sponsors": len(g["sponsors"]) if who == "you" else len(rv["sponsors"]),
                    "share": round(own / n, 2), "moves": len(g.get("moved", {}).get(who, [])) if who != "you" else None,
                    "truce": bool(rv and rv.get("truce"))})
    return out


def resolution_docx(scn: Scenario, g: dict) -> bytes:
    """The adopted resolution as a document: heading, committee, sponsors, the preamble, and each adopted operative
    clause numbered, with a semicolon between clauses and a full stop at the end."""
    from app.exports import resolution_docx as build
    s = g.get("summit") or {}
    passed = {r["clause"] for r in s.get("results", []) if r["passed"]}
    clauses = [c for c in g["draft"] if c["id"] in passed]
    ops = []
    for i, c in enumerate(clauses):
        text = c["text"].strip().rstrip(";.,")
        if c.get("text_stale"):
            labels = [E._lc(scn.tags[t]).rstrip(".") for t in c["tags"]]
            text = labels[0][:1].upper() + labels[0][1:] + ("" if len(labels) == 1 else ", and " + "; and ".join(labels[1:]))
        ops.append({"position": i + 1, "text": text + ("." if i == len(clauses) - 1 else ";")})
    pre = [{"text": p} for p in getattr(scn, "preamble", [])]
    sponsors = [scn.member(g["iso3"]).name] + [scn.member(i).name for i in g["sponsors"] if scn.member(i)]
    return build({"title": scn.title}, {"name": scn.rule.name}, pre, ops, sponsors)


def _tug(scn: Scenario, g: dict) -> dict:
    """The tug-of-war bar: the vote on the whole draft as it stands, without the hidden moods."""
    if g["phase"] == "done":
        f = (g.get("summit") or {}).get("final") or {}
        return {"yes": f.get("yes", 0), "no": f.get("no", 0), "abstain": f.get("abstain", 0), "passed": bool(f.get("passed")),
                "summary": f.get("summary", ""), "of": len(scn.members), "final": True}
    p = E.projection(scn, g)
    tags = set(E.final_clause(g)["tags"])
    m = g["mandate"]
    aims = (m["must"] in tags) + (m.get("also") in tags) + (m["red"] not in tags)
    return {"yes": p["yes"], "no": p["no"], "abstain": p["abstain"], "passed": p["passed"], "summary": p["summary"],
            "of": len(scn.members), "final": False, "aims": aims}


def _sphere(scn: Scenario, g: dict, iso: str) -> str | None:
    """Whose sphere of influence a delegation is in: yours, a rival's, or nobody's yet."""
    mine = E.lean(scn, g, "you", iso)
    theirs = max((E.lean(scn, g, r["iso3"], iso) for r in g["rivals"]), default=-9)
    if mine > E.R["lean_min"] and mine >= theirs:
        return "you"
    if theirs > E.R["lean_min"]:
        return "rival"
    return None


def _summit_view(scn: Scenario, g: dict) -> dict | None:
    """The summit as the page shows it: the clause before the committee, any floor amendment, what you can do about
    it, the votes so far, and the final vote and statement."""
    s = g.get("summit")
    if not s:
        return None
    clauses = {c["id"]: c for c in g["draft"]}
    cur = None
    if s["step"] == "clause" and s["i"] < len(s["queue"]):
        c = clauses[s["queue"][s["i"]]]
        cur = {"id": c["id"], "text": c["text"], "tags": [scn.tags[t] for t in c["tags"]], "n": s["i"] + 1, "of": len(s["queue"]),
               "chance": E.chance(scn, g, c), "stance": E.stance(scn, g, "you", c), "mine": c["author"] == "you",
               "expected": _expected(scn, g, c),
               "author": _name(scn, g, c["author"]),
               "promised_to": [scn.member(pr["iso3"]).name for pr in g["promises"] if pr["clause"] == c["id"] and pr["kept"] is None]}
    atk = s.get("attack")
    if atk:
        atk = {**atk, "by_name": scn.member(atk["by"]).name}
    pend = s.get("pending")
    if pend:
        pend = {**pend, "by_name": scn.member(pend["by"]).name,
                "change": ("drop " + scn.tags[pend["remove"]].lower()) if pend.get("remove") else ("add " + scn.tags[pend["add"]].lower())}
    results = []
    for r in s["results"]:
        c = clauses.get(r["clause"], {})
        results.append({**r, "text": c.get("text", ""), "labels": [scn.tags[t] for t in r["tags"]]})
    final = s.get("final")
    kept_tags = list(dict.fromkeys(t for r in s["results"] if r["passed"] for t in r["tags"]))
    golden = None
    if s["step"] == "final":
        kept = {t for r in s["results"] if r["passed"] for t in r["tags"]}
        m = g["mandate"]
        if m["must"] in kept and m["red"] not in kept:
            golden = "aims_in"
        elif m["red"] in kept:
            golden = "red_in"
    return {"step": s["step"], "current": cur, "pending": pend, "results": results, "final": final, "attack": atk, "golden": golden,
            "can_reply": g["respect"] >= E.R["reply_respect"],
            "kept": [scn.tags[t] for t in kept_tags],
            "statement_options": [{"code": t, "label": scn.tags[t]} for t in s.get("statement_options", [])],
            "statement": s.get("statement"), "speech": s.get("speech"),
            "favours": [scn.member(i).name for i in g["favours"]], "po": "point_of_order" in g["skills"] and not s["po_used"],
            "offer_cost": E.R["offer_cost"], "influence": g["influence"],
            "names": {m.iso3: m.name for m in scn.members}}


def _expected(scn: Scenario, g: dict, c: dict) -> dict:
    """At the summit, every decision card shows the vote count you can expect (without the moods on the day)."""
    st = {a: E.stance(scn, g, a, c) for a in ["you", *[r["iso3"] for r in g["rivals"]]]}
    word = {1: "yes", -1: "no", 0: "abstain"}
    votes = [word[st[m.iso3 if m.iso3 != g["iso3"] else "you"]] if (m.iso3 in st or m.iso3 == g["iso3"])
             else E.vote_of(scn, E.latent(scn, g, m.iso3, c, st, mood=False)) for m in scn.members]
    return {k: votes.count(k) for k in ("yes", "no", "abstain")}


def results_for_staff(conn, class_ids) -> list[dict]:
    """Finished sessions of the students a teacher can see (None: everyone): the scenario, the path, the grades. The
    students' own words (reworded clauses) stay in the saved game and are never shown here."""
    from app.modules.mun.packfile import available
    from app.util import display_name
    titles = {p["code"]: p["title"] for p in available()}
    out = []
    for r in rows(conn, "SELECT cs.id, cs.pack, cs.iso3, cs.length, cs.difficulty, cs.path, cs.grade, cs.updated_at, cs.state_json, "
                        "st.first_name, st.last_initial, st.class_id, c.name AS country FROM campaign_save cs "
                        "JOIN student st ON st.id = cs.student_id JOIN country c ON c.iso3 = cs.iso3 "
                        "WHERE cs.phase = 'done' AND cs.deleted_at IS NULL AND st.deleted_at IS NULL ORDER BY cs.updated_at DESC LIMIT 300"):
        if class_ids is not None and r["class_id"] not in class_ids:
            continue
        res = (json.loads(r["state_json"]).get("result") or {})
        out.append({"student": display_name(r["first_name"], r["last_initial"]), "scenario": titles.get(r["pack"], r["pack"]),
                    "country": r["country"], "length": r["length"], "difficulty": r["difficulty"], "path": r["path"],
                    "grade": r["grade"], "paths": res.get("paths", {}), "passed": res.get("passed"),
                    "whip": f"{res.get('whip_right', 0)} of {res.get('whip_judged', 0)}", "when": r["updated_at"]})
    return out
