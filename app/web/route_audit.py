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
