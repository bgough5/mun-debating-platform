# Phase reports — measured exit criteria

Each phase ends with a tag `phase-N-complete`. Numbers here were measured in the cloud build container (Linux, Python 3.12.3, Chromium 141 headless), not on Ben's laptop, unless stated. "Not verified" means exactly that.

## Phase 1 — Coordinator spine (tag `phase-1-complete`)

| Exit criterion (spec §10) | Result | How measured |
|---|---|---|
| All §5.8 tests pass | **Pass** | `pytest tests/engine` (parity, rules, determinism, ties, calibration maths, unknown handling, simulation accuracy) |
| Parity fixture 100% | **279/279 cells, 54/54 amendment cases; 300/300 sponsorship sequences** | `tests/engine/test_parity.py` against `tests/fixtures/stance_parity.json`, generated from the frozen JS by `node tools/parity/gen_fixture.js`. Raw scores match bit for bit. |
| Simulation accuracy | **Pass**: within 3 Monte Carlo SE of the exact answer for GA majority (31 countries, 20,000 runs), two-thirds and SC rules (15 countries) | `test_simulate.py` (exact answer by dynamic programming) |
| Calibration maths | **Pass**: Brier, log loss, reliability bins and Wilson interval against hand-computed values; calibrated synthetic data not flagged, over- and under-confident data flagged | `test_calibration.py`; error rates in D-033 |
| W-1 completed end-to-end by Ben in demo mode | **Automated stand-in passes; Ben's own run not done** | `tests/api/test_w1_workflow.py` (all six W-1 acceptance steps through the HTTP API) and `tests/ui/test_phase1_ui.py::test_w1_in_browser` (clicked through in Chromium). Ben still needs to do it himself. |
| axe: 0 serious | **0 serious or critical on all 33 Phase 1 pages** (30 signed-in, 3 anonymous) | `tests/ui/test_phase1_ui.py` with axe-core 4.10.2, WCAG 2.0/2.1/2.2 A and AA tags. Results in `test-results/axe/` |
| Every export opens in Word, Excel and a PDF viewer | **Opens in LibreOffice Writer/Calc and poppler; Word and Excel themselves not verified** | `python tools/check_exports.py`: resolution .docx → LibreOffice converts it; 3 CSVs (UTF-8 with BOM) → LibreOffice converts to .xlsx; browser print-to-PDF → `pdfinfo` reads 1 page, `pdftotext` 2,050 characters |

Other Phase 1 numbers:
- Test suite: 376 tests, all passing, 48 s (engine and API tests ~20 s; browser tests the rest).
- Prediction for the 31-delegation GA with swing analysis: 0.16 s per page view (4,000 runs).
- Keyboard: the skip link is the first Tab stop and moves focus to main; sign-in works with the keyboard alone (tested). Pages have no horizontal scroll at 320 px width (tested on three key pages).
- **Not verified:** NVDA screen-reader pass (needs Windows + NVDA; must be done by a person), 200% zoom (only 320 px width was tested, which is the stricter reflow case), Microsoft Word/Excel.

Audit figures re-checked with `node tools/audit/engine_audit.js` (output in `tools/audit/engine_audit_output.json`): 279 cells, 263 computed, 83 abstain, Germany = Spain, 2 pass/fail flips in 54 amendment cases, 51 of 96 override cases changed, rubric 30/30 for the keyword salad and 15/30 for the real offer. The audit's "62 of 263 within ±0.10 of a bucket boundary" is explained and corrected in `docs/audit.md` §7: 55 strictly within, 78 including exact ties, and 62 with the original no-tolerance `<= 0.10` test, where floating-point rounding splits the 23 exact ties.

## Phase 2 — Class mode (tag `phase-2-complete`)

| Exit criterion (spec §10) | Result | How measured |
|---|---|---|
| 30 simulated clients for 45 min: no lost events | **Pass: 0 lost** of 2,888 changes × 30 clients; 0 WebSocket reconnects; 0 server errors | `python tools/loadtest.py --minutes 45` (25 students joined by code + name and voting, 1 chair acting every ~2 s, 1 projector, 3 staff). Every change on the session channel was checked against every client's received list. `test-results/load/summary.json` |
| p95 update latency under 1 s on the laptop | **0.83 s in the cloud build container; not measured on the laptop.** p50 0.25 s, p99 1.19 s, max 1.82 s (72,225 updates) | Latency = from the start of the action to the moment each client has the re-rendered fragment (WebSocket notice + HTTP fetch). Run it on the laptop: pilot checklist D2 |
| Chair browser killed mid-session recovers to the same state | **Pass** | `tests/ui/test_phase2_ui.py::test_chair_browser_killed_recovers_same_state`: the chair's browser context is closed mid-session with speakers and a running timer; a new browser opens the console and shows the same current speaker, the same queue and the timer still running. (Students' pages hold their own connections and aren't affected by the chair's browser.) |
| Staff dry-run done | **Not done** (needs staff; pilot checklist E1) | |

**Honest notes on the 45-minute run**
- p95 drifted upward across the run: by 5-minute window, 0.76, 0.81, 0.79, 0.80, 0.80, 0.80, 0.86, 0.89, 0.97 s. The server's own request timings (from its timing log) were flat at p95 0.45–0.54 s for the first 35 minutes, then 0.75 s in the last window; database writes stayed at 3 ms median throughout. Each fragment costs ~5 ms on its own at the start and at the end of the run, so the extra time is queueing when 30 clients re-fetch at once after every change. The cause of the last-window rise was not established. A longer class (90 min) was not tested.
- 12 client fetches (of ~75,000) hit a keep-alive connection the server had just closed and were retried once by the test client (counted, not hidden). Browsers retry these automatically.
- Server memory grew from 97 MB to 127 MB over 45 minutes. Not investigated further.
- The test clients and the server ran on the same machine, so the clients' own CPU use is included in the latencies. Ben's laptop may be faster or slower: run the test there.
- An earlier version of the test had a client-side lookup that slowed as the run went on (fixed: it now uses bisect); a first 45-minute run was lost to a container restart.

**Other Phase 2 checks (tests)**
- Small groups: 1 student (`test_solo_student_substantive_vote`), 2–3 students (`test_small_groups_procedural_vote`: procedural thresholds scale, computed delegations don't vote on procedure, D-040); the 25-student cap (`test_25_student_cap`: the 26th is refused, a returning student is let back in).
- Computed delegations in a division are labelled and excluded from calibration (`test_division_with_computed_delegations_records_calibration`); the Security Council veto live (`test_security_council_veto_live`).
- One editor per paragraph and lock expiry (`test_one_editor_per_paragraph`, `test_lock_lapses_without_heartbeat`); WebSocket channel access per role (`test_websocket_access_and_live_message`).
- axe: 0 serious or critical on all Phase 2 pages (chair console, student live page, projector, minutes).

## Phase 3 — Debating (tag `phase-3-complete`)

| Exit criterion (spec §10) | Result | How measured |
|---|---|---|
| Draw tests: no repeat pairings where avoidable, side balance, determinism | **Pass** | `tests/engine/test_draw.py` (12 tests). Over 100 simulated 16-team events of 4 rounds: 0 repeat pairings; 97.5% of teams within one of an even aff/neg split, none worse than two. 108 teams × 4 rounds: 99.98% exactly 2 aff / 2 neg. Same seed → identical draw. Byes rotate; same-house debates avoided in carnivals; any rule the draw had to break is shown on it (D-045). |
| Ladder maths tests | **Pass** | `test_round_ballot_validation_and_ladder`, `test_panel_majority_and_chair_casting` (2–1 panel; 1–1 goes to the chair), `test_house_points_reversible_and_attributed`, `test_corrected_ballot_moves_win_points`; the carnival test checks house totals equal the sum of entries exactly |
| A 325-student carnival generated from fake data runs end to end | **Pass: 325 students, 108 teams, 216 debates over 4 rounds (random, then power-paired), every debate with a ballot, in 0.2 s** | `test_carnival_325_students_end_to_end`: every student on a team, one house per team, no repeat pairings, no same-house debates, ladder, speaker tab (≥300 speakers), house points, run sheet and MC script for all 4 rounds, and the event, setup, round and results pages render |
| Staff dry-run done | **Not done** (needs staff; pilot checklist E1) | |

Also: class practice for every group size 1–25 gives everyone a role (`test_practice_small_groups`, `test_practice_plan_uses_everyone`); a student adjudicator enters a ballot and students see only their own scores (`test_student_adjudicator_enters_ballot_and_student_sees_own_scores`); solo speech practice counts toward the pathway; the ballot works on a 360 px phone screen with touch (`test_ballot_on_a_phone`); axe 0 serious/critical on all debating pages. Bug found and fixed while closing the phase: re-awarding house points re-created entries staff had reversed (D-047).

## Phase 4 — Intelligence (tag `phase-4-complete`)

| Exit criterion (spec §10) | Result | How measured |
|---|---|---|
| Licence-checked UN voting data import | **Built; real import locked.** Neither licence could be confirmed: both hosts were unreachable from the build environment (D-051). | `test_real_import_locked_until_licence_confirmed`: import is refused until the coordinator records the licence text; then the importer runs. The UN Digital Library column mapping is from memory and unverified. |
| Backtest report against baselines published in docs | **Published below, on SYNTHETIC data only.** No real backtest is possible until a real dataset is imported. | `test_backtest_beats_naive_baseline_on_synthetic`; numbers below from the same code |
| Any AI output without a source is stored as unknown (tested) | **Pass** | `test_ai_estimate_without_source_is_stored_as_unknown`, `test_ai_estimate_with_sources_is_labelled_estimate` |
| AI use approved by the school before it's switched on | **Enforced in code; approval not obtained.** The default provider is offline; a real provider is used only when the coordinator records the school's approval (`test_default_provider_is_offline_and_approval_required`). The Anthropic adapter was tested only with a mock client. | |

**Backtest on synthetic data — these numbers say nothing about real UN voting.** The fixture (`tools/make_synthetic_votes.py`: 120 resolutions × 70 countries, generated with a known per-country, per-topic tendency) was split 70/30 by date: 84 resolutions to learn from, 36 to test on (2,440 test votes). Brier is the three-outcome score (0 best, 2 worst); intervals are 95% bootstrap; "beats" means the paired-bootstrap interval of the difference is entirely below 0.

| Predictor | Brier | Log loss | Difference vs voting-history prior (95% CI) |
|---|---|---|---|
| **Voting-history prior (the platform)** | **0.395** (0.377–0.414) | **0.682** (0.651–0.715) | — |
| Each country's past vote shares | 0.515 | 0.876 | prior better by 0.121 (0.108–0.132) |
| Everyone votes yes | 0.747 | 1.349 | prior better by 0.352 (0.329–0.375) |
| Regional group majority (leave-one-out) | 0.786 | 1.416 | prior better by 0.391 (0.367–0.418) |

Calibration verdict on the same data: **over-confident** (expected calibration error 0.061; 7 of 10 reliability bins flagged after Bonferroni correction, e.g. outcomes the prior gave about 85% happened 70% of the time). So on data generated to contain the signal the prior looks for, the prior finds it, but its probabilities are too extreme. Tuning `history_weight_per_vote` or `sigma_min` against a **real** backtest is the next step once a licence is confirmed; tuning against synthetic data would only fit the generator.

Other Phase 4 checks: synthetic data loads only into the demo dataset; the history prior is used in predictions and labelled "Voting history (SYNTHETIC test data)"; position requests carry no student fields (checked on the dataclass); student AI practice is labelled as AI and private to the student; coaching points to rubric levels and asks questions, never rewrites the student's text.

## Phase 5 — Hardening (tag `phase-5-complete`)

| Exit criterion (spec §10) | Result | How measured |
|---|---|---|
| Permissions audit | **Pass: 164 route/method pairs, every one with a server-side check or a listed public reason; 309 refused requests made, all refused, 0 data changes; cross-class access refused** | `tests/api/test_permissions_matrix.py`; table in `docs/permissions.md` (generated from the code). Found and fixed: the UN-vote import route checked the role inside the function, invisible to the audit; it now uses the standard dependency. |
| Restore from backup on a second machine | **Done between two separate app processes with separate data folders on one computer; not on a second physical machine or on Windows.** 79 tables, 973 rows, 0 differences; integrity ok; 0.07 s | `python tools/restore_drill.py`, `docs/backup-restore.md`. Found and fixed: a damaged backup left the app refusing requests until restarted; restored backups revived old device sign-ins (D-057). |
| Accessibility audit with no AA failures outstanding | **Automated: 0 serious or critical axe issues and no horizontal scroll at 320 px on all 337 distinct pages reachable by the coordinator (276), staff (37), students (18) and projector/public (6). Manual NVDA pass not done.** *Correction (Phase 6): the crawl treated every path segment of 12+ characters as a random token, so long admin table names (e.g. `archetype_affinity`) were checked once between them; fixed, see Phase 6.* | `tests/ui/test_phase5_a11y.py` follows every link per role; page list in `test-results/a11y-pages.json`. Found and fixed: 25+ pages overflowed at 320 px (dropdowns sized to their longest option, grid columns with fixed minimums, an unwrapped URL), printable documents lacked an h1. axe checks only what can be automated (roughly a third to a half of WCAG). |
| Privacy summary for school sign-off | **Written; not yet reviewed by the school** | `docs/privacy-summary.md`, with 6 open questions for the school |
| Performance check | See Phase 2 (45-minute load test) | |
| Staff guide | **Written** | `docs/staff-guide.md` |
| Pilot go/no-go checklist signed off by Ben | **Checklist written; not signed (needs Ben)** | `docs/pilot-checklist.md` |
| The pilot with a class of 25 | **Not done** (out of scope for the build) | |

Also in Phase 5: the nightly retention purge (D-054) and coordinator-only student erasure (D-055), both tested; the CSV and UN-vote imports moved off the event loop.

**Test suite at the end of the build:** 519 tests, all passing (engine, API, Playwright + axe), 5 min 22 s in the cloud container, most of it the accessibility crawl.


## Phase 6 — South Oakleigh redesign, MUN simulation v3, polish (tag `phase-6-complete`)

Work package from PR #1 (22 Oct 2026), done in its priority order; decisions D-058 to D-063.

| Item | Result | How measured |
|---|---|---|
| 0. Audit figure corrected | **Done.** `docs/audit.md` §1, §4, §7 now say 55 to 78 of 263 (21–30%). The original 62 **reproduced**: the same `<= 0.10` test with no tolerance gives 62, because floating-point rounding splits the 23 stances exactly 0.10 from a boundary. | `node tools/audit/engine_audit.js` (`near_boundary_within_0_10_no_tolerance`) |
| 1. Design system (D-058) | **Done.** SOC maroon/dark maroon/green/gold/cream, Cambria/Calibri, logo in the header; 37 text/background and interface pairs all meet WCAG 2.2 AA; no raw colours outside the tokens. Gold fails as text on light surfaces (2.5:1), so a darker `gold-text` (5.2:1) and a two-tone focus ring were added; logged. Letterhead on every printed page and Word export; projector theme. | `tests/test_design_contrast.py` (40 tests), `tests/api/test_design_system.py` |
| 2. Icons (D-059) | **Done.** 72 Lucide icons (lucide-static 1.61.0, ISC, checksum matched npm) in one local sprite; one icon per concept; decorative icons hidden, icon-only controls named; unknown names fail tests. | `tests/test_icons.py` |
| 3. MUN simulation v3 (D-060, D-061) | **Done.** Nine procedural stages with chair scripts as Admin-editable data (GA and SC); roll call, agenda, whip count scored against actual votes (computed votes separate), debrief with pivotal votes, the engine's calibration on the vote and delegate profiles re-based per D-009 with staff override; practice for 1–3 students against a computed chamber with hidden mandates. Works with 1–25 students (GA with 25, SC with 3 tested). | `tests/api/test_phase6_sim.py` (9), `tests/ui/test_phase6_ui.py` (2: the whole flow in a browser, axe on every new screen) |
| 4. Onboarding and polish (D-062) | **Done.** First-run wizard; join cards and poster with local QR codes (segno 1.6.6, BSD-3-Clause); Help dialog on every page, glossary (31 terms), student quick-start, staff guide in the app; every page's title equals its h1 and deeper pages have breadcrumbs (11 fixed); screenshot gallery: 50 images of 25 pages at 1366×768 and 390×844 in `docs/screens/`. Reviewing the screenshots found three real defects, all fixed: the projector timer below the fold, the phone layout, and the phone stage label reading "1 of 9" at stage 7 (CSS counters skip hidden items; regression test added). | `tests/api/test_phase6_onboarding.py` (6), `tests/api/test_crawl.py`, `python tools/screenshots.py` |
| 5. Content (D-063) | **Done.** 122 practice motions (92 new; 37 junior, 44 middle, 41 senior; 15 themes); house-carnival and inter-school run sheets and scripts, chosen by event kind; 16 adjudicator feedback prompts on every ballot; an Evatt-style Security Council demo on a **fictional** crisis with every position labelled "Unverified demo". | `tests/api/test_phase6_content.py` (6) |
| 6. Robustness | See below. | |

**Robustness (item 6)**

| Check | Result | How measured |
|---|---|---|
| `tools/windows_smoke.ps1` | **Works under PowerShell 7.4.6 on Linux: PASS** (Python found, requirements installed into `.venv-smoke`, 573 non-browser tests passed, platform answered its health check in 1.6 s, 4 pages loaded, stopped and tidied). **Not run on Windows or under Windows PowerShell 5.1**, and its `-Browser` option was not run (it downloads Chromium). Ben runs it on the laptop. | `pwsh -File tools/windows_smoke.ps1` |
| Server killed mid-session (SIGKILL, no clean shutdown) and restarted | **No acknowledged change lost, 10 of 10 runs.** Each run: a chair adding speakers and 12 students voting concurrently; killed after at least 2 speaker adds and 3 votes were acknowledged (2 adds and 4–12 votes per run); after restart every acknowledged change was present, `PRAGMA integrity_check` = ok, event numbers strictly increasing. **One earlier run of 11, before the test waited for acknowledgements and caught all connection errors, failed; its output wasn't captured, so the cause is not known.** | `tests/api/test_phase6_chaos.py::test_kill_mid_session_loses_no_acknowledged_change` |
| Chair reconnects to the same state after the restart | **Pass**: a new browser signs in and sees the open vote and the same speakers queue. | same test |
| Missed changes replayed after reconnecting | **Pass**: a client reconnecting with the last event number it saw before the kill received exactly the change groups after it (3 per run), in order. | same test |
| Clean stop and start between lessons | **Pass**: stage, agenda and open session kept. | `test_restart_between_lessons_keeps_everything` |
| Full suite after the redesign | **593 tests, all passing (9 min 40 s in the cloud container)**, including axe (0 serious or critical) on 393 distinct pages crawled per role (coordinator 320, staff 44, student 23, public and projector 6; the crawl was fixed to stop folding long table names together) and the contrast test. | `python -m pytest` |
| Live-update latency after the redesign | **0 lost events; p95 0.77 s (under 1 s), p50 0.33 s, p99 1.30 s, max 1.61 s** over 10 minutes with 30 clients (6,719 updates, 16 divisions; 0 errors, 6 retried keep-alive races). Compared with the first 10 minutes of the Phase 2 run, p95 is unchanged but **p50 rose from about 0.23 s to 0.33 s**: the student live fragment now carries the stage tracker and prompts and costs 9.8 ms instead of 6.6 ms to render (measured on the Phase 5 and Phase 6 code side by side). Server memory went from 99 to 136 MB in 10 minutes, faster than in Phase 2 (97 to 127 MB in 45 minutes); not investigated. | `python tools/loadtest.py --minutes 10` |

**Not verified in Phase 6:** anything on Windows (smoke script, start-up, exports in Word/Excel); a screen-reader (NVDA) pass of the new screens; Ben's review of the design from the screenshots; the chair scripts' wording against the UNAA and Evatt handbooks (they follow common practice and are editable); the 2026 Security Council membership used by both SC demos.

## Phase 7 — Reliability and honesty fixes (tag `phase-7-complete`)

Work package: the Phase 7 comment on PR #1. All eight items done.

| Item | Result | Evidence |
|---|---|---|
| 1. Memory growth and latency drift | **Memory target met:** 4.0 MB growth over the 60 minutes after warm-up (target <10 MB); Phase 6 grew 37 MB in 10 minutes. **p95 target not met:** it rises about 0.16 s an hour; the cause is bounded (below). | D-064 (leak fixed, `tests/engine/test_db_pool.py`); 90-minute soak, 30 clients, below. |
| 2. Kill-and-restart failure | **0 failures in 100 runs** (95% upper bound on the failure rate: about 3%). The Phase 6 failure did not reproduce. | `tools/chaos_loop.sh 100`; `test-results/chaos/`. |
| 3. Evidence quality instead of "0% unknown" | Done | D-065; `tests/api/test_phase7_quality.py` (demo GA: over 99% estimate only, 0% unknown). |
| 4. Honest label for the offline bot | Done | D-066; `tests/api/test_phase7_ai_label.py` covers both states, and an unknown provider is never labelled AI. |
| 5. Phone header | Header **208–246 px → 69 px** at 390×844 (target ≤130). Nav behind a Menu button (`aria-expanded`); Escape closes it; without JavaScript the list shows. | D-067; `tests/ui/test_phase7_header.py` (height, keyboard path, axe open and closed, no-JavaScript fallback). |
| 6. Laptop header on one row | **122 px (two rows) → 69 px (one row)** at 1366×768, staff and students. | Same test; compact account area. |
| 7. Windows smoke script | The Detail column shows pip's own last error line, with a hint for `WinError 206` or network errors; a folder path over 80 characters with long paths off is a WARN before installing; README says where to keep the folder or how to enable long paths. | Parse check and a failing `pip install` exercised under PowerShell 7 on Linux. **Not yet run on Windows.** |
| 8. Whip-count wording | "0 of 100 predictions made (25 students × 4 delegations each)", with singular forms. | `tests/api/test_phase6_sim.py`. |

### Item 1 in detail

90-minute soak, 30 clients (29 students and the chair), run from a frozen copy of commit `97fe24d` on the cloud build machine (4 cores), with nothing else running. 2,020 changes on the session channel, 58,206 live updates measured; **0 lost events, 0 errors, 0 reconnects.**

| Minutes | 0 | 10 | 20 | 30 | 40 | 50 | 60 | 70 | 80 | 85 |
|---|---|---|---|---|---|---|---|---|---|---|
| Server memory at window end (MB) | 104.4 | 106.3 | 106.7 | 106.8 | 108.4 | 109.5 | 109.7 | 109.8 | 109.9 | 109.9 |
| Live-update p95 (s, client side) | 0.70 | 0.74 | 0.66 | 0.79 | 0.82 | 0.78 | 0.78 | 0.89 | 0.84 | 0.90 |

- **Memory:** +4.0 MB between minute 10 and minute 70 (slope 3.6 MB an hour), flat over the last 25 minutes. The fix was D-064: the thread pool retires idle threads, and the read-connection pool kept every dead thread's SQLite connection.
- **Latency:** client p95 0.74 → about 0.90 s (slope +0.16 s an hour); server-side p95 0.51 → 0.58 s. Cause, measured: on the database as it stood at the end of the run, one live-fragment request costs about 1 ms (13%) more than on a fresh one, because the load test's speakers lists fill up (25 → 47 waiting entries: its chair adds speakers to the general list faster than it calls them during moderated caucuses). With 30 clients queuing for 8 worker threads, 13% more work per request becomes the drift. It is **bounded**: a delegation can wait only once per list, so the lists stop growing at the number of delegations (31 here). Rendering does not slow with history otherwise (10 ms at 0 and at 160 votes of history). The server's other counters (pooled connections, threads, caches, live subscriptions, Python objects) were flat for the whole run. **Mitigation:** none needed for a lesson; if a list grows long, the chair clears it.
- **Not valid:** an earlier soak run that day (code was edited under the running server; requests failed after 30 minutes) and one cut short by a worker restart. `tools/loadtest.py` now writes each memory sample as it goes (`rss.jsonl`).

### Item 2 in detail

`tools/chaos_loop.sh 100`: the server is killed with SIGKILL mid-burst (a chair adding speakers and 12 students voting), restarted on the same data, and checked: every acknowledged speaker and vote present, database integrity "ok", event numbers unique, the chair reconnects to the same state, and a client that reconnects is sent exactly the changes it missed. **100 passed, 0 failed**, 6.7 s a run. Each run killed the server after 2 speaker adds and 3–8 votes had been acknowledged. The single failure in 11 early Phase 6 runs (before the test waited for acknowledged actions) did not reproduce.

The full suite then found three live-update bugs in the browser (D-073): a page could stay stale after a page swap (a student missed the vote card in about one run in five), open panels closed on refresh, and an unsent drop-down choice was reset. All fixed; the guided-session test then passed 40 of 40 runs.

Full suite at the phase-7-complete commit: **624 passed** (engine, API, Playwright and axe), 8 min 11 s.

## Phase 8 — Committee flow v4 (D-068 to D-072)

Ben approved the flow in `docs/design/mun-committee-flow.html` on 27 Oct 2026 and asked for student tabs and friends and foes sheets. Built:

- **Six stages** (roll call, agenda, opening statements, the floor, voting procedure, debrief). Migration 0007 maps running sessions and keeps edited scripts; an upgrade test builds an old database and checks it.
- **The floor:** motions in order of precedence; unmoderated caucus at most 10 minutes per motion; close debate moves to voting procedure; roll-call order drawn by lot; the floor reopens with another draft after a failed vote.
- **Amendments:** private draft → submitted (tracked changes, public) → signatories (a fifth of the delegations with students, minimum two: D-072) → suggested edits accepted or declined by the sponsors → the floor (speakers for and against on their own list) → vote → adopted on every screen, or friendly with no vote.
- **Student tabs:** floor, motions and votes (one-tap 3, 5 or 10 minute caucus), points (order, privilege, inquiry, right of reply), messages (per-delegation channels; the Chair reads and can hide them: D-070), my speech (private drafts), amendments, friends and foes (per operative clause, beside the engine's labelled estimate: D-071).
- **Prepare page:** country brief with evidence quality, the proposed resolution, the opening-statement pad.
- **Security Council:** live veto warning on the Chair's vote panel, the student's vote card and the projector.
- **Minutes** record points, amendments brought to the floor and friendly adoptions.

Found and fixed while building it, each with a test: the "one fifth of the committee" threshold was unreachable in a class (computed seats can't sign); after a failed vote the session forgot which draft had failed; "present and voting" was promised at roll call but abstaining was still accepted; a granted right of reply went to the general list while an amendment's list was live.

Tests: `tests/api/test_phase8_floor.py` (17), `tests/ui/test_phase8_floor_ui.py` (3, with axe on every new screen). Not built: sponsors and signatories for whole draft resolutions (drafts are still added by the teacher).

## Phase 9 — Debating and public speaking for the classroom (D-074 to D-077)

Ben, 27 Oct 2026: the debating section should be a classroom tool (teachers type each team's names, set speech times, project it) and a preparation tool for the debate team (arguments, the other side's likely arguments to rebut, scored), with impromptu topics, prepared-speech help, templates and timers for students to practise alone. Not for the carnival. Built:

- **Classroom runner** (D-075): class debates (1 to 4 speakers a side, optional preparation and reply speeches) and speaking rounds (prepared, or impromptu with a topic drawn when each turn starts). The run order is computed from the settings. One server-held timer per step, shown on the teacher's page and an unguessable-link projector view: green while speaking, amber after the warning bell, red at time, then counting past time; one ring and two rings on the teacher's laptop. Space, arrow keys and presentation clickers run it. Each speaker's time is recorded; quick rubric scores, a winner and comments; students whose names match the roster see their own on their page.
- **Prep studio** (D-076): debate cases (team line, definition, arguments in four parts), rebuttals in four steps against the other side's **three likely arguments for every one of the 122 motions** (732 written for the platform, labelled as starting points and not evidence, editable in Admin), a structure check that only counts written parts, and two new rubrics (written argument, written rebuttal) for the student's self-score and the teacher's score.
- **Speaking practice and speech writer** (D-077): impromptu practice from 117 topics by year level with four structure cards, prepared rehearsal, rebuttal drills; four prepared-speech templates with a live word count and time estimate (130 words a minute, stated), a rehearsal view and cue cards.
- **Privacy:** typed names are first names only (no digits, @ or symbols, at most 24 characters); unmatched names are replaced with "Speaker N" after a year (retention); erasing a student deletes their cases, rebuttals and speeches and removes their name and comments from runs (tested, including the change history).
- The debating home leads with the classroom tools; tournaments and carnivals are unchanged, lower on the page.

Found and fixed while building it: a control button's `form.action` returned the form's own `<input name="action">` instead of the URL, so every button press got a 405 (caught in the browser, not by the API tests); the first impromptu speaker's topic wasn't drawn when there was no thinking time; `hidden` lost to the `.field` display rule, so unused speaker places still showed.

Tests: `tests/api/test_phase9_debating.py` (17: content coverage, run order and recorded times, the bell phases, name rules, impromptu reveal, projector token and live channel, staff scope, scores reaching only the student, editing, case privacy, the structure check, the speech estimate, practice modes, erasure, the yearly name purge), `tests/ui/test_phase9_ui.py` (3: keyboard-driven run with the projector following, the bell phases in the browser, the student practice flow saved end to end, axe on every new page).

Not verified: on Ben's Windows laptop; the bell's volume through a classroom projector's speakers; the likely arguments against the school's own debating coaching (they are generic and editable).

## Phase 10 — Smooth, no phones, the College design (D-078 to D-080)

Ben, 27 Oct 2026: fix scroll and typing glitches; no phones, students connect with a code that has their name built in, and absent students mustn't be a problem; restyle to the SOC design system; rebuild the deck with both the facilitator's and students' views.

- **Smoothness (D-078):** measured in the browser before and after (`tests/ui/test_phase10_smooth.py`, 4 tests). Before: a live update replaced the box a student had clicked into (shown failing against the old `live.js`); a new page opened 410 px down. After: a region with the focused box waits until the student leaves it; live refreshes keep the scroll position; saving keeps your place and shows the confirmation as a toast; new pages start at the top. A probe that types into every box in the live regions while the committee changes every 0.7 s found no jump, lost focus or lost text.
- **Sign-in (D-079):** personal six-character codes (no 0, O, 1 or I), on printable per-student cards with the student's own address; no list of names; one laptop at a time; throttled; teachers can show or renew a code; codes never exported. QR codes, the device lock and second-device approval are gone. Delegations whose students are away are voted by the engine and labelled computed; a student who arrives in time takes the vote back. Tests: `tests/api/test_phase2_join.py` (rewritten, 8).
- **Design (D-080):** the SOC design system's tokens, Cinzel and Open Sans served locally, a white header with the crest, maroon table headers, pill buttons, the gold heading bar, the letterhead footer; the projector on white with the design system's timer colours.
- **Deck:** rebuilt with paired views (teacher's laptop, student's laptop, the projector) at laptop and classroom-screen sizes.

Not verified: the fonts on Ben's Windows laptop (they are served by the app, so they should not depend on what's installed); the look on the classroom projector itself.
