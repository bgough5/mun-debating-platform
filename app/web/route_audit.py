"""Permissions audit (Phase 5): which role each route requires, read from the code itself.

Every route must either sit in PUBLIC (with a reason) or depend on one of the
require_* checks in app.web.auth. `tests/api/test_permissions_matrix.py` fails
if a new route has neither, and `python tools/permissions_report.py` writes the
table to docs/permissions.md.
"""
from __future__ import annotations

from fastapi.routing import APIRoute, APIWebSocketRoute

from app.web import auth

# Lowest role that passes each check, in order of privilege.
LEVELS = ["public", "signed_in", "student", "staff", "coordinator"]
CHECKS = {auth.require_any: "signed_in", auth.require_student: "student",
          auth.require_staff: "staff", auth.require_coordinator: "coordinator"}

# Routes anyone may open, and why. Each one still does its own checks where noted.
PUBLIC = {
    "/": "Home: signed-out visitors see the sign-in links only",
    "/healthz": "Liveness check for the start script; returns 'ok' only",
    "/setup": "First-run passphrase setup; refuses once a passphrase exists",
    "/login": "Sign-in form (throttled)",
    "/logout": "Sign-out",
    "/accessibility": "Accessibility statement",
    "/privacy": "Privacy notice",
    "/practice-game": "Link to the frozen v2 practice game",
    "/practice-game/solo": "The frozen v2 solo game page",
    "/join": "Students: type your personal sign-in code (throttled)",
    "/play": "Single player: choose a scenario; open to guests, who keep nothing (D-099)",
    "/play/start": "Single player: start a game; a guest's is never stored, a signed-in student's is their own (D-099)",
    "/play/g/{code}/{iso3}/{seed}/{pid}": "Single player as a guest: the game is in the address and the browser; nothing stored (D-099)",
    "/play/api": "Single player moves: a guest's game is checked and answered without storing it; a saved game needs the student's own session (D-099)",
    "/session": "The Session's title screen: open to guests; a signed-in student also sees only their own saved sessions (D-101)",
    "/session/new": "The Session: set up a new campaign; nothing is stored until a signed-in student starts one (D-101)",
    "/session/seats/{code}": "The Session: the seats in a scenario for the setup screen; scenario data only (D-101)",
    "/session/guest/{code}": "The Session as a guest: the game lives in the browser, signed by the server; nothing stored (D-101)",
    "/session/profile": "The Session: your record; a signed-in student sees only their own finished sessions, a guest's is kept in their browser (D-101)",
    "/session/account": "The Session: sign in or create a player account (sign-up only once the school approves it; D-103)",
    "/session/account/signin": "The Session: sign in to a player account (throttled; one generic error)",
    "/session/account/create": "The Session: create a player account; refused unless the school's approval is recorded (throttled)",
    "/session/account/signout": "The Session: sign this browser's player account out",
    "/session/account/password": "The Session: change your own password; needs your current password",
    "/session/account/delete": "The Session: erase your own account and its saves; needs your password",
    "/session/a/{save_id}": "The Session: a player account's saved campaign; only the account that owns it (checked against its session)",
    "/session/almanac": "The Session's Almanac: choose a scenario; reference material only, nothing personal (D-101)",
    "/session/almanac/{code}": "The Session's Almanac for one scenario: procedure, paths, skills and the country files with sources (D-101)",
    "/session/api": "The Session's moves: a guest's signed state is checked and returned without storing it; a saved session needs the student's own session (D-101)",
    "/s/{code}": "Students: your own sign-in link from your card; needs a valid personal code (throttled)",
    "/projector/{token}": "Projector view of a live session; needs the session's unguessable token",
    "/projector/{token}/f": "Projector view fragment; needs the token",
    "/projector/{token}/state.json": "The board's live state (D-092): what the projector shows anyway; needs the token",
    "/projector/{token}/plain": "The plain projector page, the board's fallback; needs the token",
    "/debating/projector/{token}": "Projector view of a debating event; needs the event's unguessable token",
    "/debating/projector/{token}/f": "Projector fragment; needs the token",
    "/debating/present/{token}": "Projector view of a class debate or speaking round; needs the run's unguessable token",
    "/debating/present/{token}/f": "Class run projector fragment; needs the token",
    "/help": "Help index: general guidance only, no data",
    "/help/glossary": "MUN and debating glossary: static text",
    "/help/students": "Student quick-start: static text, needed before a student has joined",
    "/ws": "WebSocket: every channel subscription is checked per role (app/web/ws.py channel_allowed)",
}


def _checks(dependant) -> set[str]:
    found = set()
    for d in dependant.dependencies:
        if d.call in CHECKS:
            found.add(CHECKS[d.call])
        found |= _checks(d)
    return found


def _routes(routes):
    """Flatten included routers (newer FastAPI keeps them nested; app.main adds no prefix or dependencies)."""
    for r in routes:
        inner = getattr(r, "original_router", None)
        if inner is not None:
            yield from _routes(inner.routes)
        else:
            yield r


def classify(app) -> list[dict]:
    out = []
    for r in _routes(app.routes):
        if isinstance(r, APIRoute):
            methods = sorted(m for m in r.methods if m != "HEAD")
            found = _checks(r.dependant)
        elif isinstance(r, APIWebSocketRoute):
            methods, found = ["WS"], set()
        else:
            continue          # static files
        level = max(found, key=LEVELS.index) if found else ("public" if r.path in PUBLIC else "UNCHECKED")
        for m in methods:
            out.append({"method": m, "path": r.path, "level": level, "note": PUBLIC.get(r.path, "")})
    return sorted(out, key=lambda x: (x["path"], x["method"]))
