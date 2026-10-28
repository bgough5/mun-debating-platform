"""Student sign-in (D-079, replacing D-003's class code and name list): each student has a personal code with their
name built in. Opening their link (`/s/<code>`) or typing the code on `/join` signs them in on any laptop. No list of
names is shown, so an absent student's name can't be taken, and nothing waits for a teacher's approval.

Signing in on a laptop signs that student out everywhere else (one laptop at a time), so a shared school laptop
never stays signed in as the last student who used it once they sign in somewhere new. Attempts are throttled;
the teacher can give a student a new code at any time.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.db import one, rows, scalar
from app.errors import UserError
from app.modules.people import codes
from app.util import display_name, new_token, now_iso
from app.web.auth import SESSION_COOKIE, create_session, join_throttle, require_student, revoke_devices
from app.web.http import redirect, form_data
from app.web.templating import render

router = APIRouter()


def _set_session(resp, token: str):
    resp.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 120)
    return resp


def _sign_in(request: Request, raw: str):
    key = "join:" + (request.client.host if request.client else "anon")
    wait = join_throttle.check(key)
    if wait:
        raise UserError(f"Too many tries. Wait {wait} seconds, then type the code from your card again.", 429)
    with request.app.state.db.read() as conn:
        st = codes.student_by_code(conn, raw)
        if not st:
            join_throttle.fail(key)
            is_class = one(conn, "SELECT 1 FROM class WHERE code = ?", (codes.normalise(raw),))
            raise UserError("That's the class code. Type your own code: it's on your sign-in card, under your name." if is_class else
                            "That code didn't match. Check your sign-in card (six letters and numbers; there is no O, 0, I or 1).")
        join_throttle.ok(key)
        # One laptop at a time: signing in here signs this student out of any other laptop.
        revoke_devices(conn, "student_id = ?", (st["id"],))
        token = create_session(conn, "student", student_id=st["id"], class_id=st["class_id"])
        conn.execute("INSERT INTO event_log (at, actor_kind, actor_id, actor_label, entity, entity_id, action, channel, action_group) "
                     "VALUES (?,?,?,?,?,?,?,?,?)", (now_iso(), "student", st["id"], display_name(st["first_name"], st["last_initial"]),
                                                    "student", str(st["id"]), "signed_in", f"class:{st['class_id']}", new_token()[:12]))
        conn.commit()
    request.app.state.hub.publish({f"class:{st['class_id']}"}, 0)
    return _set_session(redirect("/me", f"Welcome, {st['first_name']}."), token)


@router.get("/join")
def join_form(request: Request):
    s = request.state.session
    if s and s.kind == "student":
        return RedirectResponse("/me", status_code=303)
    return render(request, "people/join.html", {"title": "Sign in"})


@router.post("/join")
def join_code(request: Request, form=Depends(form_data)):
    return _sign_in(request, form.get("code") or "")


@router.get("/s/{code}")
def join_link(request: Request, code: str):
    """A student's own link, printed on their card: opening it signs them in."""
    return _sign_in(request, code)


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
