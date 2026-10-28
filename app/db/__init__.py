"""SQLite access, migrations and event-logged writes.

Every change to data goes through `Writer`, which appends to `event_log`
(spec §6.6). That log is the source of version history, undo, minutes and
the "who changed what" record.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
import weakref
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

from app.util import now_iso

_TIMING = os.environ.get("SOC_TIMING_LOG")
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

# Tables whose primary key is not `id`.
PRIMARY_KEYS = {"country": "iso3", "app_setting": "key", "event_log": "seq"}


def pk_of(table: str) -> str:
    return PRIMARY_KEYS.get(table, "id")


def connect(path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def migrate(conn: sqlite3.Connection) -> list[str]:
    """Apply numbered SQL migrations not yet applied. Returns names applied."""
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)"
    )
    done = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
    applied = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version = int(path.name.split("_", 1)[0])
        if version in done:
            continue
        sql = path.read_text(encoding="utf-8")
        try:
            conn.executescript("BEGIN;\n" + sql + "\nCOMMIT;")
        except Exception:
            conn.execute("ROLLBACK") if conn.in_transaction else None
            raise
        conn.execute(
            "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
            (version, path.name, now_iso()),
        )
        conn.commit()
        applied.append(path.name)
    return applied


def rows(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, tuple(params))]


def one(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> dict | None:
    r = conn.execute(sql, tuple(params)).fetchone()
    return dict(r) if r else None


def scalar(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()):
    r = conn.execute(sql, tuple(params)).fetchone()
    return r[0] if r else None


def columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


@dataclass
class Actor:
    kind: str                 # coordinator | staff | student | system | projector
    id: int | None = None
    label: str = ""
    class_id: int | None = None

    @property
    def is_staff(self) -> bool:
        return self.kind in ("coordinator", "staff")

    @property
    def is_coordinator(self) -> bool:
        return self.kind == "coordinator"


SYSTEM = Actor("system", None, "System")


@dataclass
class Writer:
    """One user action: a transaction whose events share an action_group."""
    conn: sqlite3.Connection
    actor: Actor
    group: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    channels: set = field(default_factory=set)
    last_seq: int = 0

    # ---- logging ----
    def log(self, entity: str, entity_id, action: str, before=None, after=None,
            channel: str = "", undo_of: int | None = None) -> int:
        cur = self.conn.execute(
            "INSERT INTO event_log (at, actor_kind, actor_id, actor_label, entity, entity_id, action, "
            "before_json, after_json, channel, action_group, undo_of) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (now_iso(), self.actor.kind, self.actor.id, self.actor.label, entity, str(entity_id), action,
             json.dumps(before, default=str) if before is not None else None,
             json.dumps(after, default=str) if after is not None else None,
             channel, self.group, undo_of),
        )
        if channel:
            self.channels.add(channel)
        self.last_seq = cur.lastrowid
        return cur.lastrowid

    def touch(self, *channels: str) -> None:
        self.channels.update(c for c in channels if c)

    # ---- row helpers ----
    def get(self, table: str, key) -> dict | None:
        return one(self.conn, f"SELECT * FROM {table} WHERE {pk_of(table)} = ?", (key,))

    def insert(self, table: str, values: dict, channel: str = "", log: bool = True):
        cols = list(values)
        cur = self.conn.execute(
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
            [values[c] for c in cols],
        )
        key = values.get(pk_of(table), cur.lastrowid) if pk_of(table) != "id" else cur.lastrowid
        if log:
            self.log(table, key, "create", None, self.get(table, key), channel)
        else:
            self.touch(channel)
        return key

    def update(self, table: str, key, changes: dict, channel: str = "", action: str = "update") -> bool:
        before = self.get(table, key)
        if before is None:
            raise KeyError(f"{table} {key} not found")
        changes = {k: v for k, v in changes.items() if before.get(k) != v}
        if not changes:
            return False
        sets = ", ".join(f"{c} = ?" for c in changes)
        self.conn.execute(f"UPDATE {table} SET {sets} WHERE {pk_of(table)} = ?", [*changes.values(), key])
        self.log(table, key, action, before, self.get(table, key), channel)
        return True

    def soft_delete(self, table: str, key, channel: str = "") -> None:
        self.update(table, key, {"deleted_at": now_iso()}, channel, action="delete")

    def restore(self, table: str, key, channel: str = "") -> None:
        self.update(table, key, {"deleted_at": None}, channel, action="restore")

    def hard_delete(self, table: str, key, channel: str = "") -> None:
        before = self.get(table, key)
        self.conn.execute(f"DELETE FROM {table} WHERE {pk_of(table)} = ?", (key,))
        self.log(table, key, "purge", before, None, channel)


class Database:
    def __init__(self, path: Path | str, hub=None):
        self.path = Path(path)
        self.hub = hub
        self._local = threading.local()
        # One read connection per thread, with a weak reference to its thread. The server's worker threads come and
        # go (anyio retires idle ones), so connections of finished threads are closed when the next one is opened;
        # before Phase 7 they were kept forever, which grew memory through a long lesson (D-064).
        self._pooled: list[tuple[weakref.ref, sqlite3.Connection]] = []
        self._pool_lock = threading.Lock()
        self.disposed = False

    def connect(self) -> sqlite3.Connection:
        if self.disposed:
            from app.errors import UserError
            raise UserError("The data was just switched or restored. Reload the page.", 409)
        return connect(self.path)

    def dispose(self) -> None:
        """Close every pooled connection before the database file is replaced or switched."""
        self.disposed = True
        with self._pool_lock:
            for _, c in self._pooled:
                try:
                    c.close()
                except sqlite3.Error:
                    pass
            self._pooled.clear()

    def _prune(self) -> None:
        """Close connections whose thread has finished (call with _pool_lock held)."""
        keep = []
        for ref, c in self._pooled:
            t = ref()
            if t is not None and t.is_alive():
                keep.append((ref, c))
            else:
                try:
                    c.close()
                except sqlite3.Error:
                    pass
        self._pooled = keep

    def pooled_count(self) -> int:
        with self._pool_lock:
            return len(self._pooled)

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        """A connection for reading, reused per thread (opening one costs ~0.5 ms).

        If the caller wrote something without committing, it is rolled back here,
        so a reused connection never carries an open transaction."""
        conn = getattr(self._local, "conn", None)
        if conn is None or self.disposed:
            conn = self.connect()
            self._local.conn = conn
            with self._pool_lock:
                self._prune()
                self._pooled.append((weakref.ref(threading.current_thread()), conn))
        try:
            yield conn
        finally:
            if conn.in_transaction:
                conn.rollback()

    @contextmanager
    def write(self, actor: Actor) -> Iterator[Writer]:
        conn = self.connect()
        w = Writer(conn, actor)
        try:
            t0 = time.perf_counter()
            conn.execute("BEGIN IMMEDIATE")
            t1 = time.perf_counter()
            yield w
            conn.commit()
            if _TIMING:
                with open(_TIMING, "a") as f:
                    f.write(f"{time.time():.3f} WRITE wait={t1 - t0:.4f} held={time.perf_counter() - t1:.4f} "
                            f"thread={threading.current_thread().name} actor={actor.kind}\n")
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()
        if self.hub is not None and w.channels:
            self.hub.publish(w.channels, w.last_seq)


# ---------------- undo and restore ----------------

UNDOABLE = {"create", "update", "delete", "restore", "restore_version"}


def undo_last(w: Writer, entity_filter: set[str] | None = None) -> dict | None:
    """Revert the actor's most recent undoable action group.

    Returns a summary dict, or None if there is nothing to undo.
    """
    a = w.actor
    params: list = [a.kind, a.id]
    sql = ("SELECT * FROM event_log WHERE actor_kind = ? AND actor_id IS ? AND undone_by IS NULL "
           "AND undo_of IS NULL AND action IN ('create','update','delete','restore','restore_version')")
    if entity_filter:
        sql += f" AND entity IN ({','.join('?' for _ in entity_filter)})"
        params += sorted(entity_filter)
    last = one(w.conn, sql + " ORDER BY seq DESC LIMIT 1", params)
    if not last:
        return None
    group = rows(w.conn, "SELECT * FROM event_log WHERE action_group = ? AND undone_by IS NULL ORDER BY seq DESC",
                 (last["action_group"],))
    undone = []
    for ev in group:
        if ev["action"] not in UNDOABLE:
            continue
        table, key = ev["entity"], ev["entity_id"]
        if pk_of(table) == "id":
            key = int(key)
        before = json.loads(ev["before_json"]) if ev["before_json"] else None
        cols = set(columns(w.conn, table))
        if ev["action"] == "create":
            if "deleted_at" in cols:
                w.conn.execute(f"UPDATE {table} SET deleted_at = ? WHERE {pk_of(table)} = ?", (now_iso(), key))
            # Tables without soft delete (version rows) are history: the
            # pointer update in the same group is what gets reverted.
        elif before is not None:
            restore_cols = [c for c in before if c in cols and c != pk_of(table)]
            w.conn.execute(
                f"UPDATE {table} SET {', '.join(c + ' = ?' for c in restore_cols)} WHERE {pk_of(table)} = ?",
                [before[c] for c in restore_cols] + [key],
            )
        seq = w.log(table, key, "undo", None, w.get(table, key), ev["channel"], undo_of=ev["seq"])
        w.conn.execute("UPDATE event_log SET undone_by = ? WHERE seq = ?", (seq, ev["seq"]))
        undone.append(ev)
    return {"group": last["action_group"], "events": undone, "entity": last["entity"], "entity_id": last["entity_id"]}


def history(conn: sqlite3.Connection, entity: str, entity_id) -> list[dict]:
    return rows(conn, "SELECT * FROM event_log WHERE entity = ? AND entity_id = ? ORDER BY seq DESC",
                (entity, str(entity_id)))


def restore_from_event(w: Writer, seq: int) -> None:
    """Write a past event's `after` snapshot back as the current row."""
    ev = one(w.conn, "SELECT * FROM event_log WHERE seq = ?", (seq,))
    if not ev or not ev["after_json"]:
        raise ValueError("That version cannot be restored.")
    table = ev["entity"]
    key = int(ev["entity_id"]) if pk_of(table) == "id" else ev["entity_id"]
    after = json.loads(ev["after_json"])
    cols = set(columns(w.conn, table))
    changes = {c: v for c, v in after.items() if c in cols and c != pk_of(table)}
    w.update(table, key, changes, ev["channel"], action="restore_version")
