# CLAUDE.md — working rules for this repo

Owner: Ben Gough, Public Speaking and Debating Coordinator, South Oakleigh College. This is a work project.

## Current state

- **Phases 1–6 are built (22 Oct 2026); Phase 7 (reliability and honesty), Phase 8 (committee flow v4, D-068 to D-072) and Phase 9 (debating and public speaking for the classroom, D-074 to D-077) and Phase 10 (personal sign-in codes, smooth pages, South Oakleigh restyle, D-078 to D-080), 27 Oct 2026,** on branch `platform-build`, draft PR #1 into `main` (Ben merges). Status tables in `docs/phase-reports.md`. The committee flow and its flow charts: `docs/design/mun-committee-flow.html`. Phase 6 (design system, icons, guided simulation, onboarding, content, robustness) is D-058 to D-063. Class size is 1–25 live students (D-022). Not done: the student pilot and everything in `docs/pilot-checklist.md` that needs Ben, staff or the school.
- Build progress and measured exit criteria: `docs/phase-reports.md`. Phase tags `phase-1-complete` to `phase-10-complete` are all on GitHub (`phase-7` and `phase-8` share commit `4e28a2b`).
- **All work happens in the local Claude Code session on Ben's laptop (decided 28 Oct 2026).** The cloud session that built Phases 1–10 is retired; everything it did is on GitHub. Don't start cloud sessions for this repo.
- **Feature freeze (D-082, 29 Oct 2026):** PR #1 is merged into `main` (tag `feature-freeze`). Fixes, hardening and simplification only, until real use shows a need. Work on a short branch from `main`, push, merge after tests pass. `platform-build` is history only.
- **Setup simplification (D-084, 29 Oct 2026):** stage 1 (one student list with year levels, People → Students; tournament tools hidden behind `show_tournaments`) and stage 2 (Start an activity, `/start`, `app/modules/core/start.py`) are on `main`. Stage 3 (Dashboard "In progress" with Resume → "Who's here today?", `app/modules/core/resume.py`) and saved groups (D-085: People → Groups, `app/modules/people/groups.py`; old classes shown as "Teacher access") are on `main`. Shared countries (D-086) are on `main`. Cue cards, autosave and debate team view (D-087) are on `main`. Rehearse from cards, team comments, prep overview by group and head-of-delegation voting (D-088) are on `main`. The live room (D-089: gavel, sounds, title cards, vote reveal, whip map, placards, breaking news), the real world map with alignments (D-090), and "Now speaking" and "Amendment adopted" (D-091) are on `main`. Effects only show procedure more clearly; Ben ruled out game mechanics (D-091). The board (D-092: the projector view in its own window, in a retro war-room look) is on `main`. The main deck is https://claude.ai/artifact/1B5XZqCFwEKEtRjnS25HKV, written as Ben's presentation to leadership. The stage-by-stage review deck is https://claude.ai/artifact/FX2JNSedk4DrE4g8VwBGyJ.
- **Since the board (4–5 Nov 2026), all on `main`:**
  - the board and flags (D-092, D-093);
  - country choice and "My country" (D-094, D-095);
  - scoring (D-096);
  - solo play and scenario packs (D-097);
  - six real-issue packs (D-098);
  - one front door for setup, a rebuilt demo, and single player on the board for students and guests (D-099);
  - the speech coach beside every speech box (D-100).

  The main deck was rewritten for leadership on 4 Nov ("From Engagement to the Classroom"); 22 slides since 5 Nov (the speech coach, and solo play on the board).
- Verified on Ben's laptop (Windows 10, 28 Oct 2026): `tools/windows_smoke.ps1 -Browser` passed: 620 engine and API tests, all 33 browser and axe tests, and start-up in 3.3 s. Not yet re-run on the laptop: the 90-minute soak (`python tools/loadtest.py --minutes 90`; memory now records on Windows, D-081).
- Local backups from the 28 Oct sync, safe to delete once Ben is happy: branch `backup/local-phase7-2026-10-23` and `stash@{0}` (superseded duplicates of Phase 7 items 1, 5–8).
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
- Debating (D-074): the classroom runner is `app/modules/debating/classroom.py` (run order computed by `steps()`, never stored; timer state on `class_run`; live channel `run:<id>`); the prep studio is `prep.py`. Typed names go through `clean_name`. Prep rubrics are found by code (`argument_written`, `rebuttal_written`), not kind. Likely arguments, impromptu topics and speech templates are seed data added by `seed_content_updates`; arguments are added only to motions that have none, so a teacher's edits stay. Timers, bells, keys and the practice flow are `app/static/js/speaking.js`.
- Sign-in (D-079): no phones at the College, so no QR codes and nothing that assumes one. Each student has a personal code (`student.login_code`, `app/modules/people/codes.py`: six characters, no 0/O/1/I); `/s/<code>` or typing it at `/join` signs them in and signs out any other laptop using that code. New students get a code from `assign_missing`. Codes are secrets: they are in `SECRET_COLUMNS`. Absent students never block a vote: a delegation with no active participant is voted by the engine (`cast_by = 'engine: away'`) and a student who arrives replaces that vote.
- Smoothness (D-078): `live.js` holds a live refresh while a text box inside the region has focus (flushed on `focusout`) and keeps the scroll position across swaps; `app.js` keeps the scroll position when a boosted form posts back to the same page and shows the flash as a toast. `tests/ui/test_phase10_smooth.py` checks both. Don't add `scrollTo` or `autofocus` that fights this.
- Design (D-080): South Oakleigh College look: white pages and cards, maroon `#621723` for actions and table heads, gold for accents, green for success, Cinzel headings and Open Sans body (vendored woff2 in `app/static/fonts/` with their OFL licences). Timer colours are bright go/warn/over with ink text.
- Setup (D-084): students are entered once and ticked per activity; `student.year_level` (5–12, optional) drives the suggested difficulty. Groups (`class`) only decide which teachers see whom; first-timers go into the "Students" group (`pool_class_id`). Activities from `/start` link students to slots by id (`_set_student_ids`), never by typed name, so they can mix groups. Saved groups (`student_group`, D-085) are many-to-many shortcuts for ticking and never grant visibility; the student tick list is `core/_pick_students.html`, and its buttons (add first-timers, tick a group, save as group) are handled by `groups.picker_op` on every page that shows it.
- Shared countries (D-086): any number of students per delegation, one vote per country. Anything a student does in MUN is shown as "Ben G, Australia" via `app/modules/mun/who.py` (`label`, `name_rows`; authors of motions, amendments and signatures come from the change log). New MUN displays of student actions must use it. Co-delegates can read each other's speech drafts (`floor.service.team_drafts`), never edit them. The country's vote is cast by the head of delegation, or by a present co-delegate when the head is away (`chair.service.may_cast`, D-088); predictions and friends and foes stay per student.
- Cue cards and teams (D-087): `app/modules/debating/cuecards.py` (build, fit_for_print, edited sets in `cue_card_set`) and `team.py` (a team is one side of a class debate; read-only). Forms that should save themselves get `data-autosave` and a `[data-autosave-status]`; their POST handler must answer 204 when `autosave=1`. Measure print layouts with print media: Playwright's `page.pdf` uses whatever media was last emulated, so call `emulate_media(media="print")` first (a measurement taken under screen media misled for an hour on 30 Oct).
- Live room (D-089): effects are driven by `[data-fx]` markers (`chair/_fx.html`) read by `app/static/js/effects.js`, never by the server pushing "play" commands, so a reconnect never replays a moment. Sounds are Web Audio (no audio files); every sound needs a caption. Overlays are projector-only (`data-fx-room="projector"`). New colours for it are tokens (`felt`, `wood`, `parchment`, `stamp`, `brass`). On the projector, `.projector h2/p` rules outrank single-class selectors: scope effect styles under `.fx-layer`.
- World map (D-090): `app/modules/mun/worldmap.py` + `worldmap.json` (built by `tools/build_worldmap.py` from Natural Earth; not hand-edited). Alliances for the map live in `alignment`, never in `bloc` (blocs feed the model and calibration). Token placement is cached per country set; keep anything on the live path cached like this.
- The board (D-092): `/projector/<token>` is a standalone page (`chair/board.html`, `board.css`, `board.js`), not on `base.html`. It reads `board.state()` as JSON on each change and animates the difference, so anything new it shows goes into `state()` first. It is a fixed 1920×1080 canvas scaled to fit: check layouts with Playwright at 1920×1080. Keep it retro: square corners and bevels, with only coins, seals and dials round. Rail cards are keyed (`data-key`) and animate only when new, so a refresh doesn't replay them. Tokens are counter-scaled on zoom in `placeTokens()`. Prefix board classes with `b-`: a plain `flash` class picked up the app's flash-message style. `.b-card p` outranks `.b-big`, so scope rail styles under `.b-card`. Flags (D-093): `tools/build_flags.py` turns flag-icons SVGs into what `safe_svg` allows; never round path data or transforms (it bent coats of arms). Board tokens are 52×36 placement boxes (`board.TOKEN`), passed to `worldmap.board(token=...)`; the committee and whip maps keep the 44×26 default.
- Scoring (D-096): Model UN contributions are counted on read in `app/modules/mun/points.py` (`RULES`, caps) from the session's records plus `mun_award` (the Chair's +1 to +3 with a reason); `tally()` runs once per change in the shared session view. A student sees only their own (`my_contrib`; `my_points` is the floor points they raised). Debating ballots are staff-only and house points are manual; don't bring back automatic awards.
- Packs (D-097): Model UN scenarios are JSON files in `app/db/seed/packs/` (rules: `docs/pack-authoring.md`; template `_template.json`; check with `python tools/validate_pack.py`). `packfile.install()` builds the committee; `veloria.json` is the Evatt demo. Students play any pack alone from Practice committee (`committee.solo_student_id`; keep solo committees out of staff lists with `cm.solo_student_id IS NULL`).
- Front door (D-099): every activity starts at `/start` (kinds `mun`, `debate`, `speeches`, `custom`; `unaa`/`evatt` still accepted). Library pages link to `/start?kind=…&pack=…` rather than having their own setup. Staff nav: Start, Model UN, Debating, People, Admin. Demo students come from one name list (no group tags).
- Single player (D-099): `/play` for everyone. A guest's game is never stored: it travels with each `/play/api` move (JSON, CSRF header) and is checked by `play.guest_game` against the scenario's shared `committee.guest_pack` committee. A signed-in student's game is a saved solo practice run (`/play/s/<id>`). Keep guest and solo committees out of staff lists. The game page is standalone (like the board): links and forms to it need `hx-boost="false"`.
- Speech coach (D-100): `coach_layout` in `_coach.html` wraps any speech form; mark each box `data-coach-text` (read-only text: `class="coach-read" data-coach-text`). Patterns and phrases live in `app/web/coach.py` and must read the same in Python `re` and JS `RegExp` (`tests/api/test_coach.py`). The marks are a copy behind a transparent textarea (`coach-back`); never change the student's text to show them. It counts in the browser and stores nothing on the server; Listen uses `localService` voices only.
- Known flake: `tests/ui/test_start_ui.py::test_resume_from_the_dashboard` timed out in two full runs (4 Nov 2026) and passes alone; not yet investigated.
- Don't run two test suites at once on the laptop: the accessibility crawl timed out on page loads twice when another pytest run overlapped it, and passed (715/715) on a clean run (30 Oct 2026).
- `tools/screenshots.py` regenerates `docs/screens/` for design review; `tools/windows_smoke.ps1` is for Ben's laptop.

## Running the frozen v2 game and its tests

- `start_server.bat`, or `python server/server.py` (pages on :8000, WebSocket on :8765). Students use the printed `http://<ip>:8000/client/player.html`. Opening the HTML file directly from disk breaks the WebSocket.
- `python -m unittest discover -s test` runs 37 tests. They passed on 22 Oct 2026, taking 51 s (about 3 s in July; cause not yet investigated).
- JS tests: open `test/*.test.html` in a browser. They are not automated.

## Gotchas

- **Security (D-083, `docs/security-audit.md`):** CSV goes through `app.exports.csv_bytes` (it neutralises formulas); redirect targets from a form or Referer go through `app.web.safety.safe_path` / `safe_back`; stored markup is never `|safe`. Use `|safe_svg` for flags, and add an allowlisted filter for anything else. Ownership checks use account IDs (the change log), never display names, and take the committee from the record, never the form. Run `tests/security` after touching any of these.

- Jinja: don't pass a context key called `path` or a dict key called `items` (clash with the base template's `req_path` and `dict.items`).
- FastAPI routes match in order: a literal path like `/t/{name}/import` must not sit under a `/t/{name}/{key}` route.
- `<input>` without a `type` attribute misses the form CSS; always give one (axe flagged it as a target-size failure).
- Request handlers that touch the database are plain `def` (run in the thread pool), with forms read by `form=Depends(form_data)`. An `async def` handler doing SQLite work blocks every client (it caused 10 s stalls in the load test, D-042).
- Close pooled connections with `db.dispose()` before replacing or switching the database file, and validate a backup before disposing (D-057).
- Live regions (`data-live-channel`) are re-fetched on every change: include `<span hidden data-view-seq="{{ view_seq }}">` in a fragment so a stale render refreshes itself, and don't rely on a refresh keeping state beyond open `<details>` and changed `<select>`s (D-073).

- The browser-testing tool can't execute pages opened via `file://`. Serve over local HTTP to test.
- Classic `<script>` top-level `const` and `let` share one scope across scripts: a second `const PACK` silently breaks pack loading.
- Never use `JSON.stringify` inside a double-quoted HTML attribute; it produced the July negotiation-channel bug.
- A form with an `<input name="action">` shadows `form.action`; read the URL with `form.getAttribute("action")` (the runner's buttons 405'd until this was fixed).
- `hidden` doesn't beat a class that sets `display` (`.field`, `.card`); add a `[...][hidden] { display: none; }` rule for script-toggled elements.
