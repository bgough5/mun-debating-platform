"""
Whip Count multiplayer server — thin relay.

Manages rooms, lobbies, and phase transitions (server/rooms.py). Deliberately
knows nothing about the game itself: no stanceOf, no scoring, no rubric
marking. That logic lives once, in shared/engine.js, loaded by every
browser client. This process just keeps players in sync — who's in the
room, what phase we're in, and an ordered log of game-event payloads
(whip guesses, votes, private negotiation messages, ...) that it relays
without interpreting. Public events (`event`) broadcast to the whole
room; private ones (`channel_message`) route only to the two delegations
in that channel plus the teacher, who always sees every channel.

See PROTOCOL.md for the message contract clients build against.

Run:  python server.py [--port 8765]
Requires:  pip install websockets
"""

from __future__ import annotations

import argparse
import asyncio
import functools
import json
import logging
import os
import posixpath
import re
import socket
import threading
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import websockets
from websockets.asyncio.server import ServerConnection, serve

from rooms import Phase, Room, RoomError, RoomRegistry, RoomSettings

log = logging.getLogger("whipcount.server")

# camelCase settings keys (as sent over the wire) -> RoomSettings field names
_SETTINGS_KEY_MAP = {
    "playerCount": "player_count",
    "packId": "pack_id",
    "clauseId": "clause_id",
    "whipCountEnabled": "whip_count_enabled",
    "fullAssembly": "full_assembly",
    "wordLimitMin": "word_limit_min",
    "wordLimitMax": "word_limit_max",
    "negotiationSeconds": "negotiation_seconds",
    "toneMode": "tone_mode",
}


class ConnectionState:
    """Per-websocket bookkeeping: which room this socket belongs to, and
    whether it's the teacher or a named player."""

    def __init__(self, ws: ServerConnection):
        self.ws = ws
        self.room: Room | None = None
        self.player_id: str | None = None  # None + room set => this is the teacher
        self.last_seq = 0

    @property
    def is_teacher(self) -> bool:
        return self.room is not None and self.player_id is None


class WhipCountServer:
    def __init__(self):
        self.registry = RoomRegistry()
        self.connections: dict[ServerConnection, ConnectionState] = {}
        # room code -> set of websockets currently in that room
        self.room_sockets: dict[str, set[ServerConnection]] = {}

    async def handle(self, ws: ServerConnection) -> None:
        state = ConnectionState(ws)
        self.connections[ws] = state
        try:
            async for raw in ws:
                await self._dispatch(state, raw)
        except websockets.ConnectionClosed:
            pass
        finally:
            await self._on_disconnect(state)
            del self.connections[ws]

    async def _dispatch(self, state: ConnectionState, raw: str) -> None:
        try:
            msg = json.loads(raw)
            if not isinstance(msg, dict) or "type" not in msg:
                raise RoomError("message must be a JSON object with a 'type' field")
            msg_type = msg["type"]
            handler = self._HANDLERS.get(msg_type)
            if handler is None:
                raise RoomError(f"unknown message type: {msg_type!r}")
            await handler(self, state, msg)
        except RoomError as e:
            await self._send(state.ws, {"type": "error", "message": str(e)})
        except (json.JSONDecodeError, TypeError):
            await self._send(state.ws, {"type": "error", "message": "malformed message"})
        except Exception as e:  # noqa: BLE001 - never let one bad message kill the connection
            log.exception("unhandled error dispatching message")
            await self._send(state.ws, {"type": "error", "message": f"internal error: {e}"})

    # ---- message handlers ----

    async def _create_room(self, state: ConnectionState, msg: dict) -> None:
        if state.room is not None:
            raise RoomError("this connection has already joined a room")
        settings = self._settings_from_wire(msg.get("settings", {}))
        room = self.registry.create_room(settings)
        room.teacher_connected = True
        state.room = room
        state.player_id = None
        self.room_sockets[room.code] = {state.ws}
        await self._send(state.ws, {"type": "room_created", "code": room.code, "state": room.to_dict()})

    async def _join_room(self, state: ConnectionState, msg: dict) -> None:
        if state.room is not None:
            raise RoomError("this connection has already joined a room")
        code = msg.get("code", "")
        name = (msg.get("name") or "").strip()
        if not name:
            raise RoomError("name is required to join a room")
        room = self.registry.get(code)
        if room is None:
            raise RoomError(f"no room with code {code!r}")
        player = room.add_player(name)
        state.room = room
        state.player_id = player.id
        self.room_sockets.setdefault(room.code, set()).add(state.ws)
        await self._send(state.ws, {"type": "joined", "playerId": player.id, "state": room.to_dict()})
        await self._broadcast_state(room, exclude={state.ws})

    async def _rejoin_room(self, state: ConnectionState, msg: dict) -> None:
        code = msg.get("code", "")
        player_id = msg.get("playerId", "")
        room = self.registry.get(code)
        if room is None:
            raise RoomError(f"no room with code {code!r}")
        if player_id not in room.players:
            raise RoomError("no such player in this room")
        room.set_player_connected(player_id, True)
        state.room = room
        state.player_id = player_id
        self.room_sockets.setdefault(room.code, set()).add(state.ws)
        missed = [e.to_dict() for e in room.events_since(msg.get("lastSeq", 0), viewer_player_id=player_id)]
        await self._send(state.ws, {"type": "rejoined", "playerId": player_id, "state": room.to_dict(), "missedEvents": missed})
        await self._broadcast_state(room, exclude={state.ws})

    async def _update_settings(self, state: ConnectionState, msg: dict) -> None:
        room = self._require_teacher(state)
        room.update_settings(**self._settings_from_wire(msg.get("settings", {}), as_kwargs=True))
        await self._broadcast_state(room)

    async def _assign_countries(self, state: ConnectionState, msg: dict) -> None:
        room = self._require_teacher(state)
        assignments = msg.get("assignments")
        if assignments:
            room.assign_countries(assignments)
        else:
            room.random_assign_countries(msg.get("availableCountries", []))
        await self._broadcast_state(room)

    async def _advance_phase(self, state: ConnectionState, msg: dict) -> None:
        room = self._require_teacher(state)
        room.advance_phase()
        await self._broadcast_state(room)

    async def _goto_phase(self, state: ConnectionState, msg: dict) -> None:
        room = self._require_teacher(state)
        try:
            phase = Phase(msg.get("phase"))
        except ValueError as e:
            raise RoomError(f"not a valid phase: {msg.get('phase')!r}") from e
        room.goto_phase(phase)
        await self._broadcast_state(room)

    async def _new_round(self, state: ConnectionState, msg: dict) -> None:
        room = self._require_teacher(state)
        room.new_round()
        await self._broadcast_state(room)

    async def _event(self, state: ConnectionState, msg: dict) -> None:
        """Opaque game-event passthrough: whip guesses, negotiation
        messages, votes, etc. The server does not interpret payload —
        every client's shared/engine.js does that locally."""
        room = state.room
        if room is None:
            raise RoomError("join a room before sending events")
        kind = msg.get("kind")
        if not kind:
            raise RoomError("event requires a 'kind'")
        entry = room.log_event(state.player_id, kind, msg.get("payload", {}))
        await self._broadcast(room, {"type": "event", **entry.to_dict()})

    async def _channel_message(self, state: ConnectionState, msg: dict) -> None:
        """Private delegation-to-delegation negotiation (the 'backroom').
        Visible only to the sender, whoever holds the target country (if
        anyone — a Full Assembly target may have no live player), and the
        teacher, who always sees every channel. Public game events (votes,
        whip guesses) stay on the broadcast-to-everyone `event` path above;
        this one is deliberately routed, not broadcast."""
        room = state.room
        if room is None or state.player_id is None:
            raise RoomError("only a joined player can send a channel message")
        sender = room.players.get(state.player_id)
        if sender is None or not sender.country:
            raise RoomError("you need an assigned country before negotiating")
        to_country = msg.get("to")
        text = msg.get("text")
        if not to_country or not text:
            raise RoomError("channel_message requires 'to' and 'text'")
        if to_country == sender.country:
            raise RoomError("cannot open a channel with your own delegation")

        target = next((p for p in room.players.values() if p.country == to_country), None)
        visible_to = {state.player_id}
        if target is not None:
            visible_to.add(target.id)
        entry = room.log_event(state.player_id, "channel_message", {"to": to_country, "text": text}, visible_to=visible_to)
        await self._broadcast_visible(room, {"type": "channel_message", **entry.to_dict()}, visible_to)

    _HANDLERS = {
        "create_room": _create_room,
        "join_room": _join_room,
        "rejoin_room": _rejoin_room,
        "update_settings": _update_settings,
        "assign_countries": _assign_countries,
        "advance_phase": _advance_phase,
        "goto_phase": _goto_phase,
        "new_round": _new_round,
        "event": _event,
        "channel_message": _channel_message,
    }

    # ---- disconnect handling ----

    async def _on_disconnect(self, state: ConnectionState) -> None:
        room = state.room
        if room is None:
            return
        sockets = self.room_sockets.get(room.code)
        if sockets:
            sockets.discard(state.ws)
        if state.is_teacher:
            room.teacher_connected = False
        elif state.player_id:
            room.set_player_connected(state.player_id, False)
        else:
            return
        await self._broadcast_state(room)

    # ---- helpers ----

    def _require_teacher(self, state: ConnectionState) -> Room:
        if not state.is_teacher or state.room is None:
            raise RoomError("only the teacher connection can do this")
        return state.room

    @staticmethod
    def _settings_from_wire(wire: dict, as_kwargs: bool = False) -> dict | RoomSettings:
        kwargs = {}
        for wire_key, field_name in _SETTINGS_KEY_MAP.items():
            if wire_key in wire:
                kwargs[field_name] = wire[wire_key]
        return kwargs if as_kwargs else RoomSettings(**kwargs)

    async def _send(self, ws: ServerConnection, payload: dict) -> None:
        try:
            await ws.send(json.dumps(payload))
        except websockets.ConnectionClosed:
            pass

    async def _broadcast(self, room: Room, payload: dict, exclude: set[ServerConnection] | None = None) -> None:
        exclude = exclude or set()
        sockets = self.room_sockets.get(room.code, set())
        data = json.dumps(payload)
        for ws in list(sockets):
            if ws in exclude:
                continue
            try:
                await ws.send(data)
            except websockets.ConnectionClosed:
                sockets.discard(ws)

    async def _broadcast_state(self, room: Room, exclude: set[ServerConnection] | None = None) -> None:
        await self._broadcast(room, {"type": "state", "state": room.to_dict()}, exclude)

    async def _broadcast_visible(self, room: Room, payload: dict, visible_to: set[str]) -> None:
        """Like _broadcast, but only to sockets whose connection is the
        teacher (always sees everything) or one of the players in visible_to."""
        sockets = self.room_sockets.get(room.code, set())
        data = json.dumps(payload)
        for ws in list(sockets):
            conn = self.connections.get(ws)
            if conn is None:
                continue
            if conn.is_teacher or conn.player_id in visible_to:
                try:
                    await ws.send(data)
                except websockets.ConnectionClosed:
                    sockets.discard(ws)


def _lan_ip() -> str:
    """Best-effort guess at this machine's LAN address, so the printed join
    URL is something a student can actually type rather than 0.0.0.0."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # no packet actually sent, just picks a route
        return s.getsockname()[0]
    except OSError:
        return "localhost"
    finally:
        s.close()


_PUBLIC_EXACT_PATHS = {"/client/player.html", "/client/teacher.html"}
_PUBLIC_PREFIXES = ("/shared/", "/assets/")
_PACK_FILE_RE = re.compile(r"^/src/pack_[A-Za-z0-9_-]+\.js$")


def _is_public_path(raw_path: str) -> bool:
    """Whitelist of the only files the static server will hand out.

    Despite this module's original intent (see the class docstring below),
    passing directory=<project root> to SimpleHTTPRequestHandler served the
    ENTIRE project tree over HTTP — HANDOVER.md, server/*.py, test/*, the
    whole repo — to anyone on the school network who guessed or browsed to
    a path, including a bare directory listing at "/". Any browser or curl
    on the same Wi-Fi as the teacher's laptop could read it, not just the
    intended client/ pages. This checks the request path against exactly
    what client/player.html and client/teacher.html actually reference
    (shared/*.js, assets/soc_logo.png, src/pack_*.js) and rejects everything
    else with 404 — including directory listings, which have no entry here
    and so are always rejected.
    """
    path = urllib.parse.unquote(raw_path.split("?", 1)[0].split("#", 1)[0])
    path = posixpath.normpath(path)
    if not path.startswith("/"):
        path = "/" + path
    if path in _PUBLIC_EXACT_PATHS:
        return True
    if path.startswith(_PUBLIC_PREFIXES) and "." in path.rsplit("/", 1)[-1]:
        return True
    return bool(_PACK_FILE_RE.match(path))


class _NoCacheRequestHandler(SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler sends no cache-control headers at all, which
    leaves browsers free to cache shared/engine.js, shared/rubric.js, the
    pack files, etc. as aggressively as they like. That's a real classroom
    hazard, not just a dev annoyance: if the teacher updates the pack or
    engine between lessons, a student's browser could silently keep running
    the OLD logic from a cached copy with no visible sign anything is wrong.
    This is a low-traffic school-LAN tool serving tiny files, so there's no
    real performance cost to simply disabling caching outright."""

    def send_head(self):
        if not _is_public_path(self.path):
            self.send_error(404, "Not Found")
            return None
        return super().send_head()

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def _start_static_server(root: str, host: str, port: int) -> ThreadingHTTPServer:
    """Serves client/, shared/, and src/ (the pack files) as plain static
    files — one command, one process, matching the 'teacher runs one
    command' promise in HANDOVER.md section 5. The game logic itself is
    still only ever reached over the websocket relay above; this just
    hands out the HTML/JS/pack assets that load it."""
    handler = functools.partial(_NoCacheRequestHandler, directory=root)
    httpd = ThreadingHTTPServer((host, port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


async def main() -> None:
    parser = argparse.ArgumentParser(description="Whip Count multiplayer relay server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765, help="WebSocket relay port")
    parser.add_argument("--http-port", type=int, default=8000, help="static file server port")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _start_static_server(project_root, args.host, args.http_port)

    display_host = _lan_ip() if args.host in ("0.0.0.0", "::") else args.host
    log.info("Player client: http://%s:%d/client/player.html", display_host, args.http_port)
    log.info("Teacher dashboard: http://%s:%d/client/teacher.html", display_host, args.http_port)

    server = WhipCountServer()
    async with serve(server.handle, args.host, args.port) as ws_server:
        log.info("WebSocket relay listening on ws://%s:%d", args.host, args.port)
        await ws_server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
