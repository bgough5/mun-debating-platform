# CLAUDE.md — working rules for this repo

Owner: Ben Gough, Public Speaking and Debating Coordinator, South Oakleigh College. This is a work project.

## Current state

- **Phase 0 is complete and the spec is approved (22 Oct 2026). Phase 1 onward may proceed.** Class size is 1–25 live students (D-022). The full build continues in a cloud session (D-024).
- Read first: `docs/spec.md` (what we're building), `docs/decisions.md` (what's decided and why), `docs/audit.md` (state of the old code).
- Rollback point: tag `pre-platform-baseline` (commit `67543a3`), the v2 whip-count game as left in July 2026.
- The existing v2 game (`shared/`, `server/`, `client/`, `src/`, `test/`) is **frozen**. Don't extend it. New work goes in `app/` per spec §7.3. `HANDOVER.md` is historical context; where it disagrees with `docs/decisions.md`, the decisions log wins.

## Non-negotiables

- **Privacy:** users are minors. No real student data in the repo, ever, and no secrets. Use the fake-data generator for all development. Collect only first names (plus last initial if needed). Enforce role-based access on the server.
- **Hosting:** no hosting decision beyond the laptop pilot without Ben's written approval and school sign-off.
- **AI:** AI-suggested country positions are always labelled as estimates with sources, or stored as unknown. Never present them as fact. Never write student work.
- **Measure, don't assert:** a claim that something works or is better needs the test or the number.
- **Report** outcome first, briefly. Flag uncertainty and anything not verified.

## Engineering

- One repo, modular; each module shippable alone. Tag each completed phase `phase-N-complete`.
- Prefer boring, well-supported tech (spec §7.2): Python 3.12, FastAPI, SQLite, Jinja2, htmx. No npm build.
- Update `README.md` and this file at the end of every session.
- Commit only when Ben asks.

## Running the frozen v2 game and its tests

- `start_server.bat`, or `python server/server.py` (pages on :8000, WebSocket on :8765). Students use the printed `http://<ip>:8000/client/player.html`. Opening the HTML file directly from disk breaks the WebSocket.
- `python -m unittest discover -s test` runs 37 tests. They passed on 22 Oct 2026, taking 51 s (about 3 s in July; cause not yet investigated).
- JS tests: open `test/*.test.html` in a browser. They are not automated.

## Gotchas

- The browser-testing tool can't execute pages opened via `file://`. Serve over local HTTP to test.
- Classic `<script>` top-level `const` and `let` share one scope across scripts: a second `const PACK` silently breaks pack loading.
- Never use `JSON.stringify` inside a double-quoted HTML attribute; it produced the July negotiation-channel bug.
