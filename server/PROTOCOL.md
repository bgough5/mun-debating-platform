# Whip Count server protocol

The server (`server.py`) is a thin relay: rooms, lobby, phase state, and an
opaque event log. It does not know what a `stanceOf` is — every game-logic
computation happens client-side in `shared/engine.js`, loaded by every
browser. See `HANDOVER.md` section 11a for why.

One WebSocket connection per browser tab. Messages are JSON objects with a
`type` field. The **first** message a connection sends decides its role for
the lifetime of that connection: `create_room` (teacher) or `join_room` /
`rejoin_room` (player).

## Client → server

| type | who | fields | effect |
|---|---|---|---|
| `create_room` | new connection | `settings` (partial, see below) | creates a room, this connection becomes its teacher |
| `join_room` | new connection | `code`, `name` | joins as a player if the room exists, is in `lobby` phase, and isn't full |
| `rejoin_room` | new connection | `code`, `playerId`, `lastSeq` | restores a dropped player connection; server replies with any events since `lastSeq` |
| `update_settings` | teacher | `settings` (partial) | allowed in `lobby` **or** `clause_pitch` only; merges into current settings — see note below on why `clause_pitch` is included |
| `assign_countries` | teacher | `assignments` (`{playerId: countryName}`) **or** `availableCountries` (string list, for random assignment) | assigns exactly one distinct country per current player |
| `advance_phase` | teacher | — | moves to the next phase in order; refuses to leave `lobby` with an even number of players |
| `goto_phase` | teacher | `phase` | jumps to any phase directly (redo a step, skip ahead) |
| `new_round` | teacher | — | same roster, phase back to `clause_pitch` (not `brief`), countries **and** `clauseId` cleared, round number incremented |
| `event` | teacher or player | `kind` (string), `payload` (object) | opaque **public** passthrough — whip guesses, votes, whatever needs to reach the whole room. Logged and broadcast verbatim, not interpreted. |
| `channel_message` | player | `to` (country name), `text` | **private** negotiation message. Routed only to the sender, whoever currently holds `to` (if anyone — a Full Assembly target may have no live player), and the teacher. Not broadcast to the rest of the room. |

`settings` keys (all optional, camelCase over the wire):
`playerCount` (3/5/7/9), `packId`, `clauseId` (`null` = random), `whipCountEnabled`,
`fullAssembly`, `wordLimitMin`, `wordLimitMax`, `negotiationSeconds`, `toneMode`
(`"standard"` or `"junior"`).

## Server → client

| type | when | fields |
|---|---|---|
| `room_created` | reply to `create_room` | `code`, `state` |
| `joined` | reply to `join_room` | `playerId`, `state` |
| `rejoined` | reply to `rejoin_room` | `playerId`, `state`, `missedEvents` (array of `event`-shaped entries) |
| `state` | broadcast to the whole room after any mutation | `state` (full room snapshot, see below) |
| `event` | broadcast to the whole room (including the sender) whenever anyone sends `event` | `seq`, `playerId`, `kind`, `payload`, `ts`, `roundNumber` |
| `channel_message` | routed to sender + recipient (+ teacher) only, whenever anyone sends `channel_message` | `seq`, `playerId`, `kind`, `payload: {to, text}`, `ts`, `roundNumber` |
| `error` | to the offending connection only | `message` |

`roundNumber` is stamped by the server at log time (`room.round_number` when
the event was logged), not supplied by the client — it's what lets a
rejoining player filter `missedEvents` down to the round in progress instead
of replaying a previous round's votes/messages/amendments on top of the
current one.

### Established `event` kinds (client-defined, server-agnostic)

| kind | who sends it | payload | purpose |
|---|---|---|---|
| `vote` | player | `{choice}` | Division-phase cast vote (-2..2) |
| `whip_lock` | player | `{guesses}` | records a locked-in whip count (mostly for the record — each client already computes its own reveal locally) |
| `amendment_sponsor` | player | `{amendmentId}` (`null` to withdraw) | sponsor an amendment; latest sponsorship per player replaces any earlier one |
| `amendment_second` | player | `{amendmentId, seconded}` | second (or withdraw a second from) an amendment someone else sponsored |
| `clause_sponsor` | player | `{clauseId}` (`null` to withdraw) | pitch a clause for the room to debate this round (HANDOVER.md 11a — "open pitch + second"); same exclusive-per-player, co-sponsorship-allowed rule as `amendment_sponsor` |
| `clause_second` | player | `{clauseId, seconded}` | second (or withdraw a second from) a clause someone else pitched |
| `round_score` | player | `{roundNumber, country, fidelity, coalition, diplomacy, total, profile}` | self-reported axis scores, sent once per round after a player's own Results screen computes them — lets the teacher dashboard build a scoreboard without re-deriving anyone else's private channel history |
| `fidelity_override` | teacher | `{targetPlayerId, points, note}` | the chair overriding a player's Mandate Fidelity score (HANDOVER.md 11a #3) — public so the target's own client can reflect it |

`state` snapshot shape (`room.to_dict()` in `rooms.py`):

```json
{
  "code": "ABCD",
  "phase": "lobby",
  "roundNumber": 1,
  "teacherConnected": true,
  "settings": { "playerCount": 5, "packId": "climate2026", "...": "..." },
  "players": [
    { "id": "a1b2c3d4", "name": "Alex", "country": null, "connected": true }
  ]
}
```

## Design notes for whoever builds the client next

- A player's identity is the server-generated `playerId` from the `joined`
  reply. The client must persist it (e.g. `sessionStorage`) to `rejoin_room`
  after a dropped connection — the server keeps the player's slot and
  history, it doesn't evict on disconnect.
- The server enforces the odd-player-count rule at `advance_phase`/`goto_phase`
  time against the *actual* roster, not just the lobby's `playerCount`
  setting — don't rely on the client to re-check this.
- `event` is intentionally schema-less on the server side. Whip-count
  guesses and votes go through this one public passthrough with a `kind`
  string the client itself defines and interprets. Keep new event kinds
  documented here as they're introduced in later build steps.
- Negotiation is private by design: students backroom-negotiate 1:1 with
  another delegation via `channel_message`, and only the two parties (plus
  the teacher) ever see it — this is deliberate, not a passthrough
  oversight. Loud floor statements happen out loud in the physical room and
  don't need a digital channel; what's worth capturing and marking is the
  private bilateral negotiation. The teacher's view is meant to be the only
  place the *combined* feed across every channel is visible.
- Phase order is `lobby → clause_pitch → brief → whip → negotiation →
  amendment → division → results`. `clause_pitch` exists because which
  clause gets debated is a player-driven open pitch/second (HANDOVER.md
  11a), not something the teacher sets unilaterally — see `clause_sponsor`/
  `clause_second`. The server resolves nothing itself (thin relay, as
  always): every client independently computes the same winner via
  `Engine.resolveClausePitch`, and the **teacher's** client is the one that
  calls `update_settings({clauseId: ...})` to lock in the result before
  calling `advance_phase` into `brief` — which is exactly why
  `update_settings` had to be allowed during `clause_pitch`, not just
  `lobby`. If nobody pitches a clause, `resolveClausePitch` returns `null`;
  the teacher's client should fall back to picking one at random rather
  than advancing with no clause set.
