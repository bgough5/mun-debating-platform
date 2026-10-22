"""Home, first-run setup, staff sign-in, static information pages, and the Practice game link."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, RedirectResponse

from app.config import REPO_ROOT
from app.db import one, rows, scalar
from app.errors import UserError
from app.util import check_passphrase, hash_passphrase
from app.web.auth import SESSION_COOKIE, create_session, login_throttle, revoke_devices
from app.web.http import redirect, form_data
from app.web.templating import render

router = APIRouter()
MIN_PASSPHRASE = 10


def _set_session(resp, token: str):
    resp.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 120)
    return resp


@router.get("/")
def home(request: Request):
    s = request.app.state.settings
    if not s.get("coordinator_hash"):
        return RedirectResponse("/setup", status_code=303)
    sess = request.state.session
    if sess and sess.kind == "student":
        return RedirectResponse("/me", status_code=303)
    if not sess:
        return render(request, "core/landing.html", {"title": "Welcome"})
    db = request.app.state.db
    with db.read() as conn:
        from app.web.auth import staff_class_ids
        ids = staff_class_ids(conn, sess.actor)
        classes = rows(conn, "SELECT * FROM class WHERE deleted_at IS NULL AND archived_at IS NULL ORDER BY year DESC, name")
        if ids is not None:
            classes = [c for c in classes if c["id"] in ids]
        committees = rows(conn, "SELECT cm.*, cf.name AS conference FROM committee cm JOIN conference cf ON cf.id = cm.conference_id "
                                "WHERE cm.deleted_at IS NULL AND cf.deleted_at IS NULL ORDER BY cf.id DESC, cm.id")
        if ids is not None:
            committees = [c for c in committees if c["class_id"] in ids]
        tasks_open = scalar(conn, "SELECT COUNT(*) FROM task WHERE status != 'done' AND deleted_at IS NULL")
    return render(request, "core/dashboard.html", {"title": "Dashboard", "classes": classes, "committees": committees,
                                                   "tasks_open": tasks_open})


@router.get("/setup")
def setup_form(request: Request):
    if request.app.state.settings.get("coordinator_hash"):
        return RedirectResponse("/login", status_code=303)
    return render(request, "core/setup.html", {"title": "First-run setup"})


@router.post("/setup")
def setup_save(request: Request, form=Depends(form_data)):
    s = request.app.state.settings
    if s.get("coordinator_hash"):
        raise UserError("Setup is already done. Sign in instead.", 409)
    p1, p2 = form.get("passphrase") or "", form.get("passphrase2") or ""
    if len(p1) < MIN_PASSPHRASE:
        raise UserError(f"Use a passphrase of at least {MIN_PASSPHRASE} characters, e.g. four random words.")
    if p1 != p2:
        raise UserError("The two passphrases don't match. Type the same passphrase twice.")
    s.set("coordinator_hash", hash_passphrase(p1))
    with request.app.state.db.read() as conn:
        token = create_session(conn, "coordinator")
        conn.commit()
    return _set_session(redirect("/", "Coordinator passphrase set. You're signed in."), token)


@router.get("/login")
def login_form(request: Request, next: str = "/"):
    with request.app.state.db.read() as conn:
        staff = rows(conn, "SELECT id, name FROM staff WHERE active = 1 AND deleted_at IS NULL AND pass_hash != '' ORDER BY name")
    return render(request, "core/login.html", {"title": "Staff sign in", "staff": staff, "next": next})


@router.post("/login")
def login(request: Request, form=Depends(form_data)):
    who = form.get("who") or "coordinator"
    passphrase = form.get("passphrase") or ""
    nxt = form.get("next") or "/"
    if not nxt.startswith("/") or nxt.startswith("//"):
        nxt = "/"
    key = f"login:{who}"
    wait = login_throttle.check(key)
    if wait:
        raise UserError(f"Too many wrong attempts. Wait {wait} seconds, then try again.", 429)
    s = request.app.state.settings
    with request.app.state.db.read() as conn:
        if who == "coordinator":
            ok = bool(s.get("coordinator_hash")) and check_passphrase(passphrase, s.get("coordinator_hash"))
            kind, staff_id = "coordinator", None
        else:
            st = one(conn, "SELECT * FROM staff WHERE id = ? AND active = 1 AND deleted_at IS NULL", (who,))
            ok = bool(st and st["pass_hash"]) and check_passphrase(passphrase, st["pass_hash"])
            kind, staff_id = "staff", (st["id"] if st else None)
        if not ok:
            login_throttle.fail(key)
            raise UserError("That passphrase isn't right. Check caps lock and try again.", 401)
        login_throttle.ok(key)
        token = create_session(conn, kind, staff_id=staff_id)
        conn.commit()
    return _set_session(redirect(nxt), token)


@router.post("/logout")
def logout(request: Request):
    sess = request.state.session
    if sess:
        with request.app.state.db.read() as conn:
            revoke_devices(conn, "id = ?", (sess.id,))
            conn.commit()
    resp = redirect("/", "Signed out.")
    resp.delete_cookie(SESSION_COOKIE)
    return resp


# ---------- Practice game (frozen v2, D-007) ----------

SOLO_BUILD = REPO_ROOT / "src" / "WhipCount_v2_solo_built.html"


@router.get("/practice-game")
def practice_game(request: Request):
    host = request.url.hostname or "localhost"
    return render(request, "core/practice_game.html", {"title": "Practice game (Whip Count v2)", "host": host,
                                                       "solo_available": SOLO_BUILD.exists()})


@router.get("/practice-game/solo")
def practice_game_solo():
    if not SOLO_BUILD.exists():
        raise UserError("The offline build of the practice game isn't in this copy of the app.", 404)
    return FileResponse(str(SOLO_BUILD), media_type="text/html")


@router.get("/accessibility")
def accessibility(request: Request):
    return render(request, "core/accessibility.html", {"title": "Accessibility"})


@router.get("/privacy")
def privacy(request: Request):
    return render(request, "core/privacy.html", {"title": "Privacy"})


@router.get("/healthz")
def healthz(request: Request):
    with request.app.state.db.read() as conn:
        n = scalar(conn, "SELECT COUNT(*) FROM schema_migrations")
    return {"ok": True, "migrations": n, "dataset": request.app.state.settings.dataset}
