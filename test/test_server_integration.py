"""
End-to-end test: runs the real WhipCountServer on a loopback port and drives
it with real websocket client connections (teacher + players), exercising
the full lobby -> phase-advance -> event-relay flow over the wire.
"""

import asyncio
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import websockets  # noqa: E402
from websockets.asyncio.server import serve  # noqa: E402

from server import WhipCountServer  # noqa: E402


async def recv_json(ws, timeout=2):
    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
    return json.loads(raw)


async def recv_type(ws, expected_type, timeout=2):
    """Read messages until one of `expected_type` arrives, discarding any
    intermediate broadcasts (e.g. a `state` update from another player's
    join landing ahead of the message this call actually wants)."""
    return await recv_until(ws, lambda m: m["type"] == expected_type, timeout)


async def recv_until(ws, predicate, timeout=2):
    """Read messages until one satisfies `predicate`, discarding the rest.
    Needed because several `state` broadcasts of the same shape can be
    queued back-to-back (one per join, one per settings change, ...) and
    a bare type check can't tell them apart."""
    while True:
        msg = await recv_json(ws, timeout)
        if predicate(msg):
            return msg


async def send_json(ws, payload):
    await ws.send(json.dumps(payload))


class ServerIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.server = WhipCountServer()
        self._ws_server = await serve(self.server.handle, "localhost", 0)
        port = self._ws_server.sockets[0].getsockname()[1]
        self.url = f"ws://localhost:{port}"

    async def asyncTearDown(self):
        self._ws_server.close()
        await self._ws_server.wait_closed()

    async def test_full_lobby_flow_three_players(self):
        async with websockets.connect(self.url) as teacher, \
                   websockets.connect(self.url) as p1, \
                   websockets.connect(self.url) as p2, \
                   websockets.connect(self.url) as p3:

            await send_json(teacher, {"type": "create_room", "settings": {"playerCount": 3}})
            created = await recv_json(teacher)
            self.assertEqual(created["type"], "room_created")
            code = created["code"]
            self.assertEqual(len(code), 4)

            for ws, name in ((p1, "Alex"), (p2, "Bao"), (p3, "Casey")):
                await send_json(ws, {"type": "join_room", "code": code, "name": name})
                joined = await recv_json(ws)
                self.assertEqual(joined["type"], "joined")
                # teacher should see a state broadcast for each join (players
                # already in the room also get one, but we don't drain those
                # here — recv_type() below skips past any left sitting in
                # their queue)
                update = await recv_json(teacher)
                self.assertEqual(update["type"], "state")

            # teacher assigns countries and advances the phase
            await send_json(teacher, {
                "type": "assign_countries",
                "availableCountries": ["Fiji", "Chile", "Kenya", "Japan", "Egypt"],
            })
            all_assigned = lambda m: m["type"] == "state" and all(p["country"] for p in m["state"]["players"])  # noqa: E731
            state_msg = await recv_until(teacher, all_assigned)
            countries = {p["country"] for p in state_msg["state"]["players"]}
            self.assertEqual(len(countries), 3)

            for ws in (p1, p2, p3):
                update = await recv_until(ws, all_assigned)
                self.assertEqual(len({p["country"] for p in update["state"]["players"]}), 3)

            in_brief = lambda m: m["type"] == "state" and m["state"]["phase"] == "brief"  # noqa: E731
            await send_json(teacher, {"type": "advance_phase"})  # -> clause_pitch
            await send_json(teacher, {"type": "advance_phase"})  # -> brief
            state_msg = await recv_until(teacher, in_brief)
            self.assertEqual(state_msg["state"]["phase"], "brief")
            for ws in (p1, p2, p3):
                update = await recv_until(ws, in_brief)
                self.assertEqual(update["state"]["phase"], "brief")

            # a player sends a game event (e.g. a negotiation statement) —
            # server relays it verbatim to everyone in the room, including
            # the sender, without interpreting it
            await send_json(p1, {"type": "event", "kind": "negotiation_message", "payload": {"text": "The delegation of Fiji rises..."}})
            for ws in (teacher, p1, p2, p3):
                event_msg = await recv_type(ws, "event")
                self.assertEqual(event_msg["kind"], "negotiation_message")
                self.assertEqual(event_msg["payload"]["text"], "The delegation of Fiji rises...")

    async def test_non_teacher_cannot_advance_phase(self):
        async with websockets.connect(self.url) as teacher, websockets.connect(self.url) as p1:
            await send_json(teacher, {"type": "create_room", "settings": {"playerCount": 3}})
            created = await recv_json(teacher)
            code = created["code"]

            await send_json(p1, {"type": "join_room", "code": code, "name": "Alex"})
            await recv_json(p1)  # joined
            await recv_json(teacher)  # state update

            await send_json(p1, {"type": "advance_phase"})
            err = await recv_json(p1)
            self.assertEqual(err["type"], "error")
            self.assertIn("teacher", err["message"])

    async def test_even_roster_blocks_advance_past_lobby(self):
        async with websockets.connect(self.url) as teacher, \
                   websockets.connect(self.url) as p1, \
                   websockets.connect(self.url) as p2:
            await send_json(teacher, {"type": "create_room", "settings": {"playerCount": 5}})
            created = await recv_json(teacher)
            code = created["code"]

            for ws, name in ((p1, "Alex"), (p2, "Bao")):
                await send_json(ws, {"type": "join_room", "code": code, "name": name})
                await recv_json(ws)
                await recv_json(teacher)

            await send_json(teacher, {"type": "advance_phase"})
            err = await recv_json(teacher)
            self.assertEqual(err["type"], "error")
            self.assertIn("odd", err["message"])

    async def test_unknown_message_type_returns_error_not_crash(self):
        async with websockets.connect(self.url) as ws:
            await send_json(ws, {"type": "not_a_real_type"})
            err = await recv_json(ws)
            self.assertEqual(err["type"], "error")
            # connection should still be alive afterwards
            await send_json(ws, {"type": "create_room", "settings": {"playerCount": 3}})
            ok = await recv_json(ws)
            self.assertEqual(ok["type"], "room_created")

    async def test_channel_message_is_private_to_sender_recipient_and_teacher(self):
        async with websockets.connect(self.url) as teacher, \
                   websockets.connect(self.url) as p1, \
                   websockets.connect(self.url) as p2, \
                   websockets.connect(self.url) as p3:
            await send_json(teacher, {"type": "create_room", "settings": {"playerCount": 3}})
            code = (await recv_json(teacher))["code"]

            ids = {}
            for ws, name in ((p1, "Alex"), (p2, "Bao"), (p3, "Casey")):
                await send_json(ws, {"type": "join_room", "code": code, "name": name})
                ids[name] = (await recv_json(ws))["playerId"]
                await recv_json(teacher)

            await send_json(teacher, {"type": "assign_countries", "assignments": {
                ids["Alex"]: "Fiji", ids["Bao"]: "Chile", ids["Casey"]: "Kenya",
            }})
            all_assigned = lambda m: m["type"] == "state" and all(p["country"] for p in m["state"]["players"])  # noqa: E731
            for ws in (teacher, p1, p2, p3):
                await recv_until(ws, all_assigned)

            await send_json(p1, {"type": "channel_message", "to": "Chile", "text": "Backroom hello to Chile."})
            is_channel_msg = lambda m: m["type"] == "channel_message"  # noqa: E731

            sender_copy = await recv_until(p1, is_channel_msg)
            self.assertEqual(sender_copy["payload"]["text"], "Backroom hello to Chile.")
            recipient_copy = await recv_until(p2, is_channel_msg)
            self.assertEqual(recipient_copy["payload"]["text"], "Backroom hello to Chile.")
            teacher_copy = await recv_until(teacher, is_channel_msg)
            self.assertEqual(teacher_copy["payload"]["to"], "Chile")

            with self.assertRaises(asyncio.TimeoutError):
                await recv_json(p3, timeout=0.3)

    async def test_rejoin_replay_respects_channel_visibility(self):
        async with websockets.connect(self.url) as teacher:
            await send_json(teacher, {"type": "create_room", "settings": {"playerCount": 3}})
            code = (await recv_json(teacher))["code"]

            p1 = await websockets.connect(self.url)
            p2 = await websockets.connect(self.url)
            p3 = await websockets.connect(self.url)
            ids = {}
            for ws, name in ((p1, "Alex"), (p2, "Bao"), (p3, "Casey")):
                await send_json(ws, {"type": "join_room", "code": code, "name": name})
                ids[name] = (await recv_json(ws))["playerId"]
                await recv_json(teacher)

            await send_json(teacher, {"type": "assign_countries", "assignments": {
                ids["Alex"]: "Fiji", ids["Bao"]: "Chile", ids["Casey"]: "Kenya",
            }})
            all_assigned = lambda m: m["type"] == "state" and all(p["country"] for p in m["state"]["players"])  # noqa: E731
            for ws in (teacher, p1, p2, p3):
                await recv_until(ws, all_assigned)

            await send_json(p1, {"type": "channel_message", "to": "Chile", "text": "Private note for Chile."})
            is_channel_msg = lambda m: m["type"] == "channel_message"  # noqa: E731
            await recv_until(p1, is_channel_msg)
            await recv_until(p2, is_channel_msg)
            await recv_until(teacher, is_channel_msg)

            await p2.close()
            await recv_json(teacher)  # state: Bao disconnected
            await p3.close()
            await recv_json(teacher)  # state: Casey disconnected

            async with websockets.connect(self.url) as p2b:
                await send_json(p2b, {"type": "rejoin_room", "code": code, "playerId": ids["Bao"], "lastSeq": 0})
                rejoined = await recv_json(p2b)
                kinds = [e["kind"] for e in rejoined["missedEvents"]]
                self.assertIn("channel_message", kinds)

            async with websockets.connect(self.url) as p3b:
                await send_json(p3b, {"type": "rejoin_room", "code": code, "playerId": ids["Casey"], "lastSeq": 0})
                rejoined = await recv_json(p3b)
                kinds = [e["kind"] for e in rejoined["missedEvents"]]
                self.assertNotIn("channel_message", kinds)

    async def test_disconnect_marks_player_disconnected_and_rejoin_restores(self):
        async with websockets.connect(self.url) as teacher:
            await send_json(teacher, {"type": "create_room", "settings": {"playerCount": 3}})
            code = (await recv_json(teacher))["code"]

            p1 = await websockets.connect(self.url)
            await send_json(p1, {"type": "join_room", "code": code, "name": "Alex"})
            joined = await recv_json(p1)
            player_id = joined["playerId"]
            await recv_json(teacher)  # state update

            await p1.close()
            state_msg = await recv_json(teacher)
            self.assertEqual(state_msg["type"], "state")
            player_state = next(p for p in state_msg["state"]["players"] if p["id"] == player_id)
            self.assertFalse(player_state["connected"])

            async with websockets.connect(self.url) as p1b:
                await send_json(p1b, {"type": "rejoin_room", "code": code, "playerId": player_id, "lastSeq": 0})
                rejoined = await recv_json(p1b)
                self.assertEqual(rejoined["type"], "rejoined")
                self.assertTrue(any(p["id"] == player_id and p["connected"] for p in rejoined["state"]["players"]))


if __name__ == "__main__":
    unittest.main()
