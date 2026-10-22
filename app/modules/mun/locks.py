"""Paragraph locks: one editor per paragraph at a time, with live updates to everyone else (D-004).

A lock is taken when an editor opens a paragraph and kept alive by heartbeats
from the page. It lapses LOCK_TTL_S seconds after the last heartbeat, so a
closed laptop never blocks a paragraph for long. Saving checks the lock.
"""
from __future__ import annotations

from app.db import Writer, one, rows
from app.errors import UserError
from app.util import now

LOCK_TTL_S = 60


def _channel(conn, paragraph_id: int) -> str:
    r = one(conn, "SELECT resolution_id FROM paragraph WHERE id = ?", (paragraph_id,))
    return f"resolution:{r['resolution_id']}" if r else ""


def _fresh(lock: dict | None) -> bool:
    return bool(lock) and now() - lock["heartbeat_at"] < LOCK_TTL_S


def _is_mine(lock: dict, actor) -> bool:
    return lock["holder_kind"] == actor.kind and lock["holder_id"] == actor.id


def active_locks(conn, resolution_id: int, actor=None) -> dict[int, dict]:
    out = {}
    for l in rows(conn, "SELECT l.* FROM paragraph_lock l JOIN paragraph p ON p.id = l.paragraph_id WHERE p.resolution_id = ?",
                  (resolution_id,)):
        if _fresh(l):
            l["mine"] = bool(actor) and _is_mine(l, actor)
            out[l["paragraph_id"]] = l
    return out


def acquire(w: Writer, paragraph_id: int) -> dict:
    """Take or refresh the lock. Raises 409 if someone else holds a fresh lock."""
    lock = one(w.conn, "SELECT * FROM paragraph_lock WHERE paragraph_id = ?", (paragraph_id,))
    t = now()
    if lock and _fresh(lock) and not _is_mine(lock, w.actor):
        raise UserError(f"{lock['holder_label']} is editing this paragraph right now. You can table an amendment, "
                        "or try again when they finish.", 409)
    if lock and _is_mine(lock, w.actor) and _fresh(lock):
        w.conn.execute("UPDATE paragraph_lock SET heartbeat_at = ? WHERE paragraph_id = ?", (t, paragraph_id))
        return {"state": "held", "renewed": True}
    w.conn.execute("INSERT OR REPLACE INTO paragraph_lock (paragraph_id, holder_kind, holder_id, holder_label, acquired_at, "
                   "heartbeat_at) VALUES (?,?,?,?,?,?)", (paragraph_id, w.actor.kind, w.actor.id, w.actor.label, t, t))
    w.log("paragraph", paragraph_id, "lock", None, {"holder": w.actor.label}, _channel(w.conn, paragraph_id))
    return {"state": "held", "renewed": False}


def release(w: Writer, paragraph_id: int) -> None:
    lock = one(w.conn, "SELECT * FROM paragraph_lock WHERE paragraph_id = ?", (paragraph_id,))
    if lock and (_is_mine(lock, w.actor) or not _fresh(lock) or w.actor.is_staff):
        w.conn.execute("DELETE FROM paragraph_lock WHERE paragraph_id = ?", (paragraph_id,))
        w.log("paragraph", paragraph_id, "unlock", None, {"holder": lock["holder_label"]}, _channel(w.conn, paragraph_id))


def check_can_save(w: Writer, paragraph_id: int) -> None:
    lock = one(w.conn, "SELECT * FROM paragraph_lock WHERE paragraph_id = ?", (paragraph_id,))
    if lock and _fresh(lock) and not _is_mine(lock, w.actor):
        raise UserError(f"{lock['holder_label']} is editing this paragraph, so your change wasn't saved. "
                        "Copy your text, wait for them to finish, or table it as an amendment.", 409)
