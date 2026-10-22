"""Student join (D-003): type the class code, tap your name. No password.

Mitigations for the accepted impersonation risk (spec §8.4): a claimed name is
locked to the device that claimed it; another device asking for it needs a
teacher's approval; everything students do is attributed in the event log;
class codes can be rotated at any time.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.db import one, rows, scalar
from app.errors import UserError
from app.util import display_name, new_token, now_iso, token_hash
from app.web.auth import SESSION_COOKIE, create_session, join_throttle, require_student
from app.web.http import redirect, form_data
from app.web.templating import render

router = APIRouter()
CLAIM_COOKIE = "soc_claim"


def _set_session(resp, token: str):
    resp.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 120)
    return resp


def _class_by_code(conn, code: str) -> dict | None:
    code = (code or "").strip().upper().replace(" ", "").replace("-", "")
    return one(conn, "SELECT * FROM class WHERE code = ? AND active = 1 AND archived_at IS NULL AND deleted_at IS NULL", (code,))


@router.get("/join")
def join_form(request: Request):
    s = request.state.session
    if s and s.kind == "student":
        return RedirectResponse("/me", status_code=303)
    return render(request, "people/join.html", {"title": "Join your class"})


@router.post("/join")
def join_code(request: Request, form=Depends(form_data)):
    key = "join:" + (request.cookies.get("soc_csrf") or "anon")
    wait = join_throttle.check(key)
    if wait:
        raise UserError(f"Too many tries. Wait {wait} seconds and check the code on the board.", 429)
    with request.app.state.db.read() as conn:
        c = _class_by_code(conn, form.get("code"))
    if not c:
        join_throttle.fail(key)
        raise UserError("That class code didn't match a class. Check the code on the board (letters and numbers; there is no O or I).")
    join_throttle.ok(key)
    return redirect(f"/join/{c['code']}")


@router.get("/join/wait")
def join_wait(request: Request):
    claim = request.cookies.get(CLAIM_COOKIE)
    if not claim:
        return RedirectResponse("/join", status_code=303)
    with request.app.state.db.read() as conn:
        req = one(conn, "SELECT cr.*, st.first_name, st.last_initial FROM claim_request cr JOIN student st ON st.id = cr.student_id "
                        "WHERE cr.token_hash = ?", (token_hash(claim),))
        if not req:
            return RedirectResponse("/join", status_code=303)
        if req["status"] == "approved":
            conn.execute("UPDATE claim_request SET status = 'used' WHERE id = ?", (req["id"],))
            token = create_session(conn, "student", student_id=req["student_id"], class_id=req["class_id"])
            conn.commit()
            resp = _set_session(redirect("/me", "Your teacher approved this device."), token)
            resp.delete_cookie(CLAIM_COOKIE)
            return resp
    return render(request, "people/join_wait.html", {"title": "Waiting for your teacher", "req": req},
                  headers={"Refresh": "4"} if req["status"] == "pending" else None)


@router.get("/join/{code}")
def join_pick(request: Request, code: str):
    with request.app.state.db.read() as conn:
        c = _class_by_code(conn, code)
        if not c:
            raise UserError("That class code isn't valid any more. Ask your teacher for the new one.", 404)
        students = rows(conn, "SELECT st.id, st.first_name, st.last_initial, (SELECT COUNT(*) FROM device_session d WHERE d.student_id = st.id "
                              "AND d.revoked_at IS NULL) AS locked FROM student st WHERE st.class_id = ? AND st.active = 1 "
                              "AND st.deleted_at IS NULL ORDER BY st.first_name, st.last_initial", (c["id"],))
    return render(request, "people/join_pick.html", {"title": f"Join {c['name']}", "c": c, "students": students})


@router.post("/join/{code}/{student_id}")
def join_claim(request: Request, code: str, student_id: int):
    with request.app.state.db.read() as conn:
        c = _class_by_code(conn, code)
        if not c:
            raise UserError("That class code isn't valid any more. Ask your teacher for the new one.", 404)
        st = one(conn, "SELECT * FROM student WHERE id = ? AND class_id = ? AND active = 1 AND deleted_at IS NULL", (student_id, c["id"]))
        if not st:
            raise UserError("That name isn't in this class.", 404)
        locked = scalar(conn, "SELECT COUNT(*) FROM device_session WHERE student_id = ? AND revoked_at IS NULL", (student_id,))
        name = display_name(st["first_name"], st["last_initial"])
        if not locked:
            token = create_session(conn, "student", student_id=student_id, class_id=c["id"])
            conn.execute("INSERT INTO event_log (at, actor_kind, actor_id, actor_label, entity, entity_id, action, channel, action_group) "
                         "VALUES (?,?,?,?,?,?,?,?,?)", (now_iso(), "student", student_id, name, "student", str(student_id),
                                                        "joined_on_device", f"class:{c['id']}", new_token()[:12]))
            conn.commit()
            request.app.state.hub.publish({f"class:{c['id']}"}, 0)
            return _set_session(redirect("/me", f"Welcome, {st['first_name']}. This device is now yours for this class."), token)
        # Name already locked to another device: ask the teacher.
        claim = new_token()
        conn.execute("INSERT INTO claim_request (class_id, student_id, token_hash, created_at) VALUES (?,?,?,?)",
                     (c["id"], student_id, token_hash(claim), now_iso()))
        conn.execute("INSERT INTO event_log (at, actor_kind, actor_id, actor_label, entity, entity_id, action, channel, action_group) "
                     "VALUES (?,?,?,?,?,?,?,?,?)", (now_iso(), "anonymous", None, "Unknown device", "student", str(student_id),
                                                    "second_device_request", f"class:{c['id']}", new_token()[:12]))
        conn.commit()
    request.app.state.hub.publish({f"class:{c['id']}"}, 0)
    resp = redirect("/join/wait")
    resp.set_cookie(CLAIM_COOKIE, claim, httponly=True, samesite="lax", max_age=3600)
    return resp


@router.get("/me")
def me(request: Request, sess=Depends(require_student)):
    sid = sess.actor.id
    with request.app.state.db.read() as conn:
        st = one(conn, "SELECT st.*, c.name AS class_name FROM student st JOIN class c ON c.id = st.class_id WHERE st.id = ?", (sid,))
        dels = rows(conn, "SELECT d.id AS delegation_id, d.iso3, c.name AS country, c.flag_svg, cm.id AS committee_id, cm.name AS committee, "
                          "dm.role, (SELECT id FROM live_session ls WHERE ls.committee_id = cm.id AND ls.state = 'open' ORDER BY id DESC LIMIT 1) AS live "
                          "FROM delegation_member dm JOIN delegation d ON d.id = dm.delegation_id JOIN country c ON c.iso3 = d.iso3 "
                          "JOIN committee cm ON cm.id = d.committee_id WHERE dm.student_id = ? AND dm.deleted_at IS NULL AND d.deleted_at IS NULL "
                          "AND cm.deleted_at IS NULL", (sid,))
        class_live = rows(conn, "SELECT ls.id, cm.name FROM live_session ls JOIN committee cm ON cm.id = ls.committee_id "
                                "WHERE cm.class_id = ? AND ls.state = 'open'", (st["class_id"],))
        tasks = rows(conn, "SELECT t.*, d.committee_id FROM task t JOIN delegation d ON d.id = t.delegation_id "
                           "WHERE t.assignee_student_id = ? AND t.deleted_at IS NULL ORDER BY t.status = 'done', t.id", (sid,))
        resolutions = rows(conn, "SELECT r.id, r.title, cm.name AS committee FROM resolution r JOIN committee cm ON cm.id = r.committee_id "
                                 "WHERE r.deleted_at IS NULL AND (cm.class_id = ? OR cm.id IN (SELECT d.committee_id FROM delegation d "
                                 "JOIN delegation_member dm ON dm.delegation_id = d.id WHERE dm.student_id = ? AND dm.deleted_at IS NULL))",
                           (st["class_id"], sid))
        from app.modules.people.pathway import pathway
        path = pathway(conn, sid)
        extra = {}
        try:
            from app.modules.debating.service import student_summary
            extra = student_summary(conn, sid)
        except ImportError:
            pass
    return render(request, "people/me.html", {"title": "My page", "st": st, "dels": dels, "class_live": class_live, "tasks": tasks,
                                              "resolutions": resolutions, "path": path, **extra})
