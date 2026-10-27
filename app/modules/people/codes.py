"""Personal sign-in codes (D-079). Each student has a six-character code with no 0, O, 1 or I. Their link
(`/s/<code>`) or the code typed on the join page signs them in on any laptop; no list of names is shown, so nobody
can tap an absent classmate's name."""
from __future__ import annotations

from app.db import one
from app.util import new_code

LENGTH = 6


def normalise(raw: str) -> str:
    """What a student typed or pasted (a code, a code with a dash, or the whole link) as a bare code."""
    text = (raw or "").strip().upper()
    if "/S/" in text:
        text = text.rsplit("/S/", 1)[1]
    return "".join(ch for ch in text if ch.isalnum())[:12]


def shown(code: str | None) -> str:
    """K7QM2X is shown as K7Q-M2X: easier to read off a card and type."""
    return f"{code[:3]}-{code[3:]}" if code and len(code) == LENGTH else (code or "")


def unique(conn) -> str:
    code = new_code(LENGTH)
    while one(conn, "SELECT 1 FROM student WHERE login_code = ?", (code,)) or one(conn, "SELECT 1 FROM class WHERE code = ?", (code,)):
        code = new_code(LENGTH)
    return code


def assign_missing(conn) -> int:
    """Give every student without a code one. Runs on start-up and whenever students are added."""
    ids = [r[0] for r in conn.execute("SELECT id FROM student WHERE login_code IS NULL")]
    for sid in ids:
        conn.execute("UPDATE student SET login_code = ? WHERE id = ?", (unique(conn), sid))
    return len(ids)


def student_by_code(conn, raw: str) -> dict | None:
    code = normalise(raw)
    if len(code) != LENGTH:
        return None
    return one(conn, "SELECT st.*, c.name AS class_name FROM student st JOIN class c ON c.id = st.class_id WHERE st.login_code = ? "
                     "AND st.active = 1 AND st.deleted_at IS NULL AND c.active = 1 AND c.archived_at IS NULL AND c.deleted_at IS NULL",
               (code,))
