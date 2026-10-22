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
