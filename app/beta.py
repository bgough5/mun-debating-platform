"""A beta copy of The Session (Ben, 11 Nov 2026): what changes when the app runs from a beta zip.

A beta zip (built by `tools/build_session_beta.py`) carries `beta.json` beside the `app` folder:
{"tester": "...", "until": "YYYY-MM-DD", "built": "..."}. Without that file nothing here does anything, so the school
platform is unaffected. With it:
- the home page sends people straight to The Session's title page and menu;
- every Session page carries a watermark: whose copy it is, and that it isn't for sharing;
- the app refuses to start after the `until` date.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

FILE = Path(__file__).resolve().parent.parent / "beta.json"


def info() -> dict | None:
    """The beta details, or None when this isn't a beta copy (a broken file counts as a beta that has expired)."""
    if not FILE.exists():
        return None
    try:
        b = json.loads(FILE.read_text(encoding="utf-8"))
        return {"tester": str(b["tester"])[:60], "until": str(b["until"])[:10], "built": str(b.get("built", ""))[:10]}
    except (ValueError, KeyError, TypeError):
        return {"tester": "unknown", "until": "2000-01-01", "built": ""}


def expired(b: dict | None, today: date | None = None) -> bool:
    if not b:
        return False
    try:
        return (today or date.today()) > date.fromisoformat(b["until"])
    except ValueError:
        return True
