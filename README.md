# South Oakleigh Debating & Model UN platform

One browser-based platform for South Oakleigh College's Model UN and debating work: evidence-based vote prediction,
the resolution workspace and chair tools, debating draws and ballots, and student pathways. It runs on the
coordinator's laptop over school Wi-Fi (D-002). Students join with a class code and tap their name; no installs.

**Status:** see `docs/phase-reports.md` for what is built and the measured exit criteria of each phase.

## Run it (Windows)

Double-click `start_platform.bat` (or run `.\start_platform.ps1`). The first run creates `.venv` and installs
`requirements.txt` (needs internet once). Then:

- Staff, on the laptop: `http://localhost:8080/` — the first visit asks you to set the coordinator passphrase.
- Students, on school Wi-Fi: the `/join` address printed in the window.
- Demo mode (fake data only, for training staff): `start_platform.bat --demo`, or Admin → Data.

Any OS: `python -m pip install -r requirements.txt` then `python -m app [--demo] [--port 8080]`.

Data lives in `data/` (gitignored): `real.db`, `demo.db`, `config.json` (passphrase hash, settings) and `backups/`.

## Tests

```
python -m pip install -r requirements-dev.txt
python -m playwright install chromium        # once, for the browser tests
python -m pytest                              # engine, API and browser (axe) tests
python -m pytest -m "not ui"                  # without the browser
node tools/parity/gen_fixture.js              # regenerate the parity fixture from the frozen v2 JS
python tools/check_exports.py                 # open every export in LibreOffice/poppler
```

## Layout

- `app/` — the platform (spec §7.3). `engine/` (prediction, rules, calibration; pure Python), `db/` (SQL migrations,
  CSV seeds), `modules/<name>/` (routes, services and templates per module: core, admin, people, mun, chair,
  debating, intelligence), `templates/` and `static/` (shared layout, CSS, vendored htmx — no CDN).
- `tests/` — pytest: `engine/`, `api/`, `ui/` (Playwright + axe). `tests/vendor/` holds axe-core for the tests.
- `tools/` — parity fixture generator, audit scripts, export checker.
- `docs/` — `spec.md`, `decisions.md` (wins over the spec), `audit.md`, `phase-reports.md`.

The v2 game below is frozen and still runnable; the platform links to it as "Practice game".

## Practice game: Whip Count v2 (frozen)

Historical brief: **HANDOVER.md**. Frozen since July 2026 (D-007); not extended.

v2 is complete: multiplayer caucus rooms (3/5/7/9 players) with typed negotiation,
rubric marking, three-axis scoring (mandate fidelity / coalition / diplomacy), an
open clause-pitch mechanic, physically-rewritten amendments, and a distinct visual
identity with country flags — plus a standalone single-player build for prep/practice.

### Run multiplayer

`python server/server.py` — starts the WebSocket relay and serves `client/player.html`
and `client/teacher.html`. See `server/PROTOCOL.md` for the message contract.

### Single-player offline build

`src/WhipCount_v2_solo_built.html` — one self-contained file, no server, no network,
opens by double-click. Rebuild it after touching `shared/engine.js`, `shared/flags.js`,
`src/engine.v2.html`, or a pack with:

```
python build_solo.py
```

`src/WhipCount_v1_built.html` is the earlier single-player build, kept as a historical
fallback; it's no longer the one to hand students.

### Layout (v2 files)

- `HANDOVER.md` — full project brief, decisions, and build history. Read it first.
- `shared/` — the engine, rubric, scoring, and flags modules, loaded by every client.
- `server/` — the Python thin-relay WebSocket server (rooms/lobby/phase state only).
- `client/` — `player.html` and `teacher.html`, the multiplayer clients.
- `src/` — single-player dev source (`engine.v2.html`), topic packs, and built artifacts.
- `test/` — Python unit tests (`test/test_*.py`) and browser-run JS test pages (`test/*.test.html`).

