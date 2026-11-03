"""Sign-in, sessions and role checks.

- Coordinator: one passphrase set at first run, stored hashed (scrypt) in the
  gitignored local config (D-017, spec §8.5).
- Staff: own passphrase, hashed in the staff table.
- Students: a personal sign-in code with their name built in (D-079). Signing
  in on a laptop signs the student out of any other.

A browser holds one random token in an HttpOnly cookie; the server stores
only its SHA-256. Role checks happen on the server for every route.
"""
from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass

from fastapi import HTTPException, Request

from app.db import Actor, one, rows
from app.util import display_name, new_token, now, now_iso, token_hash

SESSION_COOKIE = "soc_session"
CSRF_COOKIE = "soc_csrf"
TOUCH_EVERY_S = 60


class NotAllowed(HTTPException):
    def __init__(self, message: str = "You don't have access to that page.", status: int = 403):
        super().__init__(status_code=status, detail=message)


class NeedsLogin(HTTPException):
    def __init__(self, next_url: str = "/"):
        super().__init__(status_code=401, detail="Please sign in.")
        self.next_url = next_url


@dataclass
class Session:
    id: int
    kind: str
    actor: Actor
    student_id: int | None = None
    class_id: int | None = None


def actor_for(conn, row: dict) -> Actor:
    if row["kind"] == "coordinator":
        return Actor("coordinator", 0, "Coordinator")
    if row["kind"] == "staff":
        s = one(conn, "SELECT name FROM staff WHERE id = ?", (row["staff_id"],))
        return Actor("staff", row["staff_id"], s["name"] if s else "Staff")
    st = one(conn, "SELECT first_name, last_initial FROM student WHERE id = ?", (row["student_id"],))
    return Actor("student", row["student_id"], display_name(st["first_name"], st["last_initial"]) if st else "Student",
                 class_id=row["class_id"])


def load_session(conn, token: str | None) -> Session | None:
    if not token:
        return None
    row = one(conn, "SELECT * FROM device_session WHERE token_hash = ? AND revoked_at IS NULL", (token_hash(token),))
    if not row:
        return None
    if row["kind"] == "student":
        st = one(conn, "SELECT s.active, s.deleted_at, c.active AS class_active, c.deleted_at AS class_deleted "
                       "FROM student s JOIN class c ON c.id = s.class_id WHERE s.id = ?", (row["student_id"],))
        if not st or not st["active"] or st["deleted_at"] or not st["class_active"] or st["class_deleted"]:
            return None
    if row["kind"] == "staff":
        st = one(conn, "SELECT active, deleted_at FROM staff WHERE id = ?", (row["staff_id"],))
        if not st or not st["active"] or st["deleted_at"]:
            return None
    return Session(row["id"], row["kind"], actor_for(conn, row), row["student_id"], row["class_id"])


def create_session(conn, kind: str, staff_id=None, student_id=None, class_id=None) -> str:
    token = new_token()
    t = now_iso()
    conn.execute("INSERT INTO device_session (token_hash, kind, staff_id, student_id, class_id, csrf, created_at, "
                 "last_seen_at) VALUES (?,?,?,?,?,?,?,?)",
                 (token_hash(token), kind, staff_id, student_id, class_id, secrets.token_hex(16), t, t))
    return token


_last_touch: dict[int, float] = {}


def touch(conn, session: Session) -> None:
    t = now()
    if t - _last_touch.get(session.id, 0) < TOUCH_EVERY_S:
        return
    _last_touch[session.id] = t
    conn.execute("UPDATE device_session SET last_seen_at = ? WHERE id = ?", (now_iso(), session.id))
    conn.commit()


# ---------- per-process session cache ----------

_SESSION_CACHE: dict = {}
SESSION_CACHE_S = 5.0


def session_for(db, token):
    """Look up a browser's session. Cached for a few seconds: in a live session 30
    browsers each make several requests a second, and this lookup was a large
    share of the cost. Signing a device out clears the cache (revoke_devices)."""
    key = (id(db), token)
    hit = _SESSION_CACHE.get(key)
    t = time.monotonic()
    if hit and t - hit[0] < SESSION_CACHE_S:
        return hit[1]
    with db.read() as conn:
        sess = load_session(conn, token)
        if sess:
            touch(conn, sess)
    if len(_SESSION_CACHE) > 5000:
        _SESSION_CACHE.clear()
    _SESSION_CACHE[key] = (t, sess)
    return sess


def forget_sessions() -> None:
    _SESSION_CACHE.clear()


def revoke_devices(conn, where: str, params=()) -> int:
    """Sign devices out (UPDATE device_session ... WHERE <where>) and drop cached sessions."""
    n = conn.execute(f"UPDATE device_session SET revoked_at = ? WHERE revoked_at IS NULL AND ({where})",
                     (now_iso(), *params)).rowcount
    forget_sessions()
    return n


# ---------- login throttling (in memory, per process) ----------

class Throttle:
    def __init__(self, limit: int = 5, window_s: int = 60, lockout_s: int = 60):
        self.limit, self.window, self.lockout = limit, window_s, lockout_s
        self.fails: dict[str, list[float]] = {}
        self.locked_until: dict[str, float] = {}
        self.lock = threading.Lock()

    def check(self, key: str) -> int:
        """Seconds the caller must still wait (0 if allowed)."""
        with self.lock:
            return max(0, int(self.locked_until.get(key, 0) - time.time()))

    def fail(self, key: str) -> None:
        with self.lock:
            t = time.time()
            lst = [x for x in self.fails.get(key, []) if t - x < self.window] + [t]
            self.fails[key] = lst
            if len(lst) >= self.limit:
                self.locked_until[key] = t + self.lockout
                self.fails[key] = []

    def ok(self, key: str) -> None:
        with self.lock:
            self.fails.pop(key, None)


login_throttle = Throttle()
join_throttle = Throttle(limit=10, window_s=60, lockout_s=30)


# ---------- access helpers used by routes ----------

def staff_class_ids(conn, actor: Actor) -> set[int] | None:
    """Classes a staff member may run. None means all (coordinator)."""
    if actor.is_coordinator:
        return None
    if actor.kind != "staff":
        return set()
    return {r["class_id"] for r in rows(conn, "SELECT class_id FROM staff_class WHERE staff_id = ? AND deleted_at IS NULL",
                                       (actor.id,))}


def can_run_class(conn, actor: Actor, class_id: int | None) -> bool:
    if actor.is_coordinator:
        return True
    if actor.kind != "staff" or class_id is None:
        return False
    return class_id in (staff_class_ids(conn, actor) or set())


def student_delegation_ids(conn, student_id: int) -> set[int]:
    return {r["delegation_id"] for r in rows(
        conn, "SELECT delegation_id FROM delegation_member WHERE student_id = ? AND deleted_at IS NULL", (student_id,))}


def committee_access(conn, actor: Actor, committee_id: int) -> str:
    """'manage' | 'participate' | 'none' for a committee."""
    c = one(conn, "SELECT class_id FROM committee WHERE id = ? AND deleted_at IS NULL", (committee_id,))
    if not c:
        return "none"
    if actor.is_coordinator:
        return "manage"
    if actor.kind == "staff":
        return "manage" if can_run_class(conn, actor, c["class_id"]) else "none"
    if actor.kind == "student":
        if c["class_id"] is not None and c["class_id"] == actor.class_id:
            return "participate"
        mine = one(conn, "SELECT 1 FROM delegation_member dm JOIN delegation d ON d.id = dm.delegation_id "
                         "WHERE dm.student_id = ? AND d.committee_id = ? AND dm.deleted_at IS NULL", (actor.id, committee_id))
        if not mine:   # ticked for today's activity, still choosing or waiting for a country (D-094)
            mine = one(conn, "SELECT 1 FROM committee_roster WHERE student_id = ? AND committee_id = ? AND deleted_at IS NULL",
                       (actor.id, committee_id))
        return "participate" if mine else "none"
    return "none"


def require_staff(request: Request) -> Session:
    s = request.state.session
    if s is None:
        raise NeedsLogin(str(request.url.path))
    if not s.actor.is_staff:
        raise NotAllowed()
    return s


def require_coordinator(request: Request) -> Session:
    s = request.state.session
    if s is None:
        raise NeedsLogin(str(request.url.path))
    if not s.actor.is_coordinator:
        raise NotAllowed("Only the coordinator can do that.")
    return s


def require_any(request: Request) -> Session:
    s = request.state.session
    if s is None:
        raise NeedsLogin(str(request.url.path))
    return s


def require_student(request: Request) -> Session:
    s = request.state.session
    if s is None:
        raise NeedsLogin("/join")
    if s.kind != "student":
        raise NotAllowed("That page is for students.")
    return s
