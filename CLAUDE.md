# CLAUDE.md — working rules for this repo

Owner: Ben Gough, Public Speaking and Debating Coordinator, South Oakleigh College. This is a work project.

## Current state

- **Phases 1–6 are built (22 Oct 2026); Phase 7 (reliability and honesty) and Phase 8 (committee flow v4, D-068 to D-072, 27 Oct 2026)** on branch `platform-build`, draft PR #1 into `main` (Ben merges). Status tables in `docs/phase-reports.md`. The committee flow and its flow charts: `docs/design/mun-committee-flow.html`. Phase 6 (design system, icons, guided simulation, onboarding, content, robustness) is D-058 to D-063. Class size is 1–25 live students (D-022). Not done: the student pilot and everything in `docs/pilot-checklist.md` that needs Ben, staff or the school.
- Build progress and measured exit criteria: `docs/phase-reports.md`. Phase tags: `phase-N-complete` (created locally in the build; the cloud session couldn't push tags, so the PR lists the commits for Ben to tag).
- Guides: `docs/staff-guide.md`, `docs/privacy-summary.md` (for school sign-off), `docs/permissions.md` (generated), `docs/backup-restore.md`, `docs/pilot-checklist.md`.
- Read first: `docs/spec.md` (what we're building), `docs/decisions.md` (what's decided and why; D-025 onward are build-session decisions), `docs/audit.md` (state of the old code).
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

## Running the platform and its tests

- `start_platform.bat` (Windows) or `python -m app [--demo]`; serves on :8080. Data in `data/` (gitignored).
- `python -m pytest` runs engine, API and Playwright+axe browser tests; `-m "not ui"` skips the browser. Browser tests need `python -m playwright install chromium` once.
- Engine changes must keep `tests/engine/test_parity.py` green (fixture from `node tools/parity/gen_fixture.js`).
- New tables go in a new numbered file in `app/db/migrations/`; never edit an applied migration. Every data change goes through `app.db.Writer` so it is logged and undoable.
- Every new route needs a `require_*` dependency from `app/web/auth.py`, or an entry in `PUBLIC` in `app/web/route_audit.py` with a reason; `tests/api/test_permissions_matrix.py` enforces it. Re-run `python tools/permissions_report.py` after adding routes.
- Load test: `python tools/loadtest.py --minutes 90` (30 clients; results in `test-results/load/`, memory per sample in `rss.jsonl`, `summary.json` has the soak verdict). Run it from a frozen copy (`git archive HEAD`) if you will edit code meanwhile: the server renders templates from disk and lazily imports modules. Kill-and-restart loop: `tools/chaos_loop.sh 100`. Backup drill: `python tools/restore_drill.py`.
- AI: `app/ai/` provider interface; the offline `FakeProvider` is the default and the only one tested. Never enable a real provider without the school's approval recorded in Intelligence → AI settings.
- UN voting data import stays locked until a licence is confirmed in the app (D-051). Tests use `tests/fixtures/synthetic_un_votes.csv` only.
- Design: colours only as tokens in `app/web/design.py` and `:root` of `app.css`; `tests/test_design_contrast.py` checks AA and rejects raw colours. Icons only through `icon("concept")` (`app/web/icons.py`); add a concept there and rerun `tools/build_icons.py`.
- Every page's `<title>` must equal its `<h1>` and pages below a section need breadcrumbs (`tests/api/test_crawl.py`). Empty lists say what to do next (`empty_state` macro).
- The guided simulation's chair scripts are data (`procedure_stage`, Admin → Procedure stages). Whip counts are scored against actual votes, never the model (D-061).
- Committee flow v4 (D-068): six stages; the floor lives in `app/modules/floor/` (amendments, points, messages, speech drafts, friends and foes). The person running a committee is "the Chair". Messages travel on `inbox:<delegation>` and `chat:<session>` channels, not the session channel (keeps the floor from refreshing for every note). Drafts are private to sponsors until submitted (`amendment.submitted_at`): any new amendment query must filter on it. Student writing (speech drafts, friends and foes, messages) must be added to `erase_student` in `app/retention.py`.
- Demo content that invents positions uses source type `demo_unverified` and must say it isn't a real position (D-063).
- `tools/screenshots.py` regenerates `docs/screens/` for design review; `tools/windows_smoke.ps1` is for Ben's laptop.

## Running the frozen v2 game and its tests

- `start_server.bat`, or `python server/server.py` (pages on :8000, WebSocket on :8765). Students use the printed `http://<ip>:8000/client/player.html`. Opening the HTML file directly from disk breaks the WebSocket.
- `python -m unittest discover -s test` runs 37 tests. They passed on 22 Oct 2026, taking 51 s (about 3 s in July; cause not yet investigated).
- JS tests: open `test/*.test.html` in a browser. They are not automated.

## Gotchas

- Jinja: don't pass a context key called `path` or a dict key called `items` (clash with the base template's `req_path` and `dict.items`).
- FastAPI routes match in order: a literal path like `/t/{name}/import` must not sit under a `/t/{name}/{key}` route.
- `<input>` without a `type` attribute misses the form CSS; always give one (axe flagged it as a target-size failure).
- Request handlers that touch the database are plain `def` (run in the thread pool), with forms read by `form=Depends(form_data)`. An `async def` handler doing SQLite work blocks every client (it caused 10 s stalls in the load test, D-042).
- Close pooled connections with `db.dispose()` before replacing or switching the database file, and validate a backup before disposing (D-057).
- Live regions (`data-live-channel`) are re-fetched on every change: include `<span hidden data-view-seq="{{ view_seq }}">` in a fragment so a stale render refreshes itself, and don't rely on a refresh keeping state beyond open `<details>` and changed `<select>`s (D-073).

- The browser-testing tool can't execute pages opened via `file://`. Serve over local HTTP to test.
- Classic `<script>` top-level `const` and `let` share one scope across scripts: a second `const PACK` silently breaks pack loading.
- Never use `JSON.stringify` inside a double-quoted HTML attribute; it produced the July negotiation-channel bug.
