# Whip Count — v2

Start here: **HANDOVER.md**

v2 is complete: multiplayer caucus rooms (3/5/7/9 players) with typed negotiation,
rubric marking, three-axis scoring (mandate fidelity / coalition / diplomacy), an
open clause-pitch mechanic, physically-rewritten amendments, and a distinct visual
identity with country flags — plus a standalone single-player build for prep/practice.

## Run multiplayer

`python server/server.py` — starts the WebSocket relay and serves `client/player.html`
and `client/teacher.html`. See `server/PROTOCOL.md` for the message contract.

## Single-player offline build

`src/WhipCount_v2_solo_built.html` — one self-contained file, no server, no network,
opens by double-click. Rebuild it after touching `shared/engine.js`, `shared/flags.js`,
`src/engine.v2.html`, or a pack with:

```
python build_solo.py
```

`src/WhipCount_v1_built.html` is the earlier single-player build, kept as a historical
fallback; it's no longer the one to hand students.

## Layout

- `HANDOVER.md` — full project brief, decisions, and build history. Read it first.
- `shared/` — the engine, rubric, scoring, and flags modules, loaded by every client.
- `server/` — the Python thin-relay WebSocket server (rooms/lobby/phase state only).
- `client/` — `player.html` and `teacher.html`, the multiplayer clients.
- `src/` — single-player dev source (`engine.v2.html`), topic packs, and built artifacts.
- `test/` — Python unit tests (`test/test_*.py`) and browser-run JS test pages (`test/*.test.html`).

## Platform work (from October 2026)

This repo is being evolved into a single debating and Model UN platform. **Phase 0 (audit and spec) is done and approved; the build is under way.** Nothing above has been changed.

- `docs/audit.md` — what the existing code does, what's solid, what fell short, with measurements.
- `docs/spec.md` — the platform spec: user stories, data model, architecture, privacy, roadmap.
- `docs/decisions.md` — decisions and assumptions, with reasons.
- `CLAUDE.md` — working rules for development sessions.

Rollback point: git tag `pre-platform-baseline`. The v2 game described above is frozen and stays runnable.
