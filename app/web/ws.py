"""WebSocket endpoint for live updates.

Protocol (JSON text frames):
  client -> {"subscribe": ["session:3", "resolution:7"], "since": 1234}
  server -> {"subscribed": [...], "denied": [...], "seq": <latest>}
            then one {"channels": [...], "seq": n, "replay": true} per missed change since `since`
  server -> {"channels": [...], "seq": n, "t": <server time>}   whenever something changes
  client -> {"ping": <client time>}  every ~20 s;  server -> {"pong": <same>, "t": <server time>}

Every subscription is checked on the server against the same rules as the
pages (spec §8.3). The projector authenticates with its session's token.
"""
from __future__ import annotations

import asyncio
import json
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.db import one, rows
from app.web.auth import SESSION_COOKIE, can_run_class, committee_access, load_session

router = APIRouter()
MAX_CHANNELS = 12
QUEUE_LIMIT = 500


class WSClient:
    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_LIMIT)
        self.overflow = False

    def queue_message(self, data: str, channels) -> None:
        try:
            self.queue.put_nowait(data)
        except asyncio.QueueFull:
            # Too far behind: tell the client to reload everything rather than lose events silently.
            self.overflow = True

    async def sender(self):
        while True:
            data = await self.queue.get()
            if self.overflow:
                self.overflow = False
                await self.ws.send_text(json.dumps({"resync": True}))
            await self.ws.send_text(data)


def channel_allowed(conn, actor, channel: str, projector_token: str | None, cap: int) -> tuple[bool, str]:
    kind, _, ident = channel.partition(":")
    if not ident.isdigit():
        return False, "bad channel"
    ident = int(ident)
    if kind == "session":
        s = one(conn, "SELECT ls.*, cm.class_id FROM live_session ls JOIN committee cm ON cm.id = ls.committee_id WHERE ls.id = ?", (ident,))
        if not s:
            return False, "no such session"
        if projector_token:
            return (projector_token == s["projector_token"]), "bad projector link"
        if actor is None:
            return False, "sign in"
        a = committee_access(conn, actor, s["committee_id"])
        if a == "none":
            return False, "no access"
        if actor.kind == "student":
            from app.db import Writer
            from app.errors import UserError
            from app.modules.chair.service import admit
            try:
                admit(Writer(conn, actor), ident, actor.id, cap)
                conn.commit()
            except UserError as e:
                conn.rollback()
                return False, e.message
        return True, ""
    if projector_token:
        if kind == "debate":
            r = one(conn, "SELECT projector_token FROM debate_event WHERE id = ?", (ident,)) if \
                one(conn, "SELECT 1 FROM sqlite_master WHERE name = 'debate_event'") else None
            return bool(r and r["projector_token"] == projector_token), "bad projector link"
        return False, "projector links only show their own session"
    if actor is None:
        return False, "sign in"
    if kind == "inbox":
        # Messages to and from a delegation (D-068): its own members, and staff who run the committee.
        d = one(conn, "SELECT committee_id FROM delegation WHERE id = ?", (ident,))
        if not d:
            return False, "no such delegation"
        if actor.kind == "student":
            from app.web.auth import student_delegation_ids
            return ident in student_delegation_ids(conn, actor.id), "not your delegation"
        return committee_access(conn, actor, d["committee_id"]) == "manage", "staff only"
    if kind == "chat":
        s = one(conn, "SELECT committee_id FROM live_session WHERE id = ?", (ident,))
        if not s:
            return False, "no such session"
        return actor.kind != "student" and committee_access(conn, actor, s["committee_id"]) == "manage", "staff only"
    if kind in ("resolution", "committee"):
        cid = ident
        if kind == "resolution":
            r = one(conn, "SELECT committee_id FROM resolution WHERE id = ?", (ident,))
            if not r:
                return False, "no such resolution"
            cid = r["committee_id"]
        return committee_access(conn, actor, cid) != "none", "no access"
    if kind == "class":
        if actor.kind == "student":
            return actor.class_id == ident, "not your class"
        return can_run_class(conn, actor, ident), "staff only"
    if kind == "debate":
        try:
            from app.modules.debating.access import debate_access
        except ImportError:
            return False, "debating module not installed"
        return debate_access(conn, actor, ident) != "none", "no access"
    return False, "unknown channel"


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    app = ws.app
    origin = ws.headers.get("origin")
    if origin:
        from urllib.parse import urlparse
        if urlparse(origin).netloc != ws.headers.get("host"):
            await ws.close(code=1008)      # another site's page may not listen in
            return
    await ws.accept()
    projector_token = ws.query_params.get("projector")
    db = app.state.db
    hub = app.state.hub
    cap = int(app.state.settings.get("max_live_students", 25))

    def who():
        with db.read() as conn:
            s = load_session(conn, ws.cookies.get(SESSION_COOKIE))
            return s.actor if s else None

    actor = await asyncio.to_thread(who)
    client = WSClient(ws)
    sender = asyncio.create_task(client.sender())
    subscribed: list[str] = []
    try:
        while True:
            msg = json.loads(await ws.receive_text())
            if "ping" in msg:
                if actor is not None and actor.kind == "student" and subscribed:
                    await asyncio.to_thread(_touch_participant, db, subscribed, actor.id)
                client.queue_message(json.dumps({"pong": msg["ping"], "t": time.time()}), [])
                continue
            if "subscribe" in msg:
                wanted = [c for c in msg.get("subscribe", []) if isinstance(c, str)][:MAX_CHANNELS]
                since = int(msg.get("since") or 0)
                ok, denied, replay, latest = await asyncio.to_thread(_subscribe_check, db, actor, wanted, projector_token, cap, since)
                for c in ok:
                    hub.subscribe(client, c)
                    subscribed.append(c)
                client.queue_message(json.dumps({"subscribed": ok, "denied": denied, "seq": latest}), [])
                for seq, chans in replay:
                    client.queue_message(json.dumps({"channels": chans, "seq": seq, "replay": True}), chans)
    except (WebSocketDisconnect, RuntimeError, ValueError):
        pass
    finally:
        hub.unsubscribe_all(client)
        sender.cancel()


def _subscribe_check(db, actor, wanted, projector_token, cap, since):
    ok, denied = [], []
    with db.read() as conn:
        for c in wanted:
            allowed, why = channel_allowed(conn, actor, c, projector_token, cap)
            (ok if allowed else denied).append(c if allowed else {"channel": c, "reason": why})
        latest = conn.execute("SELECT COALESCE(MAX(seq), 0) FROM event_log").fetchone()[0]
        replay = []
        if since and ok:
            # One message per missed change (action group), numbered like the live messages.
            marks = ",".join("?" * len(ok))
            q = ("SELECT g.action_group, (SELECT MAX(seq) FROM event_log x WHERE x.action_group = g.action_group) AS seq, "
                 f"GROUP_CONCAT(DISTINCT g.channel) AS chans FROM event_log g WHERE g.seq > ? AND g.channel IN ({marks}) "
                 "GROUP BY g.action_group ORDER BY seq")
            replay = [(r["seq"], r["chans"].split(",")) for r in rows(conn, q, [since, *ok])]
    return ok, denied, replay, latest


def _touch_participant(db, subscribed, student_id):
    from app.modules.chair.service import seen
    with db.read() as conn:
        for c in subscribed:
            if c.startswith("session:"):
                seen(conn, int(c.split(":")[1]), student_id)
        conn.commit()
