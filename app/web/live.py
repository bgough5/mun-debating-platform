"""In-process publish/subscribe for live updates over WebSocket.

A write commits, then publishes the channels it touched with the event-log
sequence number. Subscribed browsers get {channel, seq} and re-fetch the
fragments they show, so all rendering (and every access check) stays on the
server. Clients that reconnect send the last seq they saw and receive any
channel events they missed from the event log, so nothing is lost.
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
from collections import defaultdict


class Hub:
    def __init__(self):
        self.loop: asyncio.AbstractEventLoop | None = None
        self.subs: dict[str, set] = defaultdict(set)    # channel -> set of Client
        self.lock = threading.Lock()
        self.published = 0

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

    def subscribe(self, client, channel: str) -> None:
        with self.lock:
            self.subs[channel].add(client)

    def unsubscribe_all(self, client) -> None:
        with self.lock:
            for s in self.subs.values():
                s.discard(client)

    def count(self, channel: str) -> int:
        with self.lock:
            return len(self.subs.get(channel, ()))

    def publish(self, channels, seq: int) -> None:
        """Thread-safe; callable from request threads or the event loop."""
        if self.loop is None:
            return
        msg = {"channels": sorted(channels), "seq": seq, "t": time.time()}
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self.loop:
            self._dispatch(msg)
        else:
            try:
                self.loop.call_soon_threadsafe(self._dispatch, msg)
            except RuntimeError:
                pass   # loop closed during shutdown

    def _dispatch(self, msg: dict) -> None:
        self.published += 1
        with self.lock:
            targets = set()
            for ch in msg["channels"]:
                targets |= self.subs.get(ch, set())
        data = json.dumps(msg)
        for client in targets:
            client.queue_message(data, msg["channels"])
