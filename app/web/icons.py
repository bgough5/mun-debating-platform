"""Icons (D-059): one Lucide icon per concept, served from a local SVG sprite.

Templates call `icon("vote")` or `icon("undo", "Undo")`. Without a label the icon
is decorative (aria-hidden) and the visible text beside it carries the meaning;
with a label it is announced, for icon-only controls. Unknown names raise, so a
typo fails a test instead of showing nothing.

The sprite is built by `python tools/build_icons.py <lucide-static/icons dir>`
from lucide-static (ISC licence, app/static/icons/LICENSE-lucide.txt).
"""
from __future__ import annotations

from markupsafe import Markup, escape

SPRITE = "/static/icons/sprite.svg"

# concept -> Lucide icon name. One icon per concept, used everywhere.
CONCEPTS = {
    # MUN and live sessions
    "speakers": "mic", "timer": "timer", "motion": "hand", "vote": "vote", "amendment": "file-pen-line",
    "evidence": "file-search", "task": "list-checks", "delegation": "flag", "bloc": "users-round",
    "resolution": "file-text", "committee": "landmark", "conference": "globe", "chair": "gavel",
    "projector": "presentation", "prediction": "chart-column", "calibration": "target", "stage": "list-ordered",
    "roll-call": "clipboard-list", "whip": "scale",
    # Debating
    "debate": "messages-square", "ballot": "clipboard-check", "house": "shield", "ladder": "trophy",
    "draw": "shuffle", "adjudicator": "user-check", "room": "door-open", "award": "award",
    # People and pathway
    "class": "school", "student": "user", "people": "users", "pathway": "graduation-cap", "join": "log-in",
    # Actions
    "export": "download", "import": "upload", "print": "printer", "undo": "undo-2", "history": "history",
    "settings": "settings", "add": "plus", "edit": "square-pen", "delete": "trash-2", "restore": "rotate-ccw",
    "search": "search", "lock": "lock", "unlock": "lock-open", "play": "play", "pause": "pause",
    "refresh": "refresh-cw", "view": "eye", "qr": "qr-code", "sign-out": "log-out", "next": "chevron-right", "menu": "menu",
    "x": "x", "check": "check",
    # Committee floor (D-068)
    "message": "message-circle", "speech": "notebook-pen", "point": "circle-alert", "friends": "handshake", "tracked": "file-diff",
    # Status and information
    "demo": "flask-conical", "help": "circle-help", "info": "info", "warning": "triangle-alert",
    "error": "circle-x", "ok": "circle-check", "inbox": "inbox", "ai": "bot", "data": "database",
    "glossary": "book-open", "practice": "dumbbell", "home": "house", "calendar": "calendar", "clock": "clock",
    # Stances (always beside the word)
    "yes": "circle-check", "no": "circle-x", "abstain": "circle-minus", "unknown": "circle-dashed",
}


def icon(name: str, label: str | None = None, cls: str = "") -> Markup:
    if name not in CONCEPTS:
        raise KeyError(f"Unknown icon {name!r}; add it to app/web/icons.py CONCEPTS and rebuild the sprite")
    classes = "icon" + (f" {cls}" if cls else "")
    if label:
        a11y = f'role="img" aria-label="{escape(label)}"'
    else:
        a11y = 'aria-hidden="true"'
    return Markup(f'<svg class="{classes}" {a11y} focusable="false"><use href="{SPRITE}#i-{name}"></use></svg>')
