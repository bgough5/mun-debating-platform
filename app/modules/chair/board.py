"""The board (D-092): the projector view on the second screen, a war-room table that plays the committee.

The teacher runs the session from the chair console on their own screen; the board is a separate window on the
extended display, driven only by what happens in the session. It is its own page (chair/board.html, board.css,
board.js), not part of the app's layout. On every change in the session the board fetches `state()` as JSON and
animates the difference: countries light up at roll call, the camera glides to the speaker, votes sweep across the
map, the seal stamps the result. Everything it shows is already visible to the room on the old projector page; the
board only shows it better.
"""
from __future__ import annotations

import functools
import re

from app.db import one, rows
from app.modules.mun import worldmap as WMAP
from app.util import display_name, now

STAGE_SHORT = {"roll_call": "Roll call", "agenda": "Agenda", "opening_speeches": "Openings", "floor": "The floor",
               "voting_procedure": "Voting", "debrief": "Debrief"}
NUM = re.compile(r"-?\d+(?:\.\d+)?")


@functools.lru_cache(maxsize=1)
def boxes() -> dict:
    """Each drawn country's bounding box on the map, for the camera."""
    out = {}
    for iso3, c in WMAP.data()["countries"].items():
        v = [float(x) for x in NUM.findall(c["d"])]
        xs, ys = v[0::2], v[1::2]
        out[iso3] = (min(xs), min(ys), max(xs), max(ys))
    return out


def box(iso3: str) -> tuple:
    if iso3 in boxes():
        return boxes()[iso3]
    a = WMAP.anchor(iso3) or (500, 220)
    return (a[0] - 6, a[1] - 6, a[0] + 6, a[1] + 6)


def static_board(conn, committee_id: int) -> dict:
    """What doesn't change during a session: the world, and a token for each country in the room."""
    dels = rows(conn, "SELECT d.iso3, c.name, c.p5, c.region FROM delegation d JOIN country c ON c.iso3 = d.iso3 "
                      "WHERE d.committee_id = ? AND d.deleted_at IS NULL ORDER BY c.name", (committee_id,))
    wmap = WMAP.board(conn, [d["iso3"] for d in dels], mode="plain")
    for t in wmap["tokens"]:
        t["box"] = " ".join(f"{v:.1f}" for v in box(t["iso3"]))
    return wmap


def _votes(conn, division_id: int) -> dict:
    return {v["iso3"]: {"vote": v["vote"] if v["vote"] in ("yes", "no", "abstain") else "absent", "computed": bool(v["computed"])}
            for v in rows(conn, "SELECT iso3, vote, computed FROM division_vote WHERE division_id = ?", (division_id,))}


def state(conn, sid: int) -> dict:
    """The session as the board sees it. Names are first names and initials, as on every projector page."""
    from app.modules.chair.routes import session_view
    from app.modules.sim import service as SIM
    v = session_view(conn, sid)
    s, sim = v["s"], v["sim"]
    members: dict = {}
    for m in rows(conn, "SELECT d.iso3, dm.role, st.first_name, st.last_initial FROM delegation_member dm JOIN delegation d "
                        "ON d.id = dm.delegation_id JOIN student st ON st.id = dm.student_id WHERE d.committee_id = ? "
                        "AND dm.deleted_at IS NULL AND d.deleted_at IS NULL ORDER BY dm.role = 'head' DESC, st.first_name",
                  (s["committee_id"],)):
        members.setdefault(m["iso3"], []).append(display_name(m["first_name"], m["last_initial"]))
    roll = {r["iso3"]: r["status"] for r in v["roll"]}
    countries = [{"iso3": d["iso3"], "name": d["name"], "students": members.get(d["iso3"], []), "roll": roll.get(d["iso3"])}
                 for d in v["dels"]]
    t0 = now()
    timers = [{"id": t["id"], "kind": t["kind"], "label": t["label"], "state": t["state"], "total": t["duration_s"] + t["extended_s"],
               "remaining": round(t["remaining"], 2)} for t in v["timers"]]
    cur = v["current"]
    div = v["division"]
    last = (v["recent"] or [None])[0]
    wm = SIM.whip_map(conn, sid)
    whip = None
    if wm:
        whip = {"id": wm["round"]["id"], "title": wm["round"]["title"], "phase": wm["phase"], "right": wm["right"], "judged": wm["judged"],
                "calls": {t["iso3"]: t["n"] for t in wm["tiles"]},
                "predicted": {t["iso3"]: t["predicted"] for t in wm["tiles"] if t["predicted"] and wm["phase"] != "open"},
                "correct": {t["iso3"]: t["correct"] for t in wm["tiles"] if t["correct"] is not None}}
    debrief = None
    if v["last_vote"]:
        lv = v["last_vote"]
        debrief = {"id": lv["id"], "title": lv["title"], "passed": bool(lv["passed"]), "summary": lv["summary"],
                   "votes": _votes(conn, lv["id"])}
    fa = v["floor_amendment"]
    fx = v["fx"]
    return {
        "seq": v["view_seq"], "server_now": t0,
        "session": {"id": s["id"], "committee": s["committee"], "state": s["state"], "mode": s["mode"], "mode_topic": s["mode_topic"] or "",
                    "agenda": s["agenda"] or "", "draft": (v["draft"] or {}).get("title", "")},
        "stage": {"code": sim["stage"]["code"], "name": sim["stage"]["name"], "index": sim["stage_index"],
                  "prompt": sim.get("student_prompt") or "",
                  "all": [{"code": x["code"], "name": STAGE_SHORT.get(x["code"], x["name"])} for x in sim["stages"]]},
        "countries": countries,
        "roll": {"present": v["present"], "total": len(v["roll"])},
        "current": {"iso3": cur["iso3"], "by": cur["by"], "side": cur["side"] or "", "id": cur["id"]} if cur else None,
        "timers": timers,
        "queue": [{"iso3": e["iso3"], "by": e["by"], "side": e["side"] or ""} for e in v["queue"][:12]],
        "motions": [{"name": m["name"], "topic": m["topic"] or "", "by": m["proposer_by"] or "the Chair",
                     "seconded": m["seconder_by"] or "", "needs_second": bool(m["needs_second"]) and not m["seconder"],
                     "status": m["status"], "minutes": (m["duration_s"] or 0) // 60} for m in v["motions"]],
        "division": {"id": div["id"], "title": div["title"], "procedural": bool(div["procedural"]), "cast": div["cast"],
                     "total": len(div["voters"]), "counts": div["counts"], "veto_by": div["veto_by"],
                     "votes": {x["iso3"]: x["vote"] for x in div["voters"] if x["vote"]}} if div else None,
        "result": {"id": last["id"], "title": last["title"], "passed": bool(last["passed"]), "summary": last["summary"],
                   "yes": last["yes"], "no": last["no"], "abstain": last["abstain"], "votes": _votes(conn, last["id"])} if last else None,
        "whip": whip,
        "debrief": debrief,
        "placards": [{"iso3": p["iso3"], "by": p["by"]} for p in v["placards"]],
        "news": {"id": fx["news"]["id"], "headline": fx["news"]["headline"], "body": fx["news"]["body"], "label": fx["news"]["label"]}
        if fx["news"] else None,
        "adopted": {k: fx["adopted"][k] for k in ("seq", "label", "before", "after", "friendly")} if fx["adopted"] else None,
        "gavel": {"seq": fx["gavel"], "knocks": fx["gavel_n"]},
        "amendment": {"id": fa["id"], "label": fa["kind_label"], "by": fa.get("sponsor_by") or fa.get("sponsor_name") or "",
                      "before": fa["current_text"] if fa["kind"] != "add" else "", "after": fa["proposed_text"] if fa["kind"] != "delete" else ""}
        if fa else None,
    }
