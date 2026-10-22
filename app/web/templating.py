"""Jinja2 setup and the shared `render` helper."""
from __future__ import annotations

from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse
from jinja2 import ChoiceLoader, Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

from app.web.icons import icon

APP_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIRS = [APP_DIR / "templates"] + sorted(p for p in (APP_DIR / "modules").glob("*/templates"))

env = Environment(
    loader=ChoiceLoader([FileSystemLoader(str(d)) for d in TEMPLATE_DIRS]),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)

# Stance is never shown by colour alone (spec §9): text + symbol + colour class.
STANCE = {
    "yes": ("Yes", "yes", "st-yes"), "abstain": ("Abstain", "abstain", "st-abs"), "no": ("No", "no", "st-no"),
    "absent": ("Absent", "unknown", "st-unk"), "unknown": ("Unknown", "unknown", "st-unk"),
}
POSITION = {2: "Strongly support", 1: "Support", 0: "Neutral / abstain", -1: "Oppose", -2: "Strongly oppose"}


def stance_badge(vote: str) -> Markup:
    label, icon_name, cls = STANCE.get(vote, STANCE["unknown"])
    return Markup(f'<span class="badge {cls}">{icon(icon_name)} {escape(label)}</span>')


def position_label(pos) -> str:
    if pos is None:
        return "Note (no position)"
    try:
        return POSITION[int(round(float(pos)))]
    except (KeyError, ValueError, TypeError):
        return str(pos)


def pct(x, digits: int = 0) -> str:
    if x is None:
        return "—"
    return f"{100 * float(x):.{digits}f}%"


def num(x, digits: int = 2) -> str:
    if x is None:
        return "—"
    try:
        return f"{float(x):.{digits}f}"
    except (TypeError, ValueError):
        return str(x)


def short_time(iso: str | None) -> str:
    if not iso:
        return ""
    return iso.replace("T", " ")[:16]


def mmss(seconds) -> str:
    s = max(0, int(round(float(seconds or 0))))
    return f"{s // 60}:{s % 60:02d}"


env.globals.update(icon=icon)
env.filters.update(stance=stance_badge, position=position_label, pct=pct, num=num, when=short_time, mmss=mmss)


def today_long() -> str:
    from datetime import datetime, timezone
    from app.util import now
    d = datetime.fromtimestamp(now(), timezone.utc)
    return f"{d.day} {d:%B %Y}"


def render(request: Request, template: str, ctx: dict | None = None, status: int = 200,
           headers: dict | None = None) -> HTMLResponse:
    st = request.app.state
    session = getattr(request.state, "session", None)
    base = {
        "request": request,
        "session": session,
        "actor": session.actor if session else None,
        "csrf": getattr(request.state, "csrf", ""),
        "settings": st.settings,
        "demo": st.settings.is_demo,
        "modules": {m: st.settings.module_on(m) for m in ("mun", "chair", "debating", "people", "intelligence")},
        "flash": getattr(request.state, "flash", None),
        "req_path": request.url.path,
        "printed_on": today_long(),
    }
    base.update(ctx or {})
    html = env.get_template(template).render(**base)
    resp = HTMLResponse(html, status_code=status, headers=headers)
    return resp
