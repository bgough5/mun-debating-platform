"""Guided simulation (D-060), whip-count exercise (D-061) and practice v3: chair, student and practice pages."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request

from app.db import one, rows, scalar
from app.errors import UserError
from app.modules.chair import service as C
from app.modules.chair.routes import _manage, _student_session, session_view
from app.modules.sim import service as SIM
from app.util import display_name
from app.web.auth import require_staff, require_student
from app.web.http import form_int, redirect, form_data
from app.web.templating import render

router = APIRouter()


def _act(request: Request, sid: int, fn, msg: str = "", back: str | None = None):
    with request.app.state.db.write(request.state.actor) as w:
        s = _manage(w.conn, request, sid)
        out = fn(w, s)
    return redirect(back or f"/chair/{sid}", out if isinstance(out, str) else msg)


@router.get("/chair/{sid}/guide")
def chair_guide(request: Request, sid: int, sess=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        _manage(conn, request, sid)
        ctx = session_view(conn, sid)
    return render(request, "sim/_chair_guide.html", ctx)


@router.get("/chair/{sid}/whip-map")
def chair_whip_map(request: Request, sid: int, sess=Depends(require_staff)):
    """The class's whip count on a world tile map (D-089), updating live."""
    with request.app.state.db.read() as conn:
        s = _manage(conn, request, sid)
        ctx = session_view(conn, sid)
    return render(request, "sim/whip_map.html", {"title": f"Whip map: {ctx['s']['committee']}", **ctx})


@router.get("/chair/{sid}/whip-map/f")
def chair_whip_map_fragment(request: Request, sid: int, sess=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        _manage(conn, request, sid)
        ctx = session_view(conn, sid)
    return render(request, "sim/_whip_map_region.html", ctx)


@router.post("/chair/{sid}/stage")
def chair_stage(request: Request, sid: int, sess=Depends(require_staff), form=Depends(form_data)):
    def act(w, s):
        SIM.set_stage(w, sid, form.get("stage") or "")
        name = next((x["name"] for x in SIM.stages(w.conn, s) if x["code"] == form.get("stage")), form.get("stage"))
        return f"Stage: {name}."
    return _act(request, sid, act)


@router.post("/chair/{sid}/agenda")
def chair_agenda(request: Request, sid: int, sess=Depends(require_staff), form=Depends(form_data)):
    return _act(request, sid, lambda w, s: SIM.set_agenda(w, sid, form.get("agenda") or "") or "Agenda set.")


@router.post("/chair/{sid}/roll")
def chair_roll(request: Request, sid: int, sess=Depends(require_staff), form=Depends(form_data)):
    def act(w, s):
        if form.get("action") == "computed":
            n = SIM.roll_computed(w, s)
            return f"{n} delegation(s) without a student answered present (computed)."
        SIM.answer_roll(w, s, form_int(form.get("delegation_id")), form.get("status") or "")
        return "Roll call updated."
    return _act(request, sid, act)


@router.post("/chair/{sid}/whip")
def chair_whip(request: Request, sid: int, sess=Depends(require_staff), form=Depends(form_data)):
    def act(w, s):
        kind, _, tid = (form.get("target") or "").partition(":")
        if not tid.isdigit():
            raise UserError("Choose what the whip count is for.")
        title = _title(w.conn, kind, int(tid))
        SIM.start_whip(w, s, kind, int(tid), title, form_int(form.get("per_student"), 5) or 5)
        return "Whip count started: students are predicting how their named delegations will vote."
    return _act(request, sid, act)


def _title(conn, kind: str, tid: int) -> str:
    if kind == "paragraph":
        p = one(conn, "SELECT position FROM paragraph WHERE id = ?", (tid,))
        return f"Operative paragraph {p['position']}" if p else "Paragraph"
    if kind == "amendment":
        a = one(conn, "SELECT a.id, p.position FROM amendment a JOIN paragraph p ON p.id = a.paragraph_id WHERE a.id = ?", (tid,))
        return f"Amendment {a['id']} to paragraph {a['position']}" if a else "Amendment"
    r = one(conn, "SELECT title FROM resolution WHERE id = ?", (tid,))
    return f"Resolution: {r['title']}" if r else "Resolution"


@router.post("/chair/{sid}/whip/{rid}")
def chair_whip_act(request: Request, sid: int, rid: int, sess=Depends(require_staff), form=Depends(form_data)):
    r0 = None
    pred = None
    if form.get("action") == "open":
        # The prediction for computed delegations is made before the write, as for any division (D-042).
        from app.modules.mun.predict import run_prediction
        with request.app.state.db.read() as conn:
            _manage(conn, request, sid)
            r0 = one(conn, "SELECT * FROM whip_round WHERE id = ? AND session_id = ?", (rid, sid))
            if r0:
                pred = run_prediction(conn, r0["target_kind"], r0["target_id"], with_swing=False)

    def act(w, s):
        r = one(w.conn, "SELECT * FROM whip_round WHERE id = ? AND session_id = ?", (rid, sid))
        if not r or r["status"] != "open":
            raise UserError("That whip count isn't running.", 409)
        if form.get("action") == "cancel":
            SIM.cancel_round(w, rid)
            return "Whip count cancelled."
        did = C.open_division(w, sid, r["title"], r["target_kind"], r["target_id"], pred=pred)
        SIM.lock_round(w, rid, did)
        if r["target_kind"] == "resolution":
            SIM.set_stage(w, sid, "voting_procedure")
        return "Predictions locked. Voting is open."
    return _act(request, sid, act)


@router.get("/chair/{sid}/debrief/{did}")
def chair_debrief(request: Request, sid: int, did: int, sess=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        s = _manage(conn, request, sid)
        d = SIM.debrief(conn, did)
        if d["division"]["session_id"] != sid:
            raise UserError("That vote isn't in this session.", 404)
    return render(request, "sim/debrief.html", {"title": f"Debrief: {d['division']['title']}", "s": s, "d": d, "staff": True})


@router.post("/chair/{sid}/debrief/{did}/fidelity")
def chair_fidelity(request: Request, sid: int, did: int, sess=Depends(require_staff), form=Depends(form_data)):
    def act(w, s):
        if scalar(w.conn, "SELECT session_id FROM division WHERE id = ?", (did,)) != sid:
            raise UserError("That vote isn't in this session.", 404)
        SIM.set_fidelity(w, did, form_int(form.get("delegation_id")), form.get("consistent") == "1", form.get("reason") or "")
        return "Judgement saved. The delegate profile uses it."
    return _act(request, sid, act, back=f"/chair/{sid}/debrief/{did}")


# ---------- students in a live session ----------

def _mine(conn, request, s):
    mine = one(conn, "SELECT d.* FROM delegation d JOIN delegation_member dm ON dm.delegation_id = d.id WHERE dm.student_id = ? "
                     "AND d.committee_id = ? AND dm.deleted_at IS NULL AND d.deleted_at IS NULL", (request.state.actor.id, s["committee_id"]))
    if not mine:
        raise UserError("You aren't in a delegation in this committee yet. Ask your teacher.", 403)
    return mine


@router.post("/live/{sid}/roll")
def live_roll(request: Request, sid: int, sess=Depends(require_student), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        s = _student_session(w.conn, request, sid)
        mine = _mine(w.conn, request, s)
        if form.get("status") not in ("present", "present_and_voting"):
            raise UserError("Answer Present or Present and voting.")
        SIM.answer_roll(w, s, mine["id"], form.get("status"))
    return redirect(f"/live/{sid}", "You've answered the roll.")


@router.post("/live/{sid}/whip/{rid}")
def live_whip(request: Request, sid: int, rid: int, sess=Depends(require_student), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        _student_session(w.conn, request, sid)
        if scalar(w.conn, "SELECT session_id FROM whip_round WHERE id = ?", (rid,)) != sid:
            raise UserError("That whip count isn't in this session.", 404)
        SIM.predict(w, rid, request.state.actor.id, form_int(form.get("delegation_id")), form.get("vote") or "")
    return redirect(f"/live/{sid}", "Prediction saved. You can change it until voting opens.")


@router.get("/live/{sid}/debrief/{did}")
def live_debrief(request: Request, sid: int, did: int, sess=Depends(require_student)):
    with request.app.state.db.read() as conn:
        s = _student_session(conn, request, sid)
        d = SIM.debrief(conn, did)
        if d["division"]["session_id"] != sid:
            raise UserError("That vote isn't in this session.", 404)
        mine = _mine(conn, request, s)
    me = request.state.actor.id
    # Students see the class result and their own whip score and profile, never other students' scores.
    if d["whip"]:
        d["whip"] = {**d["whip"], "students": [x for x in d["whip"]["students"] if x["student_id"] == me]}
    d["profiles"] = [p for p in d["profiles"] if p["delegation_id"] == mine["id"]]
    return render(request, "sim/debrief.html", {"title": f"Debrief: {d['division']['title']}", "s": s, "d": d, "staff": False})


# ---------- practice v3 ----------

def _my_committees(conn, student_id: int) -> list[dict]:
    """The class's committees, and the ones this student made from a pack to play alone (D-097)."""
    return rows(conn, "SELECT DISTINCT cm.id, cm.name, cm.topic_id FROM committee cm LEFT JOIN class c ON c.id = cm.class_id "
                      "LEFT JOIN student st ON st.class_id = c.id AND st.id = ? WHERE cm.deleted_at IS NULL "
                      "AND (st.id IS NOT NULL OR cm.solo_student_id = ?) ORDER BY cm.solo_student_id IS NULL, cm.name",
                (student_id, student_id))


@router.get("/me/sim")
def practice_home(request: Request, sess=Depends(require_student)):
    me = request.state.actor.id
    with request.app.state.db.read() as conn:
        mine = rows(conn, "SELECT sp.*, cm.name AS committee, m.iso3, p.position FROM sim_practice sp JOIN sim_practice_member m ON m.practice_id = sp.id "
                          "JOIN committee cm ON cm.id = sp.committee_id JOIN paragraph p ON p.id = sp.paragraph_id "
                          "WHERE m.student_id = ? AND sp.deleted_at IS NULL ORDER BY sp.id DESC", (me,))
        coms = _my_committees(conn, me)
        options = []
        for cm in coms:
            paras = rows(conn, "SELECT p.id, p.position, r.title FROM paragraph p JOIN resolution r ON r.id = p.resolution_id "
                               "WHERE r.committee_id = ? AND p.kind = 'operative' AND p.deleted_at IS NULL AND r.deleted_at IS NULL "
                               "ORDER BY r.id, p.position", (cm["id"],))
            countries = rows(conn, "SELECT d.iso3, c.name FROM delegation d JOIN country c ON c.iso3 = d.iso3 "
                                   "WHERE d.committee_id = ? AND d.deleted_at IS NULL ORDER BY c.name", (cm["id"],))
            if paras and countries:
                options.append({**cm, "paras": paras, "countries": countries})
    from app.modules.mun.packfile import available, un_members
    packs = [{**p, "options": sorted(((c, un_members().get(c, c)) for c in p["countries"]), key=lambda x: x[1])} for p in available()]
    return render(request, "sim/practice_home.html", {"title": "Practice committee", "mine": mine, "options": options, "packs": packs})


@router.post("/me/sim/scenario")
def practice_scenario(request: Request, sess=Depends(require_student), form=Depends(form_data)):
    """Play a scenario pack alone (D-097): the pack becomes this student's own committee, and a practice run starts on
    its first operative clause against the computed chamber."""
    from app.modules.mun import choice as CH
    from app.modules.mun.packfile import install, load, most_contested
    me = request.state.actor.id
    code = form.get("pack") or ""
    iso3 = (form.get(f"iso3_{code}") or form.get("iso3") or "").upper()
    with request.app.state.db.write(request.state.actor) as w:
        pack = load(code)
        if iso3 not in pack["countries"]:
            raise UserError("Choose a country that sits on this committee.")
        info = install(w, code, None, name_suffix=" · solo", solo_student_id=me)
        CH.set_roster(w, info["committee_id"], [me])
        ops = rows(w.conn, "SELECT p.id FROM paragraph p WHERE p.resolution_id = ? AND p.kind = 'operative' AND p.deleted_at IS NULL "
                           "ORDER BY p.position", (info["resolution_id"],))
        pid = SIM.create_practice(w, me, info["committee_id"], ops[most_contested(pack)]["id"], iso3)
        country = scalar(w.conn, "SELECT name FROM country WHERE iso3 = ?", (iso3,)) or iso3
    return redirect(f"/me/sim/{pid}", f"{pack['title']}: you are {country}. This is the clause the room agrees on least: lobby, "
                                      "amend if you need to, then call the vote. Try the other clauses from Practice committee.")


@router.post("/me/sim")
def practice_create(request: Request, sess=Depends(require_student), form=Depends(form_data)):
    me = request.state.actor.id
    with request.app.state.db.write(request.state.actor) as w:
        cid = form_int(form.get("committee_id"))
        if cid not in [c["id"] for c in _my_committees(w.conn, me)]:
            raise UserError("Choose one of your class's committees.", 403)
        pid = SIM.create_practice(w, me, cid, form_int(form.get(f"paragraph_id_{cid}") or form.get("paragraph_id")),
                                  (form.get(f"iso3_{cid}") or form.get("iso3") or "").upper())
    return redirect(f"/me/sim/{pid}", "Practice committee ready. Lobby the room, amend if you need to, then call the vote.")


def _practice_ctx(conn, p: dict, me: int) -> dict:
    members = rows(conn, "SELECT m.*, c.name AS country, st.first_name, st.last_initial FROM sim_practice_member m "
                         "JOIN country c ON c.iso3 = m.iso3 JOIN student st ON st.id = m.student_id WHERE m.practice_id = ? ORDER BY m.id", (p["id"],))
    me_m = next(m for m in members if m["student_id"] == me)
    lobbies = rows(conn, "SELECT l.*, c.name AS country FROM sim_practice_lobby l JOIN country c ON c.iso3 = l.iso3 "
                         "WHERE l.practice_id = ? AND l.student_id = ? ORDER BY l.id DESC", (p["id"], me))
    topic_id = scalar(conn, "SELECT topic_id FROM committee WHERE id = ?", (p["committee_id"],))
    tags = rows(conn, "SELECT code, label FROM tag WHERE topic_id IS ? AND deleted_at IS NULL ORDER BY code", (topic_id,))
    para = one(conn, "SELECT p.position, v.text, v.tags, r.title FROM paragraph p JOIN paragraph_version v ON v.id = p.current_version_id "
                     "JOIN resolution r ON r.id = p.resolution_id WHERE p.id = ?", (p["paragraph_id"],))
    countries = rows(conn, "SELECT d.iso3, c.name FROM delegation d JOIN country c ON c.iso3 = d.iso3 WHERE d.committee_id = ? "
                           "AND d.deleted_at IS NULL ORDER BY c.name", (p["committee_id"],))
    classmates = rows(conn, "SELECT st.id, st.first_name, st.last_initial FROM student st JOIN student me ON me.class_id = st.class_id "
                            "WHERE me.id = ? AND st.id != ? AND st.active = 1 AND st.deleted_at IS NULL ORDER BY st.first_name", (me, me))
    played = {m["iso3"] for m in members}
    pred = SIM.practice_prediction(conn, p) if p["stage"] == "lobbying" else None
    return {"p": p, "members": members, "me_m": me_m, "lobbies": lobbies, "tags": tags, "para": para,
            "current_tags": [t for t in (p["tags"] or "").split(",") if t], "countries": countries, "played": played,
            "classmates": classmates, "pred": pred, "used": len(lobbies), "limit": SIM.LOBBY_LIMIT,
            "result": json.loads(p["result_json"]) if p["result_json"] else None,
            "names": {m["student_id"]: display_name(m["first_name"], m["last_initial"]) for m in members}}


@router.get("/me/sim/{pid}")
def practice_page(request: Request, pid: int, sess=Depends(require_student)):
    me = request.state.actor.id
    with request.app.state.db.read() as conn:
        p = SIM.get_practice(conn, pid, me)
        ctx = _practice_ctx(conn, p, me)
    return render(request, "sim/practice.html", {"title": "Practice committee", **ctx})


@router.post("/me/sim/{pid}")
def practice_action(request: Request, pid: int, sess=Depends(require_student), form=Depends(form_data)):
    me = request.state.actor.id
    action = form.get("action")
    p_pass = None
    if action == "vote":
        with request.app.state.db.read() as conn:
            p0 = SIM.get_practice(conn, pid, me)
            p_pass = SIM.practice_prediction(conn, p0)["result"].p_pass if p0["stage"] == "lobbying" else None
    with request.app.state.db.write(request.state.actor) as w:
        p = SIM.get_practice(w.conn, pid, me)
        if action == "lobby":
            SIM.lobby(w, p, me, (form.get("iso3") or "").upper())
            msg = "They've answered. Read what they said, then record what you think they'll do."
        elif action == "read":
            SIM.record_reading(w, p, me, form_int(form.get("lobby_id")), form_int(form.get("position")), form.get("note") or "")
            msg = "Reading recorded. Your prediction now uses it."
        elif action == "amend":
            SIM.amend(w, p, form.getlist("tags"))
            msg = "Practice amendment applied. The chamber reacts to the new text."
        elif action == "my_vote":
            SIM.set_member_vote(w, p, me, form.get("vote") or "")
            msg = "Your vote is set."
        elif action == "add_member":
            sid = form_int(form.get("student_id"))
            if not one(w.conn, "SELECT 1 FROM student a JOIN student b ON a.class_id = b.class_id WHERE a.id = ? AND b.id = ?", (sid, me)):
                raise UserError("You can only add a classmate.", 403)
            SIM.add_member(w, p, sid, (form.get("iso3") or "").upper())
            msg = "Classmate added. They can open this practice from their page."
        elif action == "vote":
            SIM.call_vote(w, p, p_pass if p_pass is not None else 0.0)
            msg = "The chamber has voted. Here is your debrief."
        else:
            raise UserError("Unknown action.")
    return redirect(f"/me/sim/{pid}", msg)
