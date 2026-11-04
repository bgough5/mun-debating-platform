"""The Session (D-101): the solo campaign's pages and moves.

- `/session` is the title screen: New session, Continue, Settings, Quick vote. Open to everyone.
- `/session/new` sets a game up: scenario, country, length, rivals, victory path, tutorial.
- `/session/s/{id}` is a signed-in student's saved campaign; `/session/guest` plays a guest's campaign, which lives
  in their browser (the page reads it from there and the server checks its signature on every move).
- `POST /session/api` takes one move (JSON with the CSRF header) and answers with the new view.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Request

from app.errors import UserError
from app.modules.sim.campaign import content as K
from app.modules.sim.campaign import engine as E
from app.modules.sim.campaign import store as S
from app.web.auth import require_student
from app.web.templating import render

router = APIRouter()


def _student_id(request: Request) -> int | None:
    s = getattr(request.state, "session", None)
    return s.actor.id if s and s.actor.kind == "student" else None


def _common(request: Request) -> dict:
    return {"signed_in": bool(_student_id(request)), "paths": K.PATHS, "lengths": E.LENGTHS, "difficulties": E.DIFFICULTIES}


@router.get("/session")
def session_title(request: Request):
    me = _student_id(request)
    saves = []
    if me:
        with request.app.state.db.read() as conn:
            saves = S.my_saves(conn, me)
    return render(request, "sim/session_title.html", {"title": "The Session", "saves": saves, **_common(request)})


@router.get("/session/new")
def session_new(request: Request):
    return render(request, "sim/session_new.html", {"title": "New session", "scenarios": S.scenario_cards(), **_common(request)})


@router.get("/session/seats/{code}")
def session_seats(request: Request, code: str):
    """The seats in a scenario, with the map, for the country step of the setup (a fragment)."""
    from app.modules.chair.board import static_board
    db = request.app.state.db
    with db.read() as conn:
        with S.LOCK:
            scn = S.scenario(db, conn, code)
            seats = S.country_choices(scn)
        wmap = static_board(conn, scn.committee_id)
    return render(request, "sim/_session_seats.html", {"seats": seats, "wmap": wmap, "code": code, "scn_title": scn.title,
                                                       "veto": bool(scn.rule.veto)})


def _page(request: Request, conn, scn, view: dict, mode: str, save_id: int | None):
    from app.modules.chair.board import static_board
    return render(request, "sim/session_game.html", {"title": f"The Session: {scn.title}", "wmap": static_board(conn, scn.committee_id),
                                                     "view": view, "mode": mode, "save_id": save_id, "pack": scn.code,
                                                     **_common(request)})


@router.get("/session/s/{save_id}")
def session_saved(request: Request, save_id: int, sess=Depends(require_student)):
    db = request.app.state.db
    with db.read() as conn:
        r = S.mine(conn, save_id, request.state.actor.id)
        with S.LOCK:
            scn = S.scenario(db, conn, r["pack"])
            view = S.view(scn, r["state"])
        return _page(request, conn, scn, view, "saved", save_id)


@router.get("/session/guest/{code}")
def session_guest(request: Request, code: str):
    """A guest's game: the page loads the game from this browser and asks the server for the view."""
    db = request.app.state.db
    with db.read() as conn:
        with S.LOCK:
            scn = S.scenario(db, conn, code)
        return _page(request, conn, scn, {}, "guest", None)


def _apply(scn, g: dict, action: dict):
    try:
        return E.apply(scn, g, action)
    except E.GameError as e:
        raise UserError(str(e)) from None


def _new(scn, payload: dict) -> dict:
    iso = str(payload.get("iso3") or "").upper()
    try:
        return _start(scn, iso, payload)
    except E.GameError as e:
        raise UserError(str(e)) from None


def _start(scn, iso: str, payload: dict) -> dict:
    return E.new_game(scn, iso, str(payload.get("length") or "standard"), str(payload.get("difficulty") or "standard"),
                      str(payload.get("path") or "mandate"), seed=E.random.SystemRandom().randrange(1, 2 ** 31))


@router.post("/session/api")
def session_api(request: Request, payload: dict = Body(...)):
    """Start a game or make a move. A signed-in student's game is saved under their account; a guest's comes back
    signed, to be kept in their browser."""
    db = request.app.state.db
    me = _student_id(request)
    do = payload.get("do")
    action = payload.get("action") if isinstance(payload.get("action"), dict) else {}
    if do == "new":
        code = str(payload.get("pack") or "")
        with db.read() as conn:
            with S.LOCK:
                scn = S.scenario(db, conn, code)
                g = _new(scn, payload)
                view = S.view(scn, g)
        if me and payload.get("save", True):
            with db.write(request.state.actor) as w:
                sid = S.save_new(w, me, g)
            return {"url": f"/session/s/{sid}", "view": view}
        return {"url": f"/session/guest/{code}", "state": g, "sig": S.sign(db, g), "view": view}
    if do == "view" or do == "move":
        if payload.get("save_id"):
            if not me:
                raise UserError("Sign in to keep playing this saved session.", 403)
            with db.write(request.state.actor) as w:
                r = S.mine(w.conn, int(payload["save_id"]), me)
                with S.LOCK:
                    scn = S.scenario(db, w.conn, r["pack"])
                    g, out = (r["state"], {}) if do == "view" else _apply(scn, r["state"], action)
                    view = S.view(scn, g)
                if do == "move":
                    S.save_move(w, r["id"], g, action)
            return {"view": view, "out": out}
        g = S.verify(db, payload.get("state"), payload.get("sig"))
        with db.read() as conn:
            with S.LOCK:
                scn = S.scenario(db, conn, str(g.get("pack") or ""))
                g, out = (g, {}) if do == "view" else _apply(scn, g, action)
                view = S.view(scn, g)
        return {"view": view, "out": out, "state": g, "sig": S.sign(db, g)}
    if do == "abandon" and payload.get("save_id"):
        if not me:
            raise UserError("Sign in first.", 403)
        with db.write(request.state.actor) as w:
            r = S.mine(w.conn, int(payload["save_id"]), me)
            w.soft_delete("campaign_save", r["id"])
        return {"ok": True}
    raise UserError("That isn't something The Session can do.")
