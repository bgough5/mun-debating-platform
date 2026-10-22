# Pilot go/no-go checklist

For Ben to complete and sign before the first pilot with a class (spec §10, Phase 5 exit). The "Who" column says who can do each item; the build session could not do any item that needs the laptop, the school or real people. A single "no" in a **must** section means no-go.

## A. Approvals (must)

| # | Item | Who | Done |
|---|---|---|---|
| A1 | School has read `docs/privacy-summary.md` and signed off the pilot on the coordinator's laptop | school | ☐ |
| A2 | School has answered the open questions in privacy summary §8 (plain HTTP on school Wi-Fi, laptop security, backups after erasure, parent notice) | school | ☐ |
| A3 | AI stays **off** for the pilot (Intelligence → AI settings shows "Offline practice provider (no AI service)") | Ben | ☐ |
| A4 | No hosting beyond the laptop | Ben | ☐ |

## B. The laptop (must)

| # | Item | Who | Done |
|---|---|---|---|
| B1 | Python 3.12 installed; `start_platform.bat` starts the platform and prints the `/join` address | Ben | ☐ |
| B2 | A phone or second device on school Wi-Fi can open the `/join` address (Windows firewall allows Python; the network allows device-to-device traffic) | Ben + ICT | ☐ |
| B3 | Laptop disk is encrypted and has a screen lock | Ben | ☐ |
| B4 | Laptop plugged in; sleep turned off for the lesson | Ben | ☐ |
| B5 | Coordinator passphrase set and written down somewhere safe (it can't be recovered; deleting `data/config.json` lets you set a new one but also resets the dataset choice and AI settings; the data itself is kept) | Ben | ☐ |

## C. Data (must)

| # | Item | Who | Done |
|---|---|---|---|
| C1 | Real dataset selected (Admin → Data); demo banner **not** showing | Ben | ☐ |
| C2 | Class created with first names only (last initial only where two share a name) | Ben | ☐ |
| C3 | Backup drill: download a backup, restore it on a second machine or a fresh copy of the app, and see the class there (`docs/backup-restore.md`) | Ben | ☐ |
| C4 | A nightly backup appears in `data/backups/` after the platform has run for a day | Ben | ☐ |

## D. The software (must) — measured in the build; re-check on the laptop

| # | Item | Build result | Laptop | Done |
|---|---|---|---|---|
| D1 | All automated tests pass (`python -m pytest`) | see `docs/phase-reports.md` | ☐ | ☐ |
| D2 | 30 clients for 45 min: no lost updates, p95 under 1 s | see Phase 2 report (cloud container, not the laptop) | `python tools/loadtest.py --minutes 45` ☐ | ☐ |
| D3 | Chair browser killed mid-session recovers | tested automatically | try once by closing the chair tab ☐ | ☐ |
| D4 | axe: 0 serious/critical on every page | see Phase 5 report | — | ☐ |
| D5 | Exports open in Word and Excel | LibreOffice only in the build | open one .docx and one .csv on the laptop ☐ | ☐ |

## E. People (should)

| # | Item | Who | Done |
|---|---|---|---|
| E1 | Staff dry-run in demo mode: a live MUN session with a division, and a debating round with ballots | Ben + staff | ☐ |
| E2 | Ben has done W-1 (whip count to calibration) himself in demo mode | Ben | ☐ |
| E3 | NVDA screen-reader pass of the student join page, live page and ballot (not possible in the build) | Ben or a colleague | ☐ |
| E4 | Staff have read `docs/staff-guide.md` | staff | ☐ |
| E5 | House points rules and debate formats set to the school's real ones (Admin) | Ben | ☐ |

## F. On the day (should)

- Class code on the board; `/join` address on the board.
- Plan B if Wi-Fi fails: run the session on paper; the platform is not needed to teach the lesson.
- Afterwards, record the pilot measures (spec §10): data-loss incidents, chair recovery time, share of students who joined unaided in under 2 minutes, calibration of any predicted votes, and what staff and students said.

## Decision

Go ☐ / No-go ☐ Signed: ____________________ (Ben Gough) Date: __________

Notes:
