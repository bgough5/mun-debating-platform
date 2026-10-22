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

Audit figures re-checked with `node tools/audit/engine_audit.js` (output in `tools/audit/engine_audit_output.json`): 279 cells, 263 computed, 83 abstain, Germany = Spain, 2 pass/fail flips in 54 amendment cases, 51 of 96 override cases changed, rubric 30/30 for the keyword salad and 15/30 for the real offer. One figure did **not** reproduce exactly: the audit's "62 of 263 within ±0.10 of a bucket boundary". This script gets 55 (strictly within 0.10) or 78 (within or exactly at 0.10); the original script wasn't kept, so the convention it used is unknown. The conclusion (a large share of stances sit on a knife-edge) stands either way.

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
