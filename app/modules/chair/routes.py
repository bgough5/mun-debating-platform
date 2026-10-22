"""Chair console, student live view and projector view for a live MUN session."""
from __future__ import annotations

import threading

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from app.db import one, rows, scalar
from app.errors import UserError
from app.exports import text_docx
from app.modules.chair import service as C
from app.web.auth import committee_access, require_any, require_staff, require_student, staff_class_ids
from app.web.http import form_float, form_int, redirect, form_data
from app.util import now
from app.web.templating import render

router = APIRouter()


def _manage(conn, request, sid: int) -> dict:
    s = C.get_session(conn, sid)
    if committee_access(conn, request.state.actor, s["committee_id"]) != "manage":
        raise UserError("Only staff running this class can chair its session.", 403)
    return s


_VIEW_CACHE: dict = {}
_VIEW_LOCK = threading.Lock()


def _shared_view(conn, sid: int) -> dict:
    """Everything about a session that is the same for every viewer.

    Computed once per change and shared by all 30 clients that re-fetch after it
    (keyed by the newest event-log sequence number, so it is never stale)."""
    seq = scalar(conn, "SELECT COALESCE(MAX(seq), 0) FROM event_log")
    path = conn.execute("PRAGMA database_list").fetchone()[2]
    key = (path, sid)
    with _VIEW_LOCK:
        hit = _VIEW_CACHE.get(key)
    if hit and hit[0] == seq:
        return hit[1]
    s = C.get_session(conn, sid)
    current = None
    if s["current_entry_id"]:
        current = one(conn, "SELECT e.*, d.iso3, c.name AS country, c.flag_svg, st.first_name, st.last_initial FROM speakers_list_entry e "
                            "JOIN delegation d ON d.id = e.delegation_id JOIN country c ON c.iso3 = d.iso3 "
                            "LEFT JOIN student st ON st.id = e.student_id WHERE e.id = ?", (s["current_entry_id"],))
    data = {
        "s": s, "current": current, "queue": C.waiting(conn, sid),
        "timer_rows": rows(conn, "SELECT * FROM timer WHERE session_id = ? AND state != 'done' ORDER BY kind = 'speaker' DESC, id DESC", (sid,)),
        "motions": C.motions(conn, sid),
        "division": C.division_state(conn, s["current_division_id"]) if s["current_division_id"] else None,
        "recent": rows(conn, "SELECT * FROM division WHERE session_id = ? AND status = 'closed' ORDER BY id DESC LIMIT 5", (sid,)),
        "dels": rows(conn, "SELECT d.id, d.iso3, c.name, (SELECT COUNT(*) FROM delegation_member dm WHERE dm.delegation_id = d.id "
                           "AND dm.deleted_at IS NULL) AS students FROM delegation d JOIN country c ON c.iso3 = d.iso3 "
                           "WHERE d.committee_id = ? AND d.deleted_at IS NULL ORDER BY c.name", (s["committee_id"],)),
        "proc_motions": rows(conn, "SELECT * FROM procedure_motion WHERE rule_set_id IS ? AND deleted_at IS NULL ORDER BY precedence DESC",
                             (s["procedure_rule_set_id"],)),
        "participants": C.active_participants(conn, sid),
        "resolutions": rows(conn, "SELECT id, title FROM resolution WHERE committee_id = ? AND deleted_at IS NULL", (s["committee_id"],)),
        "paragraphs": rows(conn, "SELECT p.id, p.position, r.title FROM paragraph p JOIN resolution r ON r.id = p.resolution_id "
                                 "WHERE r.committee_id = ? AND p.kind = 'operative' AND p.deleted_at IS NULL ORDER BY r.id, p.position",
                           (s["committee_id"],)),
        "amendments": rows(conn, "SELECT a.id, a.kind, p.position, c.name AS sponsor FROM amendment a JOIN paragraph p ON p.id = a.paragraph_id "
                                 "JOIN resolution r ON r.id = p.resolution_id LEFT JOIN delegation d ON d.id = a.sponsor_delegation_id "
                                 "LEFT JOIN country c ON c.iso3 = d.iso3 WHERE r.committee_id = ? AND a.status = 'tabled' "
                                 "AND a.deleted_at IS NULL ORDER BY a.id", (s["committee_id"],)),
        "cap": 25,
    }
    with _VIEW_LOCK:
        if len(_VIEW_CACHE) > 64:
            _VIEW_CACHE.clear()
        _VIEW_CACHE[key] = (seq, data)
    return data


def session_view(conn, sid: int, actor=None) -> dict:
    view = dict(_shared_view(conn, sid))
    t0 = now()
    view["timers"] = [{**t, "remaining": C.remaining(t, t0), "server_now": t0} for t in view["timer_rows"]]
    mine = None
    if actor is not None and actor.kind == "student":
        mine = one(conn, "SELECT d.*, dm.role FROM delegation d JOIN delegation_member dm ON dm.delegation_id = d.id "
                         "WHERE dm.student_id = ? AND d.committee_id = ? AND dm.deleted_at IS NULL AND d.deleted_at IS NULL",
                   (actor.id, view["s"]["committee_id"]))
    my_place = next((i for i, q in enumerate(view["queue"], 1) if mine and q["delegation_id"] == mine["id"]), None)
    my_vote = None
    if view["division"] and mine:
        my_vote = next((v for v in view["division"]["voters"] if v["id"] == mine["id"]), None)
    view.update(mine=mine, my_place=my_place, my_vote=my_vote)
    return view


# ---------- chair ----------

@router.get("/chair")
def chair_home(request: Request, sess=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        ids = staff_class_ids(conn, sess.actor)
        coms = rows(conn, "SELECT cm.*, cf.name AS conference, (SELECT id FROM live_session ls WHERE ls.committee_id = cm.id "
                          "AND ls.state != 'closed' ORDER BY id DESC LIMIT 1) AS open_session FROM committee cm "
                          "JOIN conference cf ON cf.id = cm.conference_id WHERE cm.deleted_at IS NULL ORDER BY cf.id DESC, cm.id")
        past = rows(conn, "SELECT ls.*, cm.name AS committee, cm.class_id FROM live_session ls JOIN committee cm ON cm.id = ls.committee_id "
                          "WHERE ls.state = 'closed' ORDER BY ls.id DESC LIMIT 20")
    if ids is not None:
        coms = [c for c in coms if c["class_id"] in ids]
        past = [p for p in past if p["class_id"] in ids]
    return render(request, "chair/home.html", {"title": "Chair", "coms": coms, "past": past})


@router.get("/chair/committee/{committee_id}")
def chair_committee(request: Request, committee_id: int, sess=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        if committee_access(conn, request.state.actor, committee_id) != "manage":
            raise UserError("Only staff running this class can chair its session.", 403)
        open_s = scalar(conn, "SELECT id FROM live_session WHERE committee_id = ? AND state != 'closed' ORDER BY id DESC LIMIT 1", (committee_id,))
    if open_s:
        return redirect(f"/chair/{open_s}")
    return redirect(f"/chair?start={committee_id}")


@router.post("/chair/committee/{committee_id}/open")
def chair_open(request: Request, committee_id: int, sess=Depends(require_staff)):
    with request.app.state.db.write(request.state.actor) as w:
        if committee_access(w.conn, request.state.actor, committee_id) != "manage":
            raise UserError("Only staff running this class can chair its session.", 403)
        sid = C.open_session(w, committee_id)
    return redirect(f"/chair/{sid}", "Session open. Students in the class can join it from their page.")


@router.get("/chair/{sid}")
def chair_console(request: Request, sid: int, sess=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        _manage(conn, request, sid)
        ctx = session_view(conn, sid)
        students = rows(conn, "SELECT st.id, st.first_name, st.last_initial, ta.extra_percent FROM student st "
                              "LEFT JOIN timing_adjustment ta ON ta.student_id = st.id WHERE st.class_id = ? AND st.active = 1 "
                              "AND st.deleted_at IS NULL ORDER BY st.first_name", (ctx["s"]["class_id"],)) if ctx["s"]["class_id"] else []
    return render(request, "chair/console.html", {"title": f"Chair: {ctx['s']['committee']}", "students": students, **ctx})


@router.get("/chair/{sid}/f/{part}")
def chair_fragment(request: Request, sid: int, part: str, sess=Depends(require_staff)):
    if part not in ("floor", "motions", "division", "status"):
        raise UserError("Not found.", 404)
    with request.app.state.db.read() as conn:
        _manage(conn, request, sid)
        ctx = session_view(conn, sid)
    return render(request, f"chair/_chair_{part}.html", ctx)


def _chair_action(request: Request, sid: int, form, fn, msg: str = ""):
    with request.app.state.db.write(request.state.actor) as w:
        _manage(w.conn, request, sid)
        out = fn(w, form)
    return redirect(f"/chair/{sid}", out if isinstance(out, str) else msg)


@router.post("/chair/{sid}/speakers")
def chair_add_speaker(request: Request, sid: int, sess=Depends(require_staff), form=Depends(form_data)):
    return _chair_action(request, sid, form, lambda w, f: C.add_speaker(
        w, sid, form_int(f.get("delegation_id")), form_int(f.get("student_id")), f.get("list_kind") or "general") and None,
        "Added to the speakers list.")


@router.post("/chair/{sid}/entries/{eid}")
def chair_entry(request: Request, sid: int, eid: int, sess=Depends(require_staff), form=Depends(form_data)):
    def act(w, f):
        e = one(w.conn, "SELECT session_id FROM speakers_list_entry WHERE id = ?", (eid,))
        if not e or e["session_id"] != sid:
            raise UserError("That speaker isn't in this session.", 404)
        if f.get("action") in ("up", "down"):
            C.move_speaker(w, eid, f.get("action"))
            return "Speakers list reordered."
        C.withdraw_speaker(w, eid)
        return "Removed from the speakers list."
    return _chair_action(request, sid, form, act)


@router.post("/chair/{sid}/next")
def chair_next(request: Request, sid: int, sess=Depends(require_staff), form=Depends(form_data)):
    return _chair_action(request, sid, form, lambda w, f: "Next speaker called." if C.next_speaker(w, sid) else
                               "The speakers list is empty.")


@router.post("/chair/{sid}/yield")
def chair_yield(request: Request, sid: int, sess=Depends(require_staff), form=Depends(form_data)):
    return _chair_action(request, sid, form, lambda w, f: C.yield_floor(w, sid, f.get("to") or "chair") or
                               f"Floor yielded to {f.get('to') or 'the chair'}.")


@router.post("/chair/{sid}/timers/{tid}")
def chair_timer(request: Request, sid: int, tid: int, sess=Depends(require_staff), form=Depends(form_data)):
    def act(w, f):
        t = one(w.conn, "SELECT session_id FROM timer WHERE id = ?", (tid,))
        if not t or t["session_id"] != sid:
            raise UserError("That timer isn't in this session.", 404)
        C.timer_action(w, tid, f.get("action"), form_float(f.get("seconds"), 0))
        return {"start": "Timer started.", "pause": "Timer paused.", "reset": "Timer reset.", "stop": "Timer stopped."}.get(
            f.get("action"), "Timer extended.")
    return _chair_action(request, sid, form, act)


@router.post("/chair/{sid}/timer")
def chair_new_timer(request: Request, sid: int, sess=Depends(require_staff), form=Depends(form_data)):
    def act(w, f):
        secs = form_float(f.get("minutes"), 0) * 60 + form_float(f.get("seconds"), 0)
        if not 0 < secs <= 3 * 3600:
            raise UserError("Set a time between 1 second and 3 hours.")
        C.make_timer(w, sid, "general", (f.get("label") or "Timer")[:60], secs)
        return "Timer ready. Press Start."
    return _chair_action(request, sid, form, act)


@router.post("/chair/{sid}/state")
def chair_state(request: Request, sid: int, sess=Depends(require_staff), form=Depends(form_data)):
    def act(w, f):
        st = f.get("state")
        if st == "closed" and f.get("confirm") != "yes":
            raise UserError("Tick the box to confirm closing the session.")
        C.set_state(w, sid, st)
        return {"open": "Session resumed.", "suspended": "Session suspended.", "closed": "Session closed. Minutes are ready to generate."}[st]
    return _chair_action(request, sid, form, act)


@router.post("/chair/{sid}/end-caucus")
def chair_end_caucus(request: Request, sid: int, sess=Depends(require_staff), form=Depends(form_data)):
    return _chair_action(request, sid, form, lambda w, f: C.end_caucus(w, sid) or "Back to formal debate.")


@router.post("/chair/{sid}/speaking-time")
def chair_speaking_time(request: Request, sid: int, sess=Depends(require_staff), form=Depends(form_data)):
    def act(w, f):
        secs = form_int(f.get("seconds"))
        if not secs or not 10 <= secs <= 900:
            raise UserError("Speaking time is between 10 and 900 seconds.")
        w.update("live_session", sid, {"speaking_time_s": secs}, C.ch(sid), action="speaking_time")
        return f"Speaking time set to {secs} seconds."
    return _chair_action(request, sid, form, act)


@router.post("/chair/{sid}/motions")
def chair_motion(request: Request, sid: int, sess=Depends(require_staff), form=Depends(form_data)):
    def act(w, f):
        secs = (form_int(f.get("duration_min"), 0) or 0) * 60 or None
        C.propose_motion(w, sid, form_int(f.get("procedure_motion_id")), form_int(f.get("proposer_delegation_id")), secs,
                         form_int(f.get("speaking_time_s")), f.get("topic") or "")
        return "Motion entertained."
    return _chair_action(request, sid, form, act)


@router.post("/chair/{sid}/motions/{mid}")
def chair_motion_decide(request: Request, sid: int, mid: int, sess=Depends(require_staff), form=Depends(form_data)):
    def act(w, f):
        m = one(w.conn, "SELECT session_id FROM motion WHERE id = ?", (mid,))
        if not m or m["session_id"] != sid:
            raise UserError("That motion isn't in this session.", 404)
        if f.get("action") == "second":
            C.second_motion(w, mid, form_int(f.get("delegation_id")))
            return "Seconded."
        C.decide_motion(w, mid, f.get("action"))
        return {"consent": "Motion passed with no objection.", "vote": "Voting on the motion is open.",
                "withdrawn": "Motion withdrawn.", "ruled_out": "Motion ruled out of order."}[f.get("action")]
    return _chair_action(request, sid, form, act)


@router.post("/chair/{sid}/divisions")
def chair_division(request: Request, sid: int, sess=Depends(require_staff), form=Depends(form_data)):
    # The prediction for computed delegations is worked out before the write starts,
    # so the database isn't locked while the simulation runs.
    kind0, _, tid0 = (form.get("target") or "").partition(":")
    pred = None
    if kind0 in ("paragraph", "amendment", "resolution") and tid0.isdigit():
        from app.modules.mun.predict import run_prediction
        with request.app.state.db.read() as conn:
            _manage(conn, request, sid)
            pred = run_prediction(conn, kind0, int(tid0), with_swing=False)

    def act(w, f):
        target = f.get("target") or ""
        kind, _, tid = target.partition(":")
        if kind not in ("paragraph", "amendment", "resolution", "custom"):
            raise UserError("Choose what the committee is voting on.")
        title = (f.get("title") or "").strip()
        if not title:
            title = {"paragraph": f"Operative paragraph (id {tid})", "amendment": f"Amendment {tid}",
                     "resolution": "Draft resolution as a whole", "custom": "Vote"}[kind]
            if kind == "resolution":
                r = one(w.conn, "SELECT title FROM resolution WHERE id = ?", (int(tid),))
                title = f"Resolution: {r['title']}" if r else title
            if kind == "paragraph":
                p = one(w.conn, "SELECT position FROM paragraph WHERE id = ?", (int(tid),))
                title = f"Operative paragraph {p['position']}" if p else title
        C.open_division(w, sid, title, kind, int(tid) if tid.isdigit() else None, pred=pred)
        return "Voting is open. Delegations without a student were voted by the engine (labelled computed)."
    return _chair_action(request, sid, form, act)


@router.post("/chair/{sid}/divisions/{did}")
def chair_division_act(request: Request, sid: int, did: int, sess=Depends(require_staff), form=Depends(form_data)):
    def act(w, f):
        d = one(w.conn, "SELECT session_id FROM division WHERE id = ?", (did,))
        if not d or d["session_id"] != sid:
            raise UserError("That division isn't in this session.", 404)
        a = f.get("action")
        if a == "vote":
            C.cast_vote(w, did, form_int(f.get("delegation_id")), f.get("vote"))
            return "Vote recorded."
        if a == "close":
            return "Result: " + C.close_division(w, did)["summary"]
        if a == "cancel":
            C.cancel_division(w, did)
            return "Division cancelled."
        raise UserError("Unknown action.")
    return _chair_action(request, sid, form, act)


@router.post("/chair/{sid}/adjust")
def chair_adjust(request: Request, sid: int, sess=Depends(require_staff), form=Depends(form_data)):
    def act(w, f):
        C.set_timing_adjustment(w, form_int(f.get("student_id")), form_int(f.get("extra_percent"), 0) or 0, f.get("note") or "")
        return "Extra speaking time saved. It applies automatically when that student speaks."
    return _chair_action(request, sid, form, act)


# ---------- minutes ----------

@router.get("/chair/{sid}/minutes")
def minutes_page(request: Request, sid: int, sess=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        s = _manage(conn, request, sid)
        versions = rows(conn, "SELECT * FROM minutes WHERE session_id = ? ORDER BY version DESC", (sid,))
        draft = versions[0]["body"] if versions else C.generate_minutes(conn, sid)
    return render(request, "chair/minutes.html", {"title": f"Minutes: {s['committee']}", "s": s, "versions": versions, "draft": draft})


@router.post("/chair/{sid}/minutes")
def minutes_save(request: Request, sid: int, sess=Depends(require_staff), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        _manage(w.conn, request, sid)
        if form.get("action") == "generate":
            C.save_minutes(w, sid, C.generate_minutes(w.conn, sid), True)
            msg = "Minutes regenerated from the session log as a new version."
        else:
            body = (form.get("body") or "").strip()
            if not body:
                raise UserError("The minutes are empty.")
            C.save_minutes(w, sid, body[:100_000], False)
            msg = "Edited minutes saved as a new version."
    return redirect(f"/chair/{sid}/minutes", msg)


@router.get("/chair/{sid}/minutes.docx")
def minutes_docx(request: Request, sid: int, sess=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        s = _manage(conn, request, sid)
        body = scalar(conn, "SELECT body FROM minutes WHERE session_id = ? ORDER BY version DESC LIMIT 1", (sid,)) or C.generate_minutes(conn, sid)
    return Response(text_docx(f"Minutes — {s['committee']}", body), headers={"Content-Disposition": f'attachment; filename="minutes-{sid}.docx"'},
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


@router.get("/chair/{sid}/minutes/print")
def minutes_print(request: Request, sid: int, sess=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        s = _manage(conn, request, sid)
        body = scalar(conn, "SELECT body FROM minutes WHERE session_id = ? ORDER BY version DESC LIMIT 1", (sid,)) or C.generate_minutes(conn, sid)
    return render(request, "chair/minutes_print.html", {"title": f"Minutes — {s['committee']}", "body": body, "s": s})


# ---------- students ----------

def _student_session(conn, request, sid: int) -> dict:
    s = C.get_session(conn, sid)
    if committee_access(conn, request.state.actor, s["committee_id"]) != "participate":
        raise UserError("That session isn't for your class.", 403)
    return s


@router.get("/live/{sid}")
def live_page(request: Request, sid: int, sess=Depends(require_student)):
    cap = int(request.app.state.settings.get("max_live_students", 25))
    with request.app.state.db.write(request.state.actor) as w:
        s = _student_session(w.conn, request, sid)
        if s["state"] == "closed":
            raise UserError("This session has finished.", 409)
        C.admit(w, sid, request.state.actor.id, cap)
    with request.app.state.db.read() as conn:
        ctx = session_view(conn, sid, request.state.actor)
    return render(request, "chair/live.html", {"title": f"Live: {ctx['s']['committee']}", **ctx})


@router.get("/live/{sid}/f")
def live_fragment(request: Request, sid: int, sess=Depends(require_student)):
    with request.app.state.db.read() as conn:
        _student_session(conn, request, sid)
        ctx = session_view(conn, sid, request.state.actor)
    return render(request, "chair/_live_main.html", ctx)


def _student_action(request: Request, sid: int, form, fn, msg: str):
    with request.app.state.db.write(request.state.actor) as w:
        s = _student_session(w.conn, request, sid)
        mine = one(w.conn, "SELECT d.*, dm.role FROM delegation d JOIN delegation_member dm ON dm.delegation_id = d.id "
                           "WHERE dm.student_id = ? AND d.committee_id = ? AND dm.deleted_at IS NULL AND d.deleted_at IS NULL",
                   (request.state.actor.id, s["committee_id"]))
        if not mine:
            raise UserError("You aren't in a delegation in this committee yet. Ask your teacher.", 403)
        fn(w, form, mine, s)
    return redirect(f"/live/{sid}", msg)


@router.post("/live/{sid}/speak")
def live_speak(request: Request, sid: int, sess=Depends(require_student), form=Depends(form_data)):
    return _student_action(request, sid, form, lambda w, f, mine, s: C.add_speaker(
        w, sid, mine["id"], request.state.actor.id, "moderated" if s["mode"] == "moderated" else "general"),
        "You're on the speakers list.")


@router.post("/live/{sid}/withdraw")
def live_withdraw(request: Request, sid: int, sess=Depends(require_student), form=Depends(form_data)):
    def act(w, f, mine, s):
        for e in C.waiting(w.conn, sid):
            if e["delegation_id"] == mine["id"]:
                C.withdraw_speaker(w, e["id"])
    return _student_action(request, sid, form, act, "Taken off the speakers list.")


@router.post("/live/{sid}/vote")
def live_vote(request: Request, sid: int, sess=Depends(require_student), form=Depends(form_data)):
    def act(w, f, mine, s):
        if not s["current_division_id"]:
            raise UserError("There is no vote open right now.")
        C.cast_vote(w, s["current_division_id"], mine["id"], f.get("vote"))
    return _student_action(request, sid, form, act, "Vote recorded. You can change it until voting closes.")


@router.post("/live/{sid}/motion")
def live_motion(request: Request, sid: int, sess=Depends(require_student), form=Depends(form_data)):
    def act(w, f, mine, s):
        secs = (form_int(f.get("duration_min"), 0) or 0) * 60 or None
        C.propose_motion(w, sid, form_int(f.get("procedure_motion_id")), mine["id"], secs, form_int(f.get("speaking_time_s")),
                         f.get("topic") or "")
    return _student_action(request, sid, form, act, "Motion raised. The chair will consider it.")


@router.post("/live/{sid}/second/{mid}")
def live_second(request: Request, sid: int, mid: int, sess=Depends(require_student), form=Depends(form_data)):
    def act(w, f, mine, s):
        m = one(w.conn, "SELECT session_id FROM motion WHERE id = ?", (mid,))
        if not m or m["session_id"] != sid:
            raise UserError("That motion isn't in this session.", 404)
        C.second_motion(w, mid, mine["id"])
    return _student_action(request, sid, form, act, "Seconded.")


# ---------- projector (no sign-in; the link carries an unguessable token) ----------

@router.get("/projector/{token}")
def projector(request: Request, token: str):
    with request.app.state.db.read() as conn:
        sid = scalar(conn, "SELECT id FROM live_session WHERE projector_token = ?", (token,))
        if not sid:
            raise UserError("That projector link isn't valid. Copy it again from the chair screen.", 404)
        ctx = session_view(conn, sid)
    return render(request, "chair/projector.html", {"title": f"{ctx['s']['committee']} — live", "token": token, **ctx})


@router.get("/projector/{token}/f")
def projector_fragment(request: Request, token: str):
    with request.app.state.db.read() as conn:
        sid = scalar(conn, "SELECT id FROM live_session WHERE projector_token = ?", (token,))
        if not sid:
            raise UserError("Not found.", 404)
        ctx = session_view(conn, sid)
    return render(request, "chair/_projector_main.html", {"token": token, **ctx})
