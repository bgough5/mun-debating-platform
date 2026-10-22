# South Oakleigh Debating & Model UN platform

One browser-based platform for South Oakleigh College's Model UN and debating work: evidence-based vote prediction,
the resolution workspace and chair tools, debating draws and ballots, and student pathways. It runs on the
coordinator's laptop over school Wi-Fi (D-002). Students join with a class code and tap their name; no installs.

**Status:** Phases 1–5 built (except the student pilot, which needs Ben, staff and the school). See
`docs/phase-reports.md` for what is built and the measured exit criteria of each phase, and
`docs/pilot-checklist.md` for what must happen before any class uses it.

## What's in it

- **Model UN:** conferences, committees, delegations; a resolution workspace (one editor per paragraph, amendments,
  version history, undo); evidence-based vote prediction (Monte Carlo pass probability, swing countries, amendment
  comparison, lobbying tasks); calibration against real votes.
- **Class mode:** class code + name join; live sessions with speakers list, timers, motions, divisions (GA and
  Security Council rules, vetoes), minutes and a projector view; live updates over one WebSocket; 1–25 students,
  with countries that have no student voted by the engine and labelled "computed".
- **Debating:** events, houses, teams, rooms, adjudicators; seeded draws (random, then power-paired); rubric
  ballots and panels; ladders and speaker tabs; house points with reversals; run sheets and MC scripts; projector
  view; class practice for any number of students (solo speech practice up to full rooms); a 325-student carnival
  generator for rehearsal.
- **People:** classes, staff, student pathways and milestones.
- **Intelligence:** licence-gated UN voting-history import (locked: licences not confirmed, D-051), voting-history
  priors, backtests against baselines, and AI features behind a provider interface that is offline by default (D-053).
- **Hardening:** permissions audit, backups and restore, retention purge and student erasure, accessibility checks.

Guides: `docs/staff-guide.md` (for teachers), `docs/privacy-summary.md` (for school sign-off),
`docs/permissions.md`, `docs/backup-restore.md`, `docs/pilot-checklist.md`.

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
python tools/loadtest.py --minutes 45         # Phase 2 load test: 30 clients, writes test-results/load/
python tools/permissions_report.py            # rewrite docs/permissions.md from the code
python tools/restore_drill.py                 # backup and restore into a separate app process
```

## Layout

- `app/` — the platform (spec §7.3). `engine/` (prediction, rules, calibration; pure Python), `db/` (SQL migrations,
  CSV seeds), `modules/<name>/` (routes, services and templates per module: core, admin, people, mun, chair,
  debating, intelligence), `templates/` and `static/` (shared layout, CSS, vendored htmx — no CDN).
- `tests/` — pytest: `engine/`, `api/`, `ui/` (Playwright + axe). `tests/vendor/` holds axe-core for the tests.
- `tools/` — parity fixture generator, audit scripts, export checker, load test, permissions report, restore drill,
  synthetic UN-vote generator.
- `docs/` — `spec.md`, `decisions.md` (wins over the spec), `audit.md`, `phase-reports.md`, and the guides above.

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

