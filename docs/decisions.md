# Decisions log

Status key:
- **Decided (Ben):** Ben chose it.
- **Done:** an action taken this session.
- **Proposed:** my recommendation, awaiting approval with the spec.
- **Assumption:** made so work could continue; Ben can overturn it.

Newest entries go at the bottom. Earlier project decisions (July 2026) are in `HANDOVER.md` §11a–11b. Where this log conflicts with them, this log wins.

---

### D-001 Put the project under git and tag a baseline — Done (22 Oct 2026)
The folder wasn't a git repository, so there was nothing to tag. Ran `git init` and added a `.gitignore` covering `__pycache__/`, `*.pyc` and `.claude/settings.local.json` (local machine permissions). Committed the existing files unchanged as `67543a3` and tagged it `pre-platform-baseline`. Files on disk were not modified.
- **Note:** your global git `user.name` is the placeholder "Your Name". I set the author name to "Ben Gough" for that commit only and left your git config untouched. Fix it with: `git config --global user.name "Ben Gough"`.
- Scanned before committing: no secrets and no real student data (test names are fakes such as "Alex").

### D-002 Pilot hosting: teacher laptop on school Wi-Fi — Decided (Ben)
Already proven with student devices on the school network. No new hosting approval is needed for the pilot. The app stays host-agnostic, and any server or cloud option goes to the school for sign-off first. Nothing about hosting beyond the pilot is decided.

### D-003 Student join: class code + pick your name — Decided (Ben)
No passwords and no per-student codes. The accepted risk is that anyone with the class code can pick someone else's name. Mitigations (spec §8.4) are an **Assumption**: name locked to a device once claimed, teacher approval for a second device, event-log attribution, staff can reverse score-affecting actions, and codes rotate per term.

### D-004 Co-editing: paragraph ownership — Decided (Ben)
One editor per paragraph at a time, with live updates to everyone else. Anyone else's change is tabled as an amendment. This avoids a conflict-merging library and mirrors real procedure.

### D-005 Build and design everything before piloting; no pilot date — Decided (Ben)
The Term 1 2027 target is dropped. All of Phases 1–5 come before a student pilot.
- **Approved** addition: staff-only demo-mode dry-runs at the end of Phases 2 and 3, to catch wrong turns early without involving students.

### D-006 Keep the core idea, replace the shell — Decided (Ben approved all suggestions, 22 Oct 2026)
Evolve the domain logic and data; replace the relay and UI with a server-owned Python app (spec §7, option B). Evidence for why the existing shell can't be extended in place is in audit §5.3–5.4 and spec §7.2. About 10–15% of the existing lines carry over as logic or data. The rest is frozen in place, not deleted.

### D-007 Freeze the v2 game as a "Practice game" module — Decided (Ben approved all suggestions, 22 Oct 2026)
It works and students have used it. It stays runnable from its current files and from the tag, linked from the new app, and is not extended. Its files are not moved until Phase 2, and only if the move is tested.

### D-008 Predictions are probabilities with evidence; the archetype model becomes one prior — Decided (Ben approved all suggestions, 22 Oct 2026)
This replaces the single deterministic bucket. Constants are data and are tuned only by calibration. Countries with no evidence are shown as unknown. Spec §5.

### D-009 Stop grading students against the model — Decided (Ben approved all suggestions, 22 Oct 2026)
Mandate Fidelity must not be scored against an unvalidated prediction. In the new design, fidelity is judged against the evidence-based prediction **with a staff override**, and the score shows which evidence it used. Audit §4 explains why.

### D-010 Rubric auto-scorer is a hint, not a grade — Decided (Ben approved all suggestions, 22 Oct 2026)
A keyword salad scored 30/30 while a genuine conditional offer scored 15/30 (audit §5.1). Rubrics become data scored by staff. The regex checks survive only as optional "checklist hints" for students.

### D-011 Voting rules are data; GA and Security Council from the start — Decided (Ben approved all suggestions, 22 Oct 2026)
UNAA conferences used a General Assembly format; Evatt (UN Youth Australia) is a Security Council simulation. Spec §5.4.
- **Assumption:** Evatt's current rules match the public descriptions I found (2015–2023). Please confirm against this year's rulebook.

### D-012 Fixed tie-breaking everywhere — Decided (Ben approved all suggestions, 22 Oct 2026)
Rankings break ties by score, then ISO-3 code. Sponsorship ties go to the earliest sponsor. Simulations are seeded and reproducible from a stored seed and input hash.

### D-013 Two calibration targets, kept separate — Decided (Ben approved all suggestions, 22 Oct 2026)
- Conference outcomes: how student delegates voted.
- Real UN outcomes: backtests, Phase 4.

They answer different questions and must not be pooled.

### D-014 UN voting datasets need a licence check before use — Decided (Ben approved all suggestions, 22 Oct 2026)
Candidates are listed in spec §5.7. I could not confirm a licence for any of them. No data will be imported until each licence is confirmed and recorded here.

### D-015 Stack: FastAPI, SQLite, Jinja2, htmx, minimal vanilla JS; no npm — Decided (Ben approved all suggestions, 22 Oct 2026)
Chosen to be boring, well supported and maintainable by one person who knows Python, SQL and HTML/JS. Python package named `app/`, not `platform/`, which would shadow the standard library.

### D-016 PDF export via browser print stylesheets — Decided (Ben approved all suggestions, 22 Oct 2026)
This avoids a server-side PDF engine, which is fiddly on Windows. Word export uses `python-docx`; CSV uses the standard library. To be revisited if batch PDF generation is needed (e.g. 325 carnival certificates).

### D-017 Admin and staff sign-in by passphrase — Decided (Ben approved all suggestions, 22 Oct 2026)
Students need no password, but the admin screens must not be reachable by students. One coordinator passphrase is set at first run and stored hashed with `hashlib.scrypt`. Staff get their own.

### D-018 Accessibility target is WCAG 2.2 AA — Decided (Ben approved all suggestions, 22 Oct 2026)
Each phase is checked with axe (automated), keyboard-only use and NVDA. Spec §9.

### D-019 Retention — Decided (Ben approved all suggestions, 22 Oct 2026)
- Class data archived at year end.
- Pathway records kept while a student is in the program.
- Soft deletes purged after 30 days.
- Event log kept one school year.

All of this is subject to school policy, which Ben should check.

### D-020 Phase 0 documents not committed yet — Done, then superseded by D-021
Per the working rule "commit only when asked", `docs/`, `CLAUDE.md` and the README addition are left uncommitted for Ben to review.

### D-021 Spec approved; all suggestions accepted — Decided (Ben, 22 Oct 2026)
Ben read the Phase 0 documents and approved all suggestions. D-005's staff dry-runs and D-006 to D-019 are now decisions. Phase 1 may start. The Phase 0 documents are committed.

### D-022 Class size: 25 maximum, and everything works with fewer — Decided (Ben, 22 Oct 2026)
A live session holds **at most 25 students**, enforced by the server. Every activity must also work with fewer, so a small group is never blocked. How that applies (**Assumption**, to confirm):
- **MUN:** 1 to 25 students. Countries without a student are voted by the prediction engine, clearly labelled as computed, so a committee of 15 (Security Council) or 31+ still runs with 3 students. A single student can practise solo.
- **Debating:** a round needs two sides. With 2–5 students, team sizes shrink and roles combine. With 1 student, solo speech practice with timer and rubric self-review.
- **Ties:** odd player counts are no longer required. Ties are settled by the committee's voting rule (D-011, D-012).
- **The cap is on live joins per session, not on stored data.** A 325-student carnival is staff-entered event data, not 325 live logins.
- **Tests:** load tests cover 25 live students plus staff and projector (30 connections); small-group tests cover 1, 2 and 3 students.

### D-023 Git author name fixed — Done (22 Oct 2026)
Following D-001's suggestion, git's global `user.name` is now set to "Ben Gough" on this machine.

### D-024 Full build continues in a cloud session — Decided (Ben, 22 Oct 2026)
Ben asked for the build to move to the cloud and to "completely rebuild and reimagine" the platform, including debating, using the available cloud credits.
- `docs/spec.md` is the **floor, not the ceiling**: the cloud session may extend it, logging every new decision here.
- `CLAUDE.md`'s non-negotiables still bind: privacy, no real student data, no hosting decision beyond the laptop pilot, AI labelled as estimates, and measure, don't assert.
- The cloud session is code-only: it never receives student data.

---

## Build session (cloud, from 22 Oct 2026)

Entries D-025 onward were made during the cloud build (D-024). "Decided (build)" means I chose it so the work could proceed; Ben can overturn any of them.

### D-025 Evidence is combined as a weighted average, not added as shifts — Decided (build)
Spec §5.2 wrote μ = prior + Σ evidence shifts. Built instead: every source (archetype prior, bloc position, statements, class intel…) gives a position from −2 to +2 and a weight; μ is their weighted average and the spread σ narrows as total weight grows (σ = σ_min + (σ_unknown − σ_min)/(1 + Σw)).
- **Why:** additive shifts are unbounded (ten pieces of class intel would push a country to +10) and can't express "they will abstain". A weighted average stays on the scale, and "no sources" falls out naturally as *unknown* (μ = 0, σ = σ_unknown).
- It is still easy to explain to a student: "each source gives a position; better sources count more".

### D-026 Model constants v2.0-default — Decided (build), unvalidated
σ_unknown 1.5, σ_min 0.45, cut-points ±0.4 (the v2 abstain band), archetype weight 1, source weights 4/2/1 (high/medium/low, spec §5.3), strength ×0.5/1/1.5, conditional ×0.5, stale after 180 days ×0.5, bloc cohesion 0.15–0.6 by bloc. All are data (`model_version`, Admin → Model versions) and **none has been calibrated**: there are no real outcomes yet. Change them only from a calibration report.

### D-027 No numpy — Decided (build), measured
Spec §7.2: add numpy only if a GA simulation of 193 countries × 10,000 runs takes over 1 s. Measured in the cloud container: **1.02 s** (1.64 s including the swing analysis). That is on the line, so: no numpy; interactive predictions use 4,000 runs (31-country GA with swing: 0.12 s). Re-measure on Ben's laptop; numpy is only worth it if 193-member GA committees become routine.

### D-028 Bloc membership lists entered from memory and flagged unverified — Decided (build)
UN regional groups (193 members), EU, Arab Group, AOSIS and LDCs are seeded with a source URL each and `verified = 0`. They were typed from memory in the build session, not copied from the sources, so they must be checked before they are relied on. G77 was **not** seeded: I couldn't list its 134 members reliably. Security Council 2026 elected members in the demo are also from memory.

### D-029 Paragraph evidence carries over to its amendments — Decided (build)
Fixes audit §5.2 (in v2, any amendment discarded every override). Evidence about a paragraph still counts when predicting the paragraph as amended; evidence about a specific amendment counts only for that amendment. A *delete* amendment is predicted as the vote to delete, so positions are negated. Resolution-level evidence counts at half weight for individual paragraphs. Tested: the US override (−2) on clause 2.1 still dominates under the "soften" amendment.

### D-030 Pathway milestones are suggested from records, confirmed by staff — Decided (build), beyond spec
The pathway page detects evidence in the records (amendments sponsored, lobbying tasks done, speeches on a speakers list, debates scored, practice speeches) and shows it as a *suggestion*. Only staff record a milestone. Keeps the pathway a teacher's judgement while making it cheap to keep up to date.

### D-031 Branches — Done
The build uses one long-running branch, `platform-build`, with a draft PR into `main` (Ben merges). The cloud session's own branch `claude/kind-cori-1rh98q` is kept pointing at the same commits.

### D-032 Ports — Decided (build)
The platform serves on port 8080 (`start_platform.bat`). The frozen v2 game keeps 8000 and 8765, so both can run at once; the platform's "Practice game" page links to it and serves the offline solo build directly.

### D-033 Calibration report details — Decided (build), measured
- Reliability bins are flagged when the mean prediction lies outside the Bonferroni-corrected 95% Wilson interval of what happened. Measured on synthetic data (3,000 items, 100 seeds): a perfectly calibrated model was flagged in 4 of 100 runs; a deliberately over-confident one was flagged in 100 of 100 (87 "over-confident", 13 "miscalibrated").
- Deterministic baselines (everyone votes yes; bloc majority) give 0.9/0.05/0.05 so log loss stays finite. The bloc baseline uses the majority of the *other* bloc members on the same vote (leave-one-out), which is generous to the baseline.
- The model only "beats" a baseline when the whole 90% paired-bootstrap interval of the Brier difference is below zero; otherwise the report says it doesn't clearly beat it.

### D-034 Swing ranking — Decided (build)
ΔP(pass) for moving one step (one point on the −2..+2 scale) toward yes, computed on the same simulated draws as the baseline, multiplied by σ/σ_unknown so movable (uncertain) targets rank above settled ones. Ties: score, then ISO-3/bloc code (D-012).

### D-035 Seed comes from the inputs — Decided (build)
A prediction's seed is the first 32 bits of the SHA-256 of its inputs, so the same inputs always show the same number (no flicker on reload) and a stored snapshot replays exactly ("Check it reproduces" on the prediction page).

### D-036 Confirmations work without JavaScript — Decided (build)
Every delete, archive, reset or restore needs a ticked checkbox that names the item ("Yes, delete Fiji") and is checked on the server (spec R4).

### D-037 Sessions and forms — Decided (build)
Server-side sessions: the browser holds a random token, the database holds only its SHA-256, so staff can sign any device out. Every form carries a CSRF token (double-submit cookie) and cookies are SameSite=Lax. Five wrong passphrases lock that account's sign-in for 60 s.

### D-038 Full names are cut to a first name and initial — Decided (build)
If staff type "Sam Lee" into the roster, it is stored as "Sam L." (spec §8.1: first names only). The last initial is kept only if needed; the class page warns when two students share a first name with no initial.

### D-039 Live updates re-fetch server-rendered fragments — Decided (build)
The server sends only "channel X changed (event n)" over one WebSocket; each page re-fetches the HTML fragments that show channel X through htmx. All rendering and every access check stay on the server, and the client script is small (`app/static/js/live.js`). A client that reconnects sends the last event number it saw and is sent every change it missed from the event log, so no change is lost. Re-fetches are throttled (at once, then at most every 250 ms, never dropping the last) so a burst of 25 votes doesn't cause 25 × 30 page loads. A region holding unsaved typing, or an open paragraph editor, isn't refreshed until the typing is saved or abandoned.

### D-040 Procedural votes in small groups — Decided (build)
Delegations with no student don't vote on motions (the engine has nothing to say about procedure); only delegations with students vote. An absolute minimum in the rule (the Security Council's 9) is scaled to the share of members voting, rounded up (3 students of 15 → 2 yes needed). The chair can also pass a motion "with no objection", as real chairs do. Tested with 1, 2 and 3 students.

### D-041 Computed delegations vote the engine's most likely vote, and never calibrate the engine — Decided (build)
When a substantive vote opens, a prediction is stored and each delegation without a student is given its most likely vote (ties go to abstain), labelled "computed". When voting closes, only the human votes are recorded as conference outcomes next to that stored prediction, so live classes feed the calibration report automatically while the engine is never graded on its own guesses.

### D-042 Performance architecture — Decided (build), measured
Measured with `tools/loadtest.py` (30 clients). First runs had a p95 update latency of 10.6 s because synchronous SQLite work ran on the event loop and every client's re-fetch repeated ~21 queries. Changes, each measured: request handlers run their database work in the thread pool (forms are read by an async dependency); read connections are pooled per thread; the shared part of a live session's view is computed once per change and reused by all 30 clients; a browser's session lookup is cached for 5 s and cleared whenever a device is signed out; the thread pool is 8 workers instead of 40 (the work is Python, so more threads only fought over the GIL and starved the writer). Throughput of the student live fragment went from 57 to 267 requests/s; the 2-minute test went to p95 0.60 s with 0 lost events. Full 45-minute numbers: `docs/phase-reports.md`.

### D-043 The 25-student cap counts students seen in the last 2 minutes — Decided (build)
A live session admits a 26th student only when fewer than 25 have been active (page or WebSocket heartbeat) in the last 2 minutes. A student who already holds a place can always come back. Joining the class itself is not capped: the cap is on live joins per session (D-022).

### D-044 Paragraph locks lapse after 60 s without a heartbeat — Decided (build)
An open editor sends a heartbeat every 20 s. A closed laptop releases its paragraph within a minute; staff can always take over a lapsed lock. Saving checks the lock, so two people can't overwrite each other even without JavaScript.

### D-045 Debating draw rules — Decided (build), tested
Round 1 is a seeded random draw; later rounds are power-paired by wins, then points, then margin, then id. Pairing walks down the ranking and takes the nearest valid opponent, giving up rules only when it must, least important first: side balance, then same-house (carnivals), then repeat pairings. A swap pass then repairs any remaining clash. Every relaxed rule is shown on the draw. Measured over 100 simulated events (16 teams, 4 rounds): no repeat pairings, 97.5% of teams within one of an even side split, none worse than two; 108 teams over 4 rounds: 99.98% exactly 2 aff / 2 neg. Byes go to the lowest-ranked team that hasn't had one. Rooms go to the top of the draw first (accessible rooms to teams that need them); adjudicators are allocated by rating to the strongest brackets, never from either team's house where avoidable.

### D-046 Ballots — Decided (build)
The winner must be the team with the higher total; level totals are allowed only with an explicit winner (schools debates can't be drawn). A panel decides by majority; an even split goes to the chair's ballot. Ladders and speaker tabs are always recomputed from ballots, so a corrected ballot fixes everything at once. Students see only their own scores and feedback.

### D-047 House points are entries, reversed by counter-entries — Decided (build)
Every point is an entry with a reason and who made it. Reversing adds a cancelling entry; nothing is deleted (spec §8.4). Awarding is idempotent per debate or placing, and never re-creates an entry staff have reversed. If a corrected ballot changes a winner, the next award reverses the old win entry (reason "ballot corrected") and awards the new winner's house. The seeded rules (win 3, participation 1, places 10/6/3, best speakers 3/2/1) are placeholders for the school's real rules.

### D-048 Debating formats and scale are assumptions — Assumption
Formats seeded: schools 3 v 3 (junior, 4 min; senior, 6 min), small-group 2 v 2, and 1 v 1. Speaker scores use matter 40, manner 40, method 20. These were not checked against the DAV or any competition rulebook; edit them under Admin.

### D-049 Practice for any number of students — Decided (build), beyond spec
Staff tick who is present and the platform fits the format: 1 student → solo speech practice (timer that never cuts them off, rubric self-review, reflection, teacher comments); 2 → one-on-one with replies; 3 → one-on-one with a student adjudicator; larger groups → as many 3 v 3 rooms as fit, then smaller rooms, with leftovers as student adjudicators, so no one sits out (tested for every size from 1 to 25). Student adjudication and solo practice feed the pathway suggestions (D-030).

### D-050 School-wide events are run by all staff — Decided (build)
Staff run debating events for their classes and every event with no class (carnivals, competitions), because carnivals need many adults. Students can open only events they are in.

### D-051 UN voting data: licences not confirmed; import locked — Done (build), Ben to decide
I could not read either dataset's licence page: both hosts were unreachable from the build environment. A web search quotes the UN Digital Library record (https://digitallibrary.un.org/record/4060887) as "Copyright, United Nations; Non commercial use, with attribution"; I found no statement of terms for the Voeten Harvard Dataverse dataset. Per D-014, nothing real was imported. The importer, history priors and backtest are built and tested against a synthetic fixture (`tools/make_synthetic_votes.py`), which can be loaded only into the demo dataset. Import of a real source stays locked until the coordinator records, in the app, the licence text read on the source's own page. The UN Digital Library column names in the importer's "undl" format are from memory and must be checked against a downloaded file.

### D-052 Voting-history prior — Decided (build)
For a paragraph with tags T, each country's past votes on resolutions sharing a tag in T give a position: 2 × (yes − no) / votes cast (abstentions pull toward 0), weighted 0.25 per vote up to 4 (as strong as an official statement). Resolutions are tagged by keyword rules (Admin-editable) from their UN subjects and titles. This gives resolution-level priors only (spec §5.7) and inherits the recorded-vote bias toward contested issues.

### D-053 AI behind a provider interface; offline by default — Decided (build)
The offline provider calls nothing: its "position suggestions" only restate evidence already recorded with a real source (never unsourced notes), its practice delegation uses the archetype lines, and its coach points to the next rubric level and asks questions. An Anthropic (Claude) adapter exists but is used only when the coordinator records the school's approval and reference, the `anthropic` package is installed, and an API key is in an environment variable on the laptop. It has been tested only with a mock client, never against the live API. Any AI position without a source is stored as unknown and doesn't change predictions; with sources it is stored as "AI estimate — verify" at low weight. Requests for positions carry country and resolution text only. AI never writes a student's speech, clause or amendment.

### D-054 Retention runs nightly, after the backup — Decided (build), tested
D-019 is enforced by `app/retention.py`, run by the nightly loop straight after the nightly backup. Soft-deleted rows older than 30 days are deleted and their copies in the change history are blanked, so the data is really gone (a 14-day backup still holds them, as a safety net). A row something still points to (a deleted class that still has students) is kept and reported, never force-deleted; it goes on a later run once its children are purged. Change-history entries older than 365 days are deleted. A purge leaves one history entry with counts only. Year-end archiving of classes is the existing "Archive" button (coordinator only).

### D-055 "Erase student" for requests and exits — Decided (build), beyond spec
Spec §8.6 says pathway records are deleted on request or at exit, but a soft delete can't remove a student who appears in ballots and votes. The coordinator (only) can erase a student: the name becomes "Erased"; their own writing (practice reflections, AI practice chats, milestone notes, comments on their speeches) is deleted; their devices are signed out; and the change history is scrubbed of their name and of copies of the deleted rows. Their speaker scores, team places and votes stay, unnamed, so other students' ladders and house points don't change. Paragraphs written with the class stay as class work. Tested, including that staff can't do it.

### D-056 Permissions are audited from the code, every build — Decided (build)
`app/web/route_audit.py` reads, for every route, which server-side role check it depends on. A route with no check must be listed as public with a reason, or the test suite fails. The test also requests every route as every role that should be refused and checks it is refused with no data change, and checks cross-class access. `docs/permissions.md` is generated from the same table, so it can't drift from the code.

### D-057 Restore checks the file first and signs everyone out — Decided (build), tested
A backup is validated (zip, manifest, SQLite integrity) before the open database is touched; previously a damaged file could leave the app refusing requests until restarted. After a restore every device signed in at the time of the backup is signed out, so old sign-ins don't come back to life; the coordinator who restored stays signed in.

### D-058 South Oakleigh design system — Decided (Ben, Phase 6 work package); supersedes HANDOVER §11b's navy/UN-blue identity
The platform now uses South Oakleigh's own identity: maroon `#8C332A` (primary), dark maroon `#2A1512` (header, navigation, projector), green `#0A6B39`/`#0A4527` (success, "for"), gold `#B8960C`/`#D4B441` (accent), cream `#F4F0E6` page, `#FBFAF6` cards, ink `#2A2320`; Cambria/Georgia headings and Calibri body (Carlito, Segoe UI and system fallbacks); the SOC diamond logo with the school name in the header. Tokens live in `app/web/design.py` and the `:root` of `app/static/css/app.css`; `tests/test_design_contrast.py` checks they match, checks all 37 text/background and interface pairs against WCAG 2.2 AA, and fails if a colour is written anywhere in the stylesheet outside the tokens.

Measured and adjusted, never silently swapped:
- **Gold fails as text on every light surface** (2.5:1 on cream, 2.7:1 on cards). Gold stays decorative on light surfaces (rules, borders) and is text only on dark maroon (6.1:1; light gold 8.6:1). Added `gold-text` `#7A6206` (5.2:1 on cream) for gold-coloured text on light backgrounds.
- **A gold focus ring fails the 3:1 non-text minimum on cream** (2.5:1). Focus is a dark-maroon outline (15.2:1) with a light-gold halo, and a light-gold outline on the dark header and projector (8.6:1).
- Added `muted` `#655C55` for secondary text (5.7:1 on cream) and `control` `#8A7F76` for input borders (3.4:1).
- Maroon, dark maroon, green, cream, card and ink pass as specified: white on maroon 8.0:1, ink on cream 13.6:1, green on cream 5.8:1.

Components: primary (maroon), secondary (outline), danger (dark maroon), success (green) and link buttons; forms; tables; cards; badges; tabs as links (work without JavaScript); toasts in a polite live region; native `<dialog>` with focus returned to the opener; empty states that name the next action; htmx loading indicators. Stances and votes always carry a word and a symbol as well as colour. Print: every printed page carries a South Oakleigh letterhead, and every Word export has the logo and school name in its page header. Projector: dark maroon background, cream text, light-gold headings and timer (9rem), larger list type. Easy-read, reduced motion, 200% zoom and 320 px reflow are kept and re-tested.

### D-059 Icons: a local Lucide sprite, one icon per concept — Decided (Phase 6 work package)
72 icons from lucide-static 1.61.0 (ISC licence, checked in its `package.json` and `LICENSE`; copied to `app/static/icons/LICENSE-lucide.txt`; tarball checksum matched the npm registry's) are built into one SVG sprite by `tools/build_icons.py`. No icon font and no CDN. Templates call `icon("vote")`: without a label the icon is `aria-hidden` and the visible word carries the meaning; with a label (`icon("undo", "Undo")`) it is `role="img"` with an accessible name, for icon-only buttons. `app/web/icons.py` maps each concept to one Lucide icon (speakers list → mic, timer → timer, motion → hand, vote → vote, amendment → file-pen-line, evidence → file-search, task → list-checks, delegation → flag, bloc → users-round, debate → messages-square, ballot → clipboard-check, house → shield, ladder → trophy, export → download, undo → undo-2, history → history, settings → settings, demo → flask-conical, help → circle-help, and others); an unknown name raises, so typos fail tests. Stance badges now show an icon and the word (yes ✓-circle, no ✗-circle, abstain −-circle, unknown dashed circle) instead of ▲▼● characters. The frozen v2 game is labelled "Classic practice game".

### D-060 Guided committee simulation v3 (amends D-007) — Decided (Phase 6 work package)
A live session now follows nine stages of real procedure: roll call, setting the agenda, opening speeches, moderated and unmoderated caucus, draft resolution introduced, amendments, voting procedure, division, results and debrief. The chair console opens with a guide: a stage tracker, the chair's script for the stage (what to say, with the committee, agenda, number present and majority filled in), what happens next, and the stage's own controls (roll call table; agenda; whip count; debrief link). The scripts are data in `procedure_stage`, one set per rules of procedure (GA and Security Council seeded), editable under Admin → Procedure stages; unknown placeholders show as "…" rather than breaking. Students always see the stage tracker and "What you can do now", answer the roll on their device, and the projector shows the stage. Stage is guidance, not a lock: the existing speakers list, motions and divisions work at any stage, so a chair can run a session their own way.

Group size: works with 1–25 students. Delegations with no student answer the roll as present and vote by the engine, labelled computed (D-041). The demo Security Council has 3 students for 15 members and is tested.

Practice v3: one to three students run delegations against a computed chamber. Each computed delegation gets a hidden mandate drawn once per run from the engine's own distribution for it (with the engine's bloc correlation), so it votes consistently and an amendment moves it exactly as the engine's archetype model says. Students hold up to 5 simulated conversations (the delegation answers in its archetype's voice at its hidden stance; labelled simulated, not real statements), record their reading of each, optionally amend the paragraph's commitments (practice-only tags), set their own vote and call the division. The debrief scores each reading against the delegation's mandate at the time of the conversation, says which delegations the amendment moved, and lists the pivotal votes. Readings are practice-only sources ("Practice lobbying (your reading)", weighted like class intel) and never enter the class's evidence; tested. The frozen v2 game stays linked as "Classic practice game".

### D-061 Whip-count exercise scored against actual votes — Decided (Phase 6 work package)
In the voting-procedure stage the chair starts a whip count on a paragraph, amendment or resolution. Each student in a delegation is given N named delegations to predict (default 5, never their own), spread so every delegation is predicted about equally often (tested: coverage differs by at most one). Predictions can change until the chair opens the vote, which locks them. After the vote, each prediction is scored against the vote actually cast: never against the model (audit §4, D-009). Votes the engine cast for delegations with no student are scored separately and labelled computed. The debrief shows each student's accuracy (the chair sees everyone; a student sees only their own), how the prediction engine did on this vote against the student-cast votes (its probability of passing, how often its most likely vote was right, Brier score and log loss, with a note that one vote proves little), and a hindsight swing analysis: every delegation whose single changed vote would have flipped the result.

Delegate profiles (Statesman, Principled Isolate, Gone Native, Passenger) are kept, re-based per D-009: mandate fidelity compares the student's vote with the evidence-based prediction stored when voting opened (consistent if that vote had at least a 30% chance, against the evidence below 15%, borderline between), shows the probability it used, says "not judged" when the country has no evidence, and the chair can override it with a reason. Coalition is the winning side, the losing side or abstained. Profiles are feedback, not a grade.

### D-062 Onboarding, join cards with local QR codes, in-app help — Decided (Phase 6 work package)
- **First-run wizard** (`/welcome`, coordinator only): create a class; add students by typing names or uploading a roster CSV (a `first_name` and optional `last_initial` column, or one `name` column: any other column such as surname, email or date of birth is ignored and never stored, tested); set up a conference and committee; print join cards. In demo data a fake roster can be generated; in real data that button is refused. First-run setup now lands here, and the dashboard links to it until a class and committee exist.
- **Join cards and poster** (from the class page): class code, the student address and a QR code that opens `/join?code=…` with the code filled in (students still tap their own name). QR codes are made on the laptop by **segno 1.6.6** (BSD-3-Clause licence, read in the wheel's `LICENSE`; pure Python, no network). The address is the laptop's school-network IP, never `localhost`; if the laptop has several networks, set `"join_base_url"` in `data/config.json`.
- **Help**: a Help link in every header opens a dialog with help for the current section (falls back to the /help page without JavaScript); a glossary of 31 MUN and debating terms (plain-English, with a note that rules differ between competitions); a student quick-start; the staff guide rendered inside the app from `docs/staff-guide.md` by a small escaped Markdown converter (tested against script injection).
- **Consistency**: a test now crawls every page and requires each page's `<title>` to equal its `<h1>`, and every page below a section to carry breadcrumbs; the 11 pages that failed were fixed. Empty lists say what to do next.
- **Screenshot gallery** (`python tools/screenshots.py` → `docs/screens/`): 25 key pages at 1366×768 and 390×844 (50 images, about 4.4 MB), built from a realistic mid-lesson state on demo data. Reviewing them found and fixed three real defects: the projector timer's digits sat below the fold (a 1em margin at 9rem type); on phones the navigation and the nine-stage tracker filled the first screen (phones now show only the current stage); and that phone stage label then read "1 of 9" at every stage, because CSS counters skip hidden items (regression test added).

### D-063 Content: motions, carnival and inter-school documents, feedback prompts, a fictional Evatt-style scenario — Decided (Phase 6 work package)
- **Motion bank**: 122 practice motions (92 new, all written for the platform, none copied from a competition): 37 junior, 44 middle, 41 senior, across 15 themes. Admin-editable.
- **Run sheets and MC scripts**: a house-carnival run sheet (pre-event checklist, timing signals, every debate by room with adjudicators, after-the-day checklist) and MC script (acknowledgement of Country, house roll call, housekeeping, each motion read twice, results with house points), and an inter-school run sheet and chairperson's script (roles, order of speakers, reply speeches if the format has them). The document page now lets staff choose the template; it defaults by event kind (carnival → house carnival; competition → inter-school). Templates are data under Admin → Templates.
- **Adjudicator feedback prompts**: 16 prompts across matter, manner, method, reply and overall, shown on every ballot page and editable under Admin.
- **Evatt-style Security Council demo**: "The situation in Veloria", a crisis in a **fictional** state, with 15 members (the 2026 Council as remembered, to be checked), the Security Council voting rule with veto, a draft resolution of 3 preambular and 6 operative paragraphs, and 105 evidence entries (7 issues × 15 members). Every position is invented and stored with the new source type "Unverified demo — invented for practice", whose text says it is not that country's real position. A fictional crisis was chosen so that no real conflict or real country's stance is presented as fact. Tested: the invented vetoes sink the sanctions paragraph (P(pass) < 0.2) while humanitarian access passes (> 0.6).
- **Existing databases**: missing templates, motions and source types are added by key on start-up; anything a coordinator has edited is never overwritten (tested). The Veloria committee is part of the demo dataset; Admin → Data → Reset demo data loads it into an existing demo.

### D-064 Read connections are closed when their thread ends — Decided (Phase 7)
The read-connection pool (D-042) kept a reference to every worker thread's SQLite connection for the life of the server. The thread pool retires idle threads and starts new ones, so connections (each with its own page cache) accumulated through a lesson. Each pooled connection now carries a weak reference to its thread; when a new connection is opened, connections of finished threads are closed. Measured: 200 short-lived threads left 200 open connections before, at most 1 after (`tests/engine/test_db_pool.py`). Soak-test numbers: `docs/phase-reports.md`, Phase 7.

### D-065 Evidence quality: sourced, estimate only, unknown — Decided (Phase 7, audit §4)
The prediction page said "0% unknown" whenever every country had any source, including the unsourced archetype prior, so a prediction built entirely on hand-typed estimates looked fully known. Each country now has an evidence quality: **sourced** (at least one source that is real evidence), **estimate only** (only the archetype model estimate, unsourced notes, invented demo positions or AI estimates; an AI is not a source even when it cites one) or **unknown** (nothing). The prediction page leads with the share of outcome uncertainty that rests only on estimates, keeps the "no evidence at all" share, and shows the sourced share; every country, swing-list row, pivotal vote and debrief profile carries a badge with text and an icon. Tested: the demo GA with only archetype priors and unsourced pack notes reports over 99% "estimate only" (and still 0% unknown); one sourced statement moves that country to "sourced".

### D-066 The offline practice partner is called "Practice negotiation (rule-based)", not AI — Decided (Phase 7, item 4)
The offline `FakeProvider` is a rule-based responder, so calling it an "AI delegation" overstated it. With no school-approved provider active, the nav, page title and heading say "Practice negotiation (rule-based)", the page says "This is not AI." and bot messages carry a "rule-based" label. "AI delegation" and the AI label appear only when a real provider is selected and the school's approval is recorded (`app.ai.ai_live`, the same rule `get_provider` uses). Tested in both states (`tests/api/test_phase7_ai_label.py`). The URL stays `/me/ai-practice` so existing links keep working.

### D-067 Header: one row on a laptop, a Menu button on phones — Decided (Phase 7, items 5 and 6)
At 1366×768 the header wrapped to two rows (122 px); on a 390×844 phone it was 208 px (staff) to 246 px (student) before any content. The account area is now compact: the signed-in name sits above a text-style Sign out (the words "Signed in:" stay for screen readers), and the header bar may use up to 1340 px. Below 701 px the nav and account area sit behind a `<button aria-expanded aria-controls>` Menu button; Escape closes it and returns focus to the button. The button is `hidden` in the markup and shown by `app.js`, so without JavaScript the list simply shows. Measured: 69 px at both sizes for staff and students (`tests/ui/test_phase7_header.py`: one row at 1366 px, at most 130 px at 390 px, keyboard path, axe with the menu open and closed, no-JavaScript fallback). A Lucide `menu` icon was added to the sprite.

### D-068 MUN committee flow v4: an open floor driven by motions — Decided (27 Oct 2026, Ben)
Ben approved the flow in `docs/design/mun-committee-flow.html` with all ten recommendations, and the title **Chair** for the person who moderates a committee. It amends D-060: the nine fixed stages become six (roll call, agenda, opening statements, the floor, voting procedure, debrief). On the floor, motions move the committee between the speakers list, a moderated caucus, an unmoderated caucus (at most 10 minutes per motion; extend by a new motion) and amendment debate, until close debate passes (two-thirds; nine of fifteen in the Security Council). Amendments: private draft → submitted (public, shown as tracked changes) → signatories → the chair brings it to the floor → speakers for and against on their own list → vote → adopted on every screen (or friendly, with no vote). Amendments to amendments are replaced by suggested edits that the sponsors accept or decline. A failed resolution reopens the floor if another draft is ready. Migration 0007 maps running sessions (caucus, draft resolution and amendments → the floor; division → voting procedure) and keeps scripts Ben has edited. Tested in `tests/api/test_phase8_floor.py`, including the upgrade of an old database.

### D-069 Students can raise points and motions from their devices — Decided (27 Oct 2026, Ben)
Recommendation 10 was "motions are spoken, not tapped in". Ben asked for tabs during debate that include voting on unmoderated caucus time and raising points of order, so students can now propose motions (with one-tap unmoderated caucus motions of 3, 5 or 10 minutes) and log points (order, personal privilege, parliamentary inquiry, right of reply) on their devices. The room still leads: the page tells students to raise their placard and say it aloud; the chair decides in order of precedence. One waiting point per delegation; in voting procedure only points of order and personal privilege are accepted. A granted right of reply goes to the top of the current list.

### D-070 Messages between delegations — Decided (27 Oct 2026, Ben)
"Not judged but visible to the chair." Students message other delegations from the Messages tab, like passing notes. Messages are not assessed. Every message is visible to staff running the class, and students are told so on the tab. The chair can hide a message (its text disappears from both delegations' screens and stays in the chair's log). Limits: 500 characters, 10 messages per student per minute, none during voting procedure (the doors are closed). Messages travel on per-delegation live channels (`inbox:<delegation>`, plus `chat:<session>` for staff), so a note doesn't refresh the floor for the whole class. Erasing a student replaces their message text with "[erased]". Safeguarding note for the pilot: messages are between students in one class, in a supervised lesson.

### D-071 Friends and foes sheets and private speech drafts — Decided (27 Oct 2026, Ben)
For each operative clause (the preamble is left out on purpose), each student records every other delegation as friend, undecided or foe, with a short note. Beside it is the engine's estimate, labelled as an estimate with its evidence quality (D-065); the student's reading is never fed back into the model or shown to others. Speech drafts (opening statement, speeches, notes) are the student's own words: the program never writes them, nobody else sees them, and they are deleted when a student is erased. The prepare page puts the country brief, the proposed resolution and the opening-statement pad together before the lesson.

### D-072 Signatories needed: a fifth of the delegations that have students — Decided (27 Oct 2026)
The proposal said "one fifth of the committee (minimum two)". Testing showed that is unreachable in class: computed seats can't sign, and a fifth of the 33 General Assembly seats is 7 while a class may hold only 8 delegations. The threshold is one fifth of the delegations that have students, at least two. The chair can still bring an amendment to the floor early with "Bring it anyway".

### D-073 Live updates never leave a page stale or undo what someone was doing — Decided (27 Oct 2026)
The full suite showed the guided-session browser test failing about one run in five. Instrumented, it was three real bugs in `app/static/js/live.js`, each of which a class would hit: (1) a refresh queued just before a page swap (a boosted form or link) fired into the old, detached copy and the throttle dropped the new copy's refresh, so the student's screen showed the state before the change (here, no vote card); the refresh now targets the region on the page when it fires, and every render carries the event number it was built from (`data-view-seq`), so a page older than the last event the browser has heard of refreshes itself; (2) a refresh closed any panel the person had opened (“Jump to a stage”, “Propose another motion”); open panels are now kept open; (3) a refresh reset a drop-down the person had changed but not sent (pick a stage, then Go); the choice is now kept. After the fix the test passed 40 of 40 runs, and the full suite passed (624).

### D-074 Debating and public speaking is a classroom and preparation tool — Decided (27 Oct 2026, Ben)
Ben: the debating section is for preparation in class, not the carnival. It does two jobs: (1) a **classroom runner** a teacher projects: type the speakers' names for each team (or for a round of speeches), set the speech times, and run it with a big timer; (2) a **prep studio** students use on their own: build a case, rebut the likely opposition arguments for each motion, write prepared speeches from templates, and practise impromptu speaking against built-in topics and timers. Everything written is scored against a rubric. The carnival and tournament tools (Phase 3) stay as they are, lower on the Debating page under "Tournaments and carnivals"; nothing is removed.

### D-075 The classroom runner: one run of show, one timer, projected — Decided (27 Oct 2026)
A **run** is a class debate (two teams, 1 to 4 speakers each, optional reply speeches, optional preparation time) or a **speaking round** (a list of speakers giving prepared or impromptu speeches). The run order is computed from the settings (Aff 1, Neg 1, Aff 2 … then Negative reply, Affirmative reply, as in Australian schools debating; for impromptu speeches, thinking time then the speech). One timer per step counts down, keeps counting into overtime, and shows the bells as colour: green while speaking, amber after the warning bell (default 1 minute before time), red at time. A bell sounds on the teacher's laptop (it can be switched off). The state lives on the server, so a refresh or a second screen shows the same thing; the projector view opens from an unguessable link, like the event projector. Keys on the teacher's page: Space starts or pauses, the arrow keys move between speakers. Each speaker's actual time is recorded. The teacher can quick-score speakers (matter, manner, method for debates; the speech rubric for speeches), pick a winner and leave a comment; students whose names match the class roster see their scores and time on their page.

**Names:** typed names are first names (plus a last initial), at most 24 characters, with no digits or @, so an email or full name can't be stored by accident. A name that matches the class roster is linked to that student (so erasure and the student's own page work); an unmatched name stays only on that run and is replaced with "Speaker N" after one school year (365 days), the same period as the change history.

### D-076 Prep studio: cases, rebuttals against the likely opposition, scored — Decided (27 Oct 2026)
For any motion, a student picks a side and builds a case from a template: definition and context, a one-sentence team line, then arguments in four parts (claim, reasoning, example or evidence, impact). For rebuttal, the student sees the **likely arguments for the other side** of that motion and writes a rebuttal to each in four parts (they say, but, because, so), and can add arguments they expect that aren't listed. Scoring has two layers, kept separate and labelled: a **structure check** the platform counts (which parts have at least a few words: it says nothing about quality), and **rubric scores** for quality, given by the student (self-review) and by the teacher, on two new rubrics: written argument (clarity, reasoning, evidence, relevance) and written rebuttal (fair summary, clash, support, weighing). The new rubrics are found by code, not kind: the rubric table's `kind` check can't be widened without rebuilding a table half the schema refers to.

**Not writing student work:** the likely arguments are one-line starting points written for the platform (like the motion bank), shown so students have something to rebut. The student's own case, rebuttals and speeches are always theirs; the page says the listed arguments are not the only ones and are not evidence.

### D-077 Speaking practice: impromptu, prepared and rebuttal drills, with templates and timers — Decided (27 Oct 2026)
The student practice page has three modes. **Impromptu:** draw a topic from a bank of impromptu topics by year level, choose thinking time (30 s to 2 min) and speaking time (1 to 3 min), plan on a structure card (PREP: point, reason, example, point; past, present, future; problem, cause, solution; three angles), then speak to the timer. **Prepared:** pick one of your own speech drafts, rehearse section by section against its target time. **Rebuttal drill:** a random likely argument from the motion briefs, 30 s to think, 1 minute to rebut aloud. Each ends with the existing self-review against the speech rubric, saved to the practice log the teacher can comment on. The **speech writer** gives prepared-speech templates (persuasive, informative, personal story, tribute) with a prompt for each section, a live word count and an estimated speaking time (130 words a minute, stated on the page), a rehearsal view and printable cue cards. Templates, impromptu topics and likely arguments are reference data editable in Admin.

### D-078 Nothing jumps: scroll and focus survive saves and live updates — Decided (27 Oct 2026, Ben)
Ben: scrolling down and then typing often reset the page to the top; it must be smooth. Measured in the browser (`tests/ui/test_phase10_smooth.py`): (1) a live update could replace the box a student had clicked into before their first keystroke (only typed-in forms held updates back); now any region holding the focused box waits until the student leaves it, and typed words still hold it until they're sent; (2) a link to a new page kept the old scroll position (opened 410 px down); new pages now start at the top; (3) saving a form that returns to the same page keeps the reader where they were, and the confirmation appears as a toast instead of out of sight at the top; (4) every live refresh restores the scroll position. A probe that types into every box in the live regions while the committee changes every 0.7 s found no scroll jump, lost focus or lost text afterwards.

### D-079 Students sign in with a personal code; no phones; absent students never hold anything up — Decided (27 Oct 2026, Ben)
Ben: phones are a hard no; the connection should be a website with a code that already has the student's name built in, and students being away mustn't be a problem. Replaces D-003's class code and tap-your-name list (and with it the device lock and teacher approval of second devices, and the QR codes, D-062). Each student has a six-character code with no 0, O, 1 or I; their card shows their own address (`<laptop>/s/<code>`) and the code to type at `/join`. No list of names is ever shown, so an absent student's name can't be taken. Signing in on a laptop signs that student out of any other (one laptop at a time, safe on shared school laptops). Wrong codes are throttled; teachers can show a code or give a new one (the old one stops working); codes are never exported. In a vote, a delegation whose students are all away (not seen in the session for two minutes) is voted by the engine, labelled computed, like a country with no student; a student who arrives in time casts their own vote instead. Screenshots and the deck use laptop and large-screen sizes only.

### D-080 The app follows the South Oakleigh College design system: white, clean, the College's own colours and type — Decided (27 Oct 2026, Ben)
Ben: the look was murky, earthy and dirty; it should feel clean, intuitive and easy to use, following the SOC design system. Replaces D-058's palette (cream page, near-black brown header, brick maroon). Now, from the design system's tokens: a white ground, College Maroon #621723 leading (buttons, links, current page, table header rows), Green #135728 and Gold #A98B00 in support (gold only for heading bars and rules, never text), ink #262626 and #4A4A4A for text, #F7F7F7 panels and #DDDDDD hairlines. Cinzel for page and section titles and Open Sans for everything else, both served from the laptop (OFL licences in `app/static/fonts/`). The header is white with the crest on white (the design system never puts the logo on maroon); pill buttons as on the College website; the page title carries the website's gold heading bar; the footer is the letterhead's gold hairline over a maroon band. The projector uses the same white ground, and the speech timer uses the design system's on-screen timer colours with ink text. Every text and control pair passes WCAG 2.2 AA (`tests/test_design_contrast.py`, 43 pairs); ink on the timer red is 4.50:1, so the text on it is kept large and bold.

### D-081 The server measures its own memory, so the soak test works on Windows — Decided (28 Oct 2026, local session)
`tools/loadtest.py` read the server's memory from Linux's `/proc`, so on Ben's Windows laptop every sample was empty. Reading the process from outside wouldn't help: a Windows venv's `python.exe` is a launcher, and its PID is not the server's.
- **Fix:** the server's per-minute `STATS` line (written only when `SOC_TIMING_LOG` is set) now includes `rss_mb`, measured inside the server by `app.util.process_rss_mb` (the working set on Windows, `/proc/self/status` on Linux).
- **Fallback:** the load test uses that reading whenever `/proc` gives nothing, and the summary names the source.
- **Machine label:** the summary now names the actual machine (OS and Python version) instead of always saying "cloud build container".
- **Checked on Ben's laptop, Windows 10:** a 3-minute, 30-client run recorded memory every 30 s from the server's own lines (77.5 to 69.1 MB), with 0 lost events and p95 0.47 s.
- **Still to do:** the 90-minute soak on the laptop.

### D-082 Feature freeze; PR #1 merged into main — Decided (29 Oct 2026, Ben)
Ten phases are built and tested, but no real teacher or student has used the platform yet, so that is now the biggest risk. From this point:
- **Allowed:** fixes, security hardening, simplification, and changes that real use (Ben's walkthrough, staff practice runs, the trial) shows are needed.
- **Not allowed:** new features.

PR #1 (`platform-build`) is merged into `main` with a merge commit, so the phase tags and history stay intact. The merge is tagged `feature-freeze`.

From here, work happens on short branches from `main`, one per piece of work, pushed and merged after tests pass. `platform-build` stays on GitHub as history and is not used for new work.

### D-083 Security hardening after the 29 Oct stress test — Decided (29 Oct 2026, Ben)
Five findings, each confirmed by a test that failed on the old code. All five now pass (`tests/security/test_hardening.py`). Full write-up: `docs/security-audit.md`.
- **S-1:** CSV export cells that start like a formula are prefixed with an apostrophe, and the apostrophe is removed again on import.
- **S-2:** the sign-in throttle counts per account **and per laptop**, so no one can lock the coordinator out from another laptop.
- **S-3:** one strict same-site check (`safe_path`, `safe_back`) for every redirect taken from a form or the Referer header. Testing showed the backslash case wasn't exploitable (the framework percent-encodes it); this is for consistency.
- **S-4:** evidence deletion is decided by the evidence itself, never the form: its own committee, and its creator taken from the change log rather than a matching display name.
- **S-5:** flag SVG is rebuilt from an allowlist of plain shapes when pages are drawn, and unsafe markup is refused when saving.

Helpers live in `app/web/safety.py`. Use them for any new export, redirect or stored markup.

### D-084 One student list; tick who's taking part; tournament tools hidden — Decided (29 Oct 2026, Ben)
Ben found setup "jumbled and muddled": every "choose a class" dropdown listed seven demo classes, four of them "carnival groups", although debating is for the classroom (D-074).

His model is simple. Students come and go, and different classes use the platform at different times. A student is entered once and stays; on the day, you tick who is taking part, or add a first-timer. Every activity works with any number of students. Year level sets difficulty, and groups often mix year levels.

**Stage 1 (this change):**
- **Year levels:** each student has an optional year level, `student.year_level`, 5 to 12 (migration 0010).
- **People → Students:** everyone in one list, filtered by year level and name. You can add first-timers (into a default "Students" group, with a year level), change anyone's year level, and print sign-in cards for the students shown.
- **Groups stay in the background.** They're still called classes in the code, and they decide which teachers see which students. The coordinator sees everyone; staff see their groups, so the security model (D-083) is unchanged. Activities don't depend on groups.
- **Tournament and carnival tools are hidden** (`show_tournaments`, off by default). The coordinator can show them again at the bottom of the Debating page; nothing is deleted.
- **Demo:** the demo groups mix year levels. Year levels come from their own random stream, so the rest of the demo data is identical.

**Stage 2 (29 Oct 2026): Start an activity** (`/start`, `app/modules/core/start.py`, button on the Dashboard):
- **Choose the activity:** UNAA (the General Assembly climate pack), Evatt (the fictional Veloria Security Council crisis), a class debate, public speaking, or your own format. Kinds whose module is switched off aren't offered.
- **Choose the students:** tick who's here, grouped by year level with "Tick all" for each year. A name search and a year-level filter only hide students, so anyone already ticked stays ticked. A name that appears twice shows the student's group. First-timers are added inline into the one list and ticked, without losing the rest of the form.
- **Every new student gets a year level** (Ben, 29 Oct), here and on People → Students. Type it after the name ("Sam L, 9", "Sam Year 9"), or choose one year level for everyone typed. A line with neither is refused, and nothing in that batch is added.
- **Difficulty:** junior, middle or senior, or suggested from the median year level of the students ticked (8 or below is junior, 11 or above is senior, otherwise middle, and middle when no year levels are recorded). The level sets speech times and the motions and impromptu topics offered. Every value can still be changed once the activity is open.
- **Any number of students:**
  - **Model UN** shares the delegations out, round robin; countries with no student are voted by the engine and labelled computed (D-079).
  - **Debates** split into rooms of up to eight, all on the same motion. With an odd number, one side has a spare slot.
  - **Public speaking** takes everyone, in rounds of up to 30.
  - **Your own format** is a speaking round that opens straight on its full settings page.
- **Linking and access:** ticked students are linked to their speaking slots by id, not by typed name, so a group can mix students from any group. Staff can tick only students in their own groups, and the activity belongs to a group they can run.

**Stage 3 (30 Oct 2026): In progress and Resume** (`app/modules/core/resume.py`):
- The Dashboard lists unfinished debates, speaking rounds and Model UN sessions this person can run, most recently used first. Each has **Resume** (asks who's here first) and **Open** (goes straight in).
- **Who's here today?** uses the same tick list as Start, ticked with last time's students. On Continue:
  - **Speaking round:** anyone who has spoken, is speaking, or has been scored keeps their place. Students who are away leave the rest of the order, new students go on the end, and the current step stays on the next speaker who is here.
  - **Debate:** an away student's unspoken slot is freed, and new students fill free slots in speaking order. Anyone who doesn't fit is named in the message.
  - **Model UN:** newcomers are given a country. Away students keep theirs, and their country is voted by the engine until they sign in (D-079).
- **Who can resume:** only the people who can open the activity. A finished run must be reopened first, and a closed session can't be resumed.

**Next:** saved groups, D-085.

### D-085 Saved groups; old class-style groups become "Teacher access" — Decided (30 Oct 2026, Ben)
Ben: "there also should be groups that get saved, ie i create a debating juniors group, which i can name ... a tab for both groups, and individual students, while still cutting out the confusing manner of the groups from previous builds".

- **A saved group** (`student_group`, `student_group_member`, migration 0011) is a name plus a list of students. A student can be in any number of groups, which the old classes (one per student) couldn't do.
  - Groups are shared among staff, so anyone can tick one. Only the person who made it, or the coordinator, can rename, change or delete it.
  - Each person sees and ticks only the members they could see anyway. When an owner edits, members they can't see are left alone.
  - Membership goes when a student is erased (`erase_student`).
- **People has tabs:** Students, Groups, Teacher access, and Staff (coordinator only). `/people` is a short overview.
- **The old class-style groups are now "Teacher access"** (`/people/access`). The code still calls them classes, and they only decide which teacher sees which students. They're off the People page and the Dashboard; the Dashboard shows saved groups instead.
- **Start an activity and Who's here today?:**
  - a row of **Tick ‹group›** buttons; these are server-side, so they work without JavaScript and keep everything else on the form;
  - **Save the ticked students as a group**;
  - `/start?group=<id>` opens with a group ticked, from a group's page or the Dashboard.
- **Sign-in cards** can be printed for a group (`/people/cards?group=<id>`).
- **Not changed:** the getting-started wizard still creates a class. MUN committees and debating runs still belong to a class behind the scenes, which decides who may run them.






### D-101 Solo play becomes a one-hour campaign — Direction decided, rules proposed (5 Nov 2026, Ben)
Ben wants solo Model UN to be "an hour long experience" that feels like territory, economy and civilisation games, "with depth, gravity, decision making, unique scenarios", while staying educational. Ben is the overall designer and Claude the lead programmer.

Decided:
- **Solo only.** The live class committee stays procedure-only (D-091).
- **Luck:** event cards and the vote's real uncertainty only; no dice.
- **Guests:** the game is kept on that laptop only, and nothing goes to the server.
- **Structure:** chapters build the resolution, adding, rewording and cutting clauses; a summit then votes, with higher-frequency decisions.
- **Clauses:** clause cards, which the student may reword (the engine judges by the commitments ticked, never the words).
- **Winning:** several victory paths (Mandate, Consensus, Architect, Kingmaker).
- **Meters:** Influence, Respect, Trust (per country) and Expertise.

Ben approved rules v0.1 on 5 Nov 2026. His answers: the title is "The Session"; music as well as sound effects (synthesised, off by default); teachers see results (paths and grades), never words; today's single-clause game stays as "Quick vote".

**Phase 1 is built.**
- The rules engine (`app/modules/sim/campaign/`) gets every country's position from the real vote engine (a test checks this).
- The balance harness is `tools/campaign_sim.py`.
- The engine tests are `tests/engine/test_campaign.py`.

The simulation's 2,400 games led to rules v0.2 (`docs/design/solo-campaign.md` section 17):
- the working group decides on changes to other people's text;
- rivals move first each turn;
- rivals are never permanent members where there's a veto;
- instructions have three parts;
- Architect is harder;
- Standard has five turns a chapter.

Measured on Standard:
- 63% of competent bots reach silver or better;
- each style wins gold on its own path 34–69% of the time;
- no action is more than 19% of a winner's moves;
- the hardest scenario is at 25%;
- no games stuck.

There is no interface yet. Phase 2 waits for Ben's calls on scenario labels, a Security Council fallback and Architect.

**Phase 2, the shell (5 Nov 2026).**
- **Pages:** `/session` (title: New session, Continue, Quick vote, Settings), `/session/new` (six setup steps: scenario with its Beginner/Standard/Expert label, country on the map with how hard the seat is, length, rivals, the victory path, the briefing), and the game page on the war-room board (meters, the chapter card, news and procedure moments, your secret instructions, the draft, rivals, the record, End turn, a pause menu).
- **Saves:**
  - A signed-in student's session is a `campaign_save` row (migration 0020), only theirs, deleted by `erase_student`. Each move updates the row and logs a one-line note, not a copy of the game.
  - A guest's session is kept in their browser (up to three) and signed with an HMAC. The key lives in `app_setting.campaign_key`, and the signature covers numbers as a browser keeps them (0.0 as 0).
- **Settings:** sound, music, the room, motion, text size and the summit timer, kept in the browser; sound and music are off by default.
- **Sound:** `session-audio.js` synthesises every sound (no files), and every effect has a caption.
- **Links:** "Play solo" in the student menu, the sign-in page and the landing page now open The Session; Quick vote (`/play`) stays alongside.
- **Not yet:** the actions (lobby, propose, amend and the rest, phase 3) and the summit screens (phase 4).

**Phase 3, the moves (5 Nov 2026).**
- **The side panel has four tabs:**
  - **Brief:** the chapter's goal as a checklist, the news, your instructions, and each regional group with how many lean your way.
  - **Draft:** each clause with its chance of passing now, Amend (tick commitments: one addition and one removal at a time), Strike, and Divide and Merge once unlocked. The drafting table lists the clause cards, which can be proposed in the student's own words.
  - **Delegations:** a country chosen from the map or a list. It shows its lean, Trust, goodwill and whether it has signed, with Lobby (the reply appears as a quote), Read the file, Promise, Call in a favour, Ask to abstain (permanent members in the Council), Ask to sponsor or sign (last chapter), and Predict their vote. Side events and Bloc whip are here too.
  - **Record:** the rivals and every move.
- **Two new panels:**
  - **Country file:** each commitment with the country's position, its red lines and its sources. It says "estimates from the sources" for real issues and "invented for practice" for fictional scenarios.
  - **Skills tree:** four branches.
- **The map:** tokens light up as you and the rivals lobby them (moves record the country they're about), show Trust as a green or red frame, and show your endorsed groups.
- **Feedback:** each move has a sound. A group won or lost plays a fanfare or a sting.
- **Not yet:** the summit (phase 4).

**Phase 4, the Summit (5 Nov 2026).**
- **Tabs:** at the summit the side panel shows The Summit and the Record.
- **Opening speech:** choose Firm, Open or Bridge. There's a box for the student's own words, for practice only, never saved or marked.
- **Each clause:** shown with its chance of passing, whose it is, and any promise riding on it. A rival's floor amendment appears as a card. The decision comes first:
  - stand firm, or let the amendment go to a vote;
  - a last offer (2 Influence);
  - call in a favour;
  - accept the amendment as friendly (+1 Respect);
  - a point of order (with the skill).
  
  Then the vote.
- **Timer:** with it on (Settings), the Chair calls the vote after 20 seconds and casts the student's vote by their stance.
- **The vote sweeps the map** west to east, each token turning yes, no or abstain, then ADOPTED or REJECTED is stamped over the map, with a fanfare or a sting.
- **The resolution as a whole:** what survived goes to a final vote.
- **Presidential Statement (Council):** a failed resolution offers a statement with the commitments ticked.
- **The result:** the medal for the chosen path, the grade on all four paths, the predictions, the promises, the endorsements, Respect and Expertise. The full debrief is phase 6.

**Phase 5, scenario content (5 Nov 2026).**
- **The format:** a pack may have a `campaign` section with up to 10 extra clause cards (1–3 of the pack's tags each, written as operative clauses) and up to 8 events of its own.
  - Each event has one effect: `ap`, `lobby_cost`, `influence`, `region_mood`, or the new `spotlight` (delegations that support a commitment warm to whoever champions it).
  - The validator, `_template.json` and `docs/pack-authoring.md` cover it.
  - A plain commitment card is added only for a tag no card offers.
  - A scenario's events come up about as often as the general ones.
- **Real topics:**
  - On a real topic an event happens inside the negotiation (a regional group meets, a capital's instructions, an expert briefing, a side event, a co-sponsor wavers). It never invents a real-world event, figure or person, and it is labelled "Hypothetical".
  - The pack guide's ban on invented news for real topics stands.
- **Content:** all eight scenarios have 8 cards and 6 events each.
  - Six were written by helper agents (Sonnet) and two by Claude after an agent's edits didn't land.
  - Every event was read for invented facts.
- **Balance:** re-measured with the content (section 19 of the design doc).

**Phase 6, learning and the debrief (5 Nov 2026).** Ben: "make it as fun, deep and enjoyable as possible … really lean on the Civ but MUN with old school Monopoly graphics and animations. 60 min game should be dynamic".
- **The Almanac** (`/session/almanac/<scenario>`, open to all; from the title screen and the pause menu): how a vote is decided (the model's position from each country's stated positions, the goodwill pulls, endorsements and the hidden mood), procedure, the four paths, the skills, and every country file with its sources or its "invented" label.
- **Tips:** each part of the game is explained the first time it's met: instructions, meters, the map, a delegation, the draft, regional groups, ending a turn, skills, the summit. They're on by default ("Show me how to play as I go" at the briefing, and in Settings), can be turned off, and the ones seen are remembered on the laptop.
- **The debrief dossier:**
  - **Rank:** a diplomatic rank from the four grades together, Attaché to Special Envoy of the Secretary-General, with the points to the next.
  - **Medals:** the four paths as coins.
  - **The session in numbers:** a graph of Influence, Respect and support, turn by turn (the engine now records a snapshot each turn).
  - **Title deeds:** each clause as a Monopoly-style deed, held by its author, with its vote and stamped Adopted or Struck off.
  - **Turning points:** taken from the record.
  - **What your diplomacy did:** the delegations whose vote your goodwill turned.
  - **Why each delegation voted as it did:** the model's position, your pull, the rivals' pull, the group's pull and the mood, all as pushes on the same scale.
  - **What to try next time:** for each path.
- **The board:**
  - **Spheres of influence:** each delegation's land takes your colour when it's likely to back your draft, or red when it's likely against and leaning to a rival.
  - **Envoys:** a brass token (red for a rival's) travels across the map from whoever made a move to the delegation it was about.
- **Teachers:** Model UN → "See their results" (`/session/results`) lists their students' finished sessions: scenario, country, path, the grade on each path, the result and predictions. Never their words.

### D-100 The speech coach beside every speech box — Decided (5 Nov 2026, Ben)
Ben: "there should be some stats and visual add-ins that makes speeches easier to write. some things such as word count, expected speaking time, repetitive language indicators, lists of persuasive techniques … keep the platform clean, easily set-up and intuitive … as pretty and fun/interactive/clear as possible." He chose:
- every speech box, "togglable so it doesn't feel like a constant tutorial", plus Model UN phrases to click in ("addressing other honourable delegates etc.");
- a coach panel beside the writing;
- reading aloud with the laptop's voices only;
- teachers seeing it read-only.

- **Where.** The coach is beside:
  - prepared speeches (`prep_speech.html`);
  - debate speeches (`prep_case.html`);
  - Model UN opening statements (`floor/prepare.html`) and drafts (`chair/live.html`, the My speech tab);
  - read-only, the teacher's views of a speech and a case.
- **What it shows.**
  - A time dial at 110, 130 or 150 words a minute against the target: the speech's own target length, or an "Aim for" choice remembered per page. The default pace, 130, is the server's estimate.
  - Words, sentences, words a sentence, and a Flesch–Kincaid year level, labelled as an estimate.
  - For a speech in parts, time in each part.
  - Check: repeats (content words used 3 or more times), fillers, sentences over 30 words, and repeated sentence starts. Model UN adds first person.
  - Techniques: 12 general ones, plus rebuttal and the team line for debating and diplomatic address and the resolution for Model UN. Each has what it does and an example, a "Used ×n" tick, and click-to-show.
  - Marks in the writing, and minute markers.
  - Phrases (Model UN procedure; debate signposts and rebuttal; speech openers and closers) added at the cursor, with "…" selected for the student's own words.
  - Listen: speech synthesis with `localService` voices only. The button is hidden when there are none.
- **How it works.**
  - The data is `app/web/coach.py`: patterns that read the same in Python and JavaScript, tested in Python against their own examples. The panel is `_coach.html` (`coach_layout`, a call block round the form; boxes marked `data-coach-text`), the script `coach.js`, and the styles are under "the speech coach" in `app.css`.
  - Marks are drawn on a copy of the text behind a transparent text box, so the student's text, cursor, autosave and maxlength are untouched.
  - Nothing is stored on the server. On the laptop it remembers only whether the panel is open, the pace, the marks shown and the aim.
- **Honesty and privacy.**
  - It never writes the speech: the phrases are the set formulas of procedure and signposting, with gaps.
  - The panel says the techniques are spotted by simple patterns and can be wrong, and that the time is an estimate.
- **Colours:** four pale mark tokens (`hl-repeat`, `hl-filler`, `hl-long`, `hl-tech`), each checked for ink text at AA.
- **Tests:** `tests/api/test_coach.py` (every pattern against a yes and a no sentence, the config per kind, the panel on each page, read-only for staff) and `tests/ui/test_coach_ui.py` (counts, marks lined up with the text box, hide and stay hidden, phrases at the cursor with the country, teacher marks, axe).

### D-099 One front door for setup; single player on the board, for guests too — Decided (5 Nov 2026, Ben)
Ben: setup "still has some remnants of previous iterations", "the process for setting up still isn't completely optimal or streamlined. setting up sessions for anything should be easy, straightforward and self explanatory", "I don't want anything still looking sloppy". And single player "with board game, pushed through to the student login section (it shouldn't require a code to use and should be available as guest as well. (although with login used it should be able to save progress etc)". He chose: the one-front-door setup ("with the options of which students are participating, and then the option to turn that participation into a saved group"); the demo rebuilt the new way; nothing kept for guests; the full board table.

- **One front door.** **Start** is the only place to set anything up, in three steps:
  1. The activity, as four cards: Model UN, class debate, public speaking, your own format. Only that activity's options then appear: for Model UN, the scenario cards (every pack plus the UNAA climate conference) and how countries are given out; the motion for a debate; the topics for speaking.
  2. Who's taking part, with "Save these students as a group for next time" right there.
  3. Difficulty, as chips with the suggested level shown.
  - "UNAA" and "Evatt" are no longer separate choices. They still work in old links and forms: `unaa` means the climate conference, `evatt` means Veloria.
- **The menu.**
  - Staff: Start, Model UN, Debating, People, Admin.
  - The chair console is reached from an activity. Intelligence, calibration and the classic v2 game are linked from Admin.
  - Students: My page, Play solo, Prep & practise. Practice negotiation is linked from My page, with its honest label.
- **Libraries, not setup pages.**
  - **Model UN** lists the scenarios (each with **Run with a class**) and your committees; building a conference by hand is under Advanced.
  - **Debating** lists your class debates and speaking rounds and students' preparation; its start buttons go to Start. Tournament tools sit under Advanced; the old "several practice debates" link is gone, since Start splits big groups itself.
  - The Dashboard shows Start, In progress and Saved groups. The old committee list, task count and quick links are gone.
- **Demo data.**
  - Names come from one list, so no two demo students share a name and nobody shows a group tag ("Aisha R. (Year 8 Debating (demo))" is gone).
  - The duplicate demo "Security Council" committee is gone; the Veloria Council is the demo's Security Council.
  - Two saved groups are added: "Debating Juniors (demo)" and "Model UN club (demo)".
  - The teacher-access groups stay, because the tests rely on them to check who sees whom.
- **Single player on the board** (`app/modules/sim/play.py`, `/play`, `sim/play_game.html`, `play.js`, `play.css`).
  - The war-room table with the world map, flags and tokens.
  - Steps 1–4: read the clause; lobby up to five delegations (click a country or choose it); record what you think each will do; amend what the clause commits countries to; check the whip count; cast your own vote and call the vote. The vote sweeps the map and the seal lands. The debrief scores your readings and shows who your amendment moved.
  - Solo runs open on the clause closest to 50/50.
  - **Signed in:** the game is the student's own solo committee and practice run, saved as they go, and listed under "Your games".
  - **Guests**, from **Play solo as a guest** on the sign-in page and the landing page:
    - The game lives in the browser tab and is sent with each move; the server checks it against the scenario and answers. Nothing about a guest is written down.
    - One shared committee per scenario (`committee.guest_pack`, migration 0019) holds the clauses and positions. It is made by the system the first time, and never listed for staff.
    - Moves are JSON with the CSRF header (`/play/api`); errors come back as JSON.
  - The board's map is now one template (`chair/_board_map.html`) shared by the projector and the game.
  - The practice engine's vote is split into `practice_result` (no writes, used for guests) and `call_vote` (saves).
- **Packs:** Ben considers every pack checked for now.
- **Tests:**
  - `tests/api/test_play.py`: a guest plays and nothing is kept; tampered games are refused; a student's game is saved and theirs alone.
  - `tests/api/test_start_activity.py` covers the kinds.
  - The UI tests pick the Model UN card.

### D-098 Six real-issue scenario packs, written by delegated models — Decided (5 Nov 2026, Ben)
Ben asked for new scenarios "playable in both sec council, and mostly in general assembly", on real issues relevant to high-school students (climate, AI, immigration and so on), with preambles that are "completely low stakes, not really debatable". He asked for the work to be delegated to keep costs down.

- **The packs.** One Sonnet agent wrote each pack, following `docs/pack-authoring.md`:
  - General Assembly: `ga_autonomous_weapons`, `ga_migration`, `ga_ai_governance`, `ga_climate_transition`.
  - Security Council: `sc_climate_security`, `sc_ai_cyber`.
  - All are `"fictional": false`, with no news. Preambles carry no tags.
- **Sources.**
  - Every position comes from a page the agent opened and read; a country without one is left out (unknown).
  - Mostly these are UN voting records: un-project.org, a third-party mirror of UN votes, because the UN Digital Library and press.un.org blocked the agents. The Security Council packs also use the Council's own verbatim records (S/PV PDFs) and, for a few countries, news reports.
  - Two migration positions (Australia, Israel) rest on Wikipedia.
  - A country may now list up to four sources, because one page rarely covers every clause.
- **Playability, measured with the engine (P(pass) by clause).**
  - Three General Assembly packs have close votes: AI governance (0.47–0.98), autonomous weapons (0.41–0.97) and climate transition (0.32–0.66).
  - The migration clauses all lean to passing (0.79–0.92).
  - Both Security Council packs are hard: the best clause is about 0.2. The permanent members' stances are unknown or opposed on most clauses, which matches the real Council (the 2021 climate-security draft was vetoed). Students win by lobbying and amending.
- **Solo runs** now start on the clause the engine finds closest to 50/50 (`packfile.closest_vote`), not the clause with the lowest average support, so a Security Council run doesn't open on a certain veto.
- **Before students see them**, a teacher checks each pack as the guide says. Its `author` field reads "to be checked by B. Gough".

### D-097 Play Model UN alone; scenario packs as data files anyone can write — Decided (4 Nov 2026, Ben)
Ben: "let me know if there is a way to play the MUN game solo. If not make a way. furthering that, develop a template for new packs in the game, as i will end up delegating this to lesser models and other engines".

- **Solo before this:** only partly possible. The Practice committee (one to three students against a computed chamber) needed a committee the teacher had already set up for the class. A full live session needs someone in the Chair.
- **Solo now:** Practice committee → **Play a scenario on your own**. A student picks a pack and a country. The platform makes them their own committee from the pack (`committee.solo_student_id`, migration 0018; only that student can open it, through the roster of D-094). It then starts a practice run on the first operative clause, where every other country is played from its positions. From the same page the student can run the other clauses. Solo committees are left out of the teachers' committee lists.
- **Packs are data:**
  - One JSON file per scenario in `app/db/seed/packs/` (format 1). `app/modules/mun/packfile.py` validates, lists and installs them. A file starting with `_` is a template and is never offered.
  - `veloria.json` (the D-063 Evatt demo) is the reference pack. `load_evatt_scenario` now installs it, with identical content.
  - Teachers can pick any pack under Start an activity → Options → Model UN scenario.
- **For delegated authors:** `docs/pack-authoring.md` covers the rules, every field, how to write good tags, clauses and positions, a ready-to-paste prompt for another model, and a teacher's check before a pack goes live. The blank template is `app/db/seed/packs/_template.json`. `python tools/validate_pack.py <file>` lists every problem in plain words, including leftover `REPLACE` placeholders. `tests/api/test_packs.py` installs every pack in the folder, so a broken pack fails the suite.
- **Honesty rules the validator enforces:**
  - A fictional crisis's positions are stored as "Unverified demo". A real topic's positions need a source link per country and are stored as estimates from that source (`ai_estimate`); without a source, a position must be left out.
  - Breaking news is allowed only for fictional crises.
  - No markup and no links in text.
  - A Security Council has exactly 15 members including the five permanent members.
  - Country codes must be ones the platform knows.
- **What a person still checks** (the guide says so): no real people, no thinly veiled real conflict, sources match, language fits the year level.

### D-096 Scoring: Model UN counts up from 0; debating marks are the teacher's — Decided (4 Nov 2026, Ben)
Ben: "with debating it will all be manually inputted etc, and MUN should be starting at 0 and counting up". An agent assessed the options. Ben chose "automatic + my awards" for Model UN and "teacher-only + manual house points" for debating.

- **Model UN contributions** (`app/modules/mun/points.py`). Every student starts each session at 0. Points are counted from the session's own records each time they are shown, so a correction corrects itself. They fall into four strands.
  - **Points per action:**
    - answering the roll +1;
    - a speech given +2 (up to 3 a session);
    - a point the Chair took +1 (up to 2);
    - a motion the committee took up +1 (up to 2);
    - seconding +1 (up to 2);
    - a submitted amendment +2 (up to 2);
    - signing an amendment +1 (up to 3);
    - sponsoring an amendment that was adopted +2 (up to 2);
    - each correct whip call on a student-cast vote +1 (up to 5).
  - **Strands:** speaking, procedure, negotiation, reading the room.
  - **The Chair adds +1 to +3** with a reason the student sees (Chair → Contributions; `mun_award`, migration 0017). Withdrawing an award removes it.
  - **Who earns:** points go to the student who acted, so co-delegates are counted separately. The engine, absent students and casting the country's vote earn nothing.
  - **Who sees what:** each student sees only their own ("Your contributions" on the live page). The Chair sees everyone. There is no leaderboard and nothing per student on the board (D-091).
  - **The point values and caps** are a first setting, in `points.RULES`. Change them there.
- **Debating.**
  - Only staff running an event enter its ballots; a student adjudicator now gives their marks to the teacher.
  - The ballot shows each speaker's total, each team's total and the margin as marks go in. This is display only; the server works them out again.
  - House points are entered by hand on the results page. The "award from rules" buttons are gone, and the routes refuse them.
  - Unchanged: the higher total wins (D-046); a winner is chosen only when totals are level.
- **Privacy:** `mun_award` holds staff remarks about a student, so `erase_student` deletes them.
- **Tests:** `tests/api/test_scoring.py`. The phase 3 tests were updated for teacher-only ballots and manual house points.

### D-095 "My country": a student's alignments and information, open at will — Decided (4 Nov 2026, Ben)
Ben: students "should be able to togle up their countries alignments and information at will. it shouldn't just be seen once."

- **A panel above the live tabs, on every tab.** "My country: France" opens and closes whenever the student likes, and stays as they left it on that laptop (`details[data-remember]` in `app.js`, stored in the browser only). It shows:
  - the flag;
  - the UN regional group;
  - a permanent seat, with what that means ("a No from France is a veto");
  - who the student shares the country with;
  - every bloc and alliance the country belongs to, with the other countries in this room that share it;
  - "possible partners here";
  - links to the full country brief and the friends and foes sheet.
- **Honesty.**
  - Likely leanings come from the platform's model (the country's archetypes). They are labelled "estimate", with a note that they are not the country's stated position.
  - Alignments carry the same "entered from memory, not yet checked" note as the map until someone checks them in Admin.
- **Code:** `app/modules/mun/mycountry.py` (`card`), the panel in `chair/live.html`; tested in `tests/api/test_country_choice.py`.

### D-094 Students can choose their country when the Chair allows it — Decided (4 Nov 2026, Ben)
Ben: "students should have the ability to pick which country they want to be if the chair allows it (or still be random or assigned by chair)".

- **Three ways, chosen when the activity starts** (Start an activity → Options → Model UN countries), and changeable during the session from the chair console:
  - **At random** (the default): today's students are seated at random, always into one of the emptiest countries, so countries fill one student each before any has two. (Before this, /start seated students in ISO-code order, so the same countries always went first.)
  - **Students choose:** each student picks a country on their live page. The chooser shows each country's flag, regional group, permanent seat, alignments (marked as not yet checked) and who already holds it. A student can change their mind until the Chair closes choosing; anyone who hasn't chosen is then seated at random.
  - **The Chair assigns them:** as before, on the committee page, which now lists today's students as well as the group's.
- **Up to four students per country** (`choice.CAP`). The first to take a country is head of delegation and casts its vote (D-088). If the head moves to another country, the next student holding the old one becomes its head.
- **Today's list** (`committee_roster`, migration 0016) records who was ticked for the activity, by student id only. It lets a student open the live session, and see it under "Live now" on their page, before they have a country. Erasing a student removes them from it (`erase_student`).
- **The Chair's card** at the top of the console shows the way in use, whether choosing is open, and who is still without a country. Its buttons are Close choosing (seat the rest at random), Let students choose, Seat them at random, and Assign countries yourself. The board fills each token with the student's name as they choose.
- **Code:** `app/modules/mun/choice.py`; the student's chooser is `chair/_choose_country.html`; the Chair's card is `chair/_chair_countries.html`; tests are in `tests/api/test_country_choice.py`.

### D-093 Every country's flag; tokens carry flag, regional group and alignments — Decided (2 Nov 2026, Ben)
Ben: "make sure each country has a flag and other symbolism attached to them, eg a marker of their allignment"; the board "is merging into a civ, monopoly, risk hybrid looking board which i am happy with", and "please do ensure all spacing is perfect". He approved downloading a flag set ("yes download them, and stylise them to fit the rest of the theme of model UN gravitas and authority with the general style of the map").

- **Flags for all 195 countries.** Only 31 had one. The flags come from flag-icons 7.2.3 (MIT licence, `app/db/seed/flags-LICENSE.txt`), downloaded from jsDelivr on 2 Nov. `tools/build_flags.py` rewrites each into the plain-shape SVG that `safe_svg` allows (copies instead of `<use>`, first colour instead of gradients, ids prefixed per country so many flags on one page never clash). All 195 pass the filter and were checked by eye on a contact sheet. Rounding path data or transforms bent the coats of arms (Bolivia, Mexico, El Salvador, Serbia), so both are kept exactly. The seed now holds them (`flags.json`, about 1.7 MB). An existing database gets them through `seed_content_updates`: a country with no flag, or still the simple flag from the first pack, gets the full flag; a flag changed in Admin is kept. Seven flags with detailed coats of arms are over 60 KB (Serbia about 300 KB).
- **Styled for the board, not changed.** The flag's design is never altered. On the board it is toned to the map's aged paper (slightly less saturated, warmed), with a cloth-fold shading and a thin dark frame. Everywhere else it shows as it is.
- **Title-deed tokens.**
  - Each token (52×30, placed with room for what hangs below it) has a band along the top in its UN regional group's colour (like the colour group of a Monopoly property), with the country code and ★ for a permanent member.
  - Below the band are the flag and a second line (a name, the roll answer, the vote).
  - Up to three alignment shields hang from the bottom edge, as on a unit in a strategy game. They come from the groupings the map already has (D-090): NATO, EU, African Union, ASEAN, Arab League, BRICS, small island states, G20, least developed countries, most telling first.
  - A long second line is squeezed to fit, not cut.
- **The key.** A parchment cartouche in the bottom-left of the map explains the regional colours, the shields present in this room and the ★. It says the alignments were entered from memory and are not yet checked, which is true of all of them until someone checks them in Admin. It steps aside when the camera zooms in, or if a token in this room would sit under it. The compass moved to the bottom-right.
- **Spacing.**
  - When the camera zooms in, the view moves so that no token is cut in half at the top or bottom edge.
  - Until sound is turned on, the rail keeps clear of the "Turn on sound" button.
  - The board no longer makes a page scroll at any size (it is fixed to the window), which the 320-pixel reflow check now confirms.
- **Tests:** the existing board tests, with the token count updated; contrast pairs for the band colours and shield monograms are in `design.py`.

### D-092 The board: a projector view of its own, in a retro war-room look — Decided (30 Oct and 2 Nov 2026, Ben)
Ben: three views, "student view same as before, teacher view (on their screen only) projector view (extended screen connected like a second monitor would be that is controlled by teacher view)". Whip count only, no debate board. The look: "that old video game feel (monopoly, risk) while still referring to the importance and gravity of a UN". He chose a war-room table, the camera gliding to the speaker, and a debrief showing "the class results, but also how each different country ended up voting, shown visually on the map". After reviewing every stage in screenshots (2 Nov) he asked for the rework list to be fixed, the spacing tidied (the banner looked "a little funky"), nothing rounded or modern ("lavish, well crafted, rich"), and animations between the parts.

- **Separate page.** **Open the board** on the chair console opens `/projector/<token>` in a new window for the second screen. It has no app header, menus or footer (`chair/board.html`, `board.css`, `board.js`). It reads `/projector/<token>/state.json` (`app/modules/chair/board.py`) whenever the session changes and animates the difference. Opening or reloading it plays nothing. The old projector page is still there as **Plain view** (`/projector/<token>/plain`) for weak projectors.
- **The look.** It is laid out on a fixed 1920×1080 canvas scaled to the screen. The table is walnut under a slowly drifting lamp. The banner is UN blue with a brass roundel emblem, the agenda on a parchment ribbon, and brass stage coins. The map is an engraved world (wave hatching, compass rose) in a carved frame with brass corners and a plaque for the map credit. Countries are title-deed tokens. The rail holds parchment documents and brass plates; the speaker gets a brass clock with a hand. Corners are square and edges bevelled; only coins, seals and dials are round. Fonts are Cinzel and Palatino (a system font). Colours are tokens only; `brass-dk` and `un-blue-dk` were added with contrast pairs.
- **Moving between stages.**
  - Most stages: the stage coin flies from the banner to the middle, spinning, over rays of light, and a parchment scroll unrolls between wooden rollers. The scroll shows the stage name, the students' prompt and the stage number in wax. Then the coin flies home, a light sweeps the board and the rail's cards are dealt in.
  - Voting procedure: the chamber doors close with a gavel ("The doors are closed"), then open again.
  - Roll call: the tokens are dealt onto the map.
- **Each stage.**
  - **Roll call:** countries light gold as they answer and are ticked off in ink in a ledger ("P & V" means present and voting, explained under the ledger).
  - **Agenda:** the agenda ribbon unfurls.
  - **Opening statements and the floor:** the camera glides to the speaker and the room darkens around them. Tokens keep their size on screen when zoomed in (at most 1.5 times), so they no longer crowd or clip. The floor's mode (moderated caucus and its topic) is a brass plate in the rail, not a banner over the map. Placards rise over the tokens, now big enough to see.
  - **Voting:** a ringing bell plate; each vote drops a chip onto its token; abstentions are hatched, so they don't look like unvoted land. Vetoes are stamped on the permanent member's token. The result sweeps across the map, the wax seal lands, then settles in the corner of the map and stays while that result is the news.
  - **Debrief:** each country's vote stays on the map with the vetoes. The rail says what happened in words, for example "10 in favour, but vetoed by France and Russian Federation". The news strip and the speaker's spotlight are cleared.
- **Fixes from the review.**
  - The committee's "(demo)" is a "Practice scenario" tag, so the name fits.
  - Countries nobody plays show their short name, not "computed".
  - A caucus topic is shown only during a caucus (console status line, student page and board).
  - The whip card says "locked in" once the vote is open.
  - The speakers list on the floor is the moderated caucus list during a moderated caucus; that is intended.
- **Teacher console.**
  - The Next and Back buttons sit above the script, which folds away.
  - During voting procedure the open vote's tally and **Close voting and announce** are in the guide, and the voting table comes before the floor, so the vote's controls are on the first screen.
  - It is not yet a no-scroll panel for every stage.
- **Student page.**
  - The vote card comes straight after "What you can do now".
  - The placard button shows only while people may speak (agenda, opening statements, the floor).
  - After answering the roll, the buttons fold into "Change the answer".
- **Motion.** Admin → Sound and motion "off", or the computer's reduced-motion setting, stops every animation, including the lamp and the dust.
- **Tests:** `tests/api/test_board.py` (state, the page, the review fixes, vetoes) and `tests/ui/test_board_ui.py` (the board plays a whole session in a browser, with axe).

### D-091 "Now speaking" and "Amendment adopted"; no board-game extras — Decided (30 Oct 2026, Ben)
From the second list of ideas Ben chose 8 (a speaker card) and 9 (the amendment-adopted moment); 12 (the real map) was already built (D-090). He turned down the board-game extras (Chair's Card draws, dice for speaking order, title-deed cards, intro and credits): "all the extra board games ones will take away from core idea too much and make it trivial, rather than learning". The rule from now on is that effects only show the procedure more clearly; they never add game mechanics.

- **"Now speaking"** (projector): when the Chair calls the next speaker, a card reading "Now speaking · Ken, Bahrain" slides up along the bottom for four seconds and goes. It never covers the timer. The speaker timer's own label now uses the same "Name, Country" form (D-086).
- **"Amendment adopted"** (projector): when an amendment is adopted (by vote or as friendly), the clause is shown with its old words struck through and the new words typed in, then the ADOPTED stamp lands with one tap of the gavel. It's driven by the latest adoption since the session opened (`room.last_adopted`).
- **Presentation:** the deck was updated on 30 Oct (version 20, 38 slides) with setup, shared countries, cue cards and teams, the live room, the whip map and the world map.

### D-090 A real world map in the board-game look, with real alignments — Decided (30 Oct 2026, Ben)
Ben approved downloading a real world map, to be drawn in the board-game look, and asked that "real world alliances etc are given or allignment shown somehow". He also asked that none of it "take away from the core idea or core functionality".

- **Map data:**
  - Natural Earth 1:50m country borders, v5.1.2. They're public domain, downloaded from github.com/nvkelso/natural-earth-vector on 30 Oct 2026.
  - `tools/build_worldmap.py` projects them (Natural Earth projection), simplifies them and writes `app/modules/mun/worldmap.json`: 206 countries in 113 KB. The download isn't kept in the repo.
  - The 15 countries too small to draw at this scale (Monaco, Tuvalu, Bahrain and others) are dots at their real positions (`tilemap.LATLON`).
  - The map's credit says borders are simplified and aren't a statement on any dispute.
- **The look:** parchment land raised on a deep-sea table, walnut borders, a brass frame and a compass rose. Each country in the room has a game token pinned to it: its code, a star for the five permanent members, and a second line. Tokens in crowded regions are pushed apart, with a leader line home.
  - Placement is tested never to overlap, and is cached per set of countries: a General Assembly takes 78 ms once, then 0.03 ms.
- **Whip-count map:** now on the real map, with the same three phases as D-089 (calls only, then the class's call, then the real vote with green or red rings).
- **Committee world map** (`/mun/committees/<id>/map`, for staff and the committee's students):
  - Colour by the five UN regional groups (as board territories), or light up any bloc or alliance.
  - Students see "Your country's groupings": each group their country is in, and which countries in the room share it. It's labelled a starting point, not a vote prediction.
- **Real alignments:**
  - The model's blocs (EU, Arab Group, AOSIS, LDC) are listed, plus five alliances kept for the map only in a new table (`alignment`, migration 0015): NATO (32), the African Union (every African UN member), ASEAN (11, with Timor-Leste), the G20 (19 countries) and BRICS (10 full members).
  - They're entered from memory and labelled "not yet checked against the source", with the source linked. They're editable in Admin (Alliances on the map).
  - They're kept out of `bloc` on purpose: blocs feed the prediction model's correlation, its bloc-swing analysis and the "votes with its bloc majority" calibration baseline, and adding NATO or the AU there would have changed predictions. A test checks that they never appear among the blocs.
- **Breaking news scripts** are editable in Admin too (D-089).

### D-089 The live room: gavel, sounds, title cards, vote reveal, whip map, placards, breaking news — Decided (30 Oct 2026, Ben)
Ben chose these from a list of ideas: a gavel sound; sounds between stages; a title card when the stage changes; the vote reveal; the whip-count map; students raising a placard; and breaking news for Evatt. He wanted it to "feel really cool", borrowing the simple, smooth, real look of 1995 board games such as the old Monopoly CD-ROM.

- **The look:**
  - Felt, walnut, parchment and brass, with a red stamp. These are new design tokens, all checked for contrast (`app/web/design.py`).
  - Cards drop in, placards flip, and the stamp lands. Everything is plain CSS and SVG, with no images to licence.
- **Sounds** (`app/static/js/effects.js`): gavel, stage chime, division bell, breaking-news sting, stamp, placard.
  - All are made in the browser with the Web Audio API, so there are no recordings to licence.
  - Every sound shows a caption on screen, for example "[Gavel]".
- **Admin → Sound and motion:**
  - Where sounds play: the projector only (default), the projector and the chair's laptop, every screen, or nowhere. This avoids 25 laptops sounding at once, so I added it, though Ben didn't pick it from the list.
  - Whether things move. A computer set to reduce motion never animates.
- **When effects play:** they're triggered by state the server already has, carried in `[data-fx]` markers (`chair/_fx.html`, `app/modules/chair/room.py`). A change seen while a page is open plays once; opening or reloading a page plays nothing.
- **Gavel:** a Gavel button (two knocks) and a single tap on the chair console. The gavel also sounds when the session opens or closes, and when a vote's result lands.
- **Title cards (projector):** a full-screen card when the stage changes ("Opening statements", with what students do now) and when a division opens.
- **Vote reveal (projector):** each country's placard flips in roll-call order, the tally bars fill, then PASSED or FAILED is stamped with the gavel.
- **Whip-count map** (`app/modules/mun/tilemap.py`, `SIM.whip_map`; projector and `/chair/<id>/whip-map`):
  - Every country is a board tile placed by its approximate centre. A real map would need data downloaded with Ben's OK.
  - While predictions come in, tiles show only how many predictions each country has, never which way, so the projector can't steer anyone's guess.
  - During the vote, tiles show the class's most common prediction. After the vote, they show the actual vote, with ✓ or ✗ and "the class read 9 of 14 correctly".
  - Countries voted by the engine are marked *.
- **Placards** (migration 0014 `placard`):
  - A student presses Raise my placard, and their screen becomes a full-size title-deed card with their country, its code and their name.
  - The chair sees "Placards up" in order, and can Recognise (adds them to the speakers list and lowers the placard), Lower, or Lower all. The projector shows the placards that are up.
- **Breaking news** (`crisis_script`, `crisis_update`):
  - The chair sends the next scripted update for the fictional Veloria crisis (six, seeded), or writes their own.
  - It plays a full-screen news flash with the sting on the projector and every student's screen, and leaves a ticker on the projector and a banner on students' pages.
  - Scripted updates say "Fictional scenario update: these events are invented for practice." The chair's own say "From the chair." A General Assembly has no script, but can take the chair's own updates.

### D-088 Rehearse from cue cards; teacher comments on debate teams; prep overview by group; the head of delegation casts the vote — Decided (30 Oct 2026, Ben)
Ben said yes to rehearsing from the cards, teacher comments on the team overview, and a prep overview. On shared countries: "the head delegate can decide the final vote, but all other mini games, like predicting votes can be individual so that everyone can learn."

- **Rehearse from cue cards** (`/me/cards/<kind>/<id>/rehearse`):
  - The student's own cards, one at a time, against a target time, using the existing timer, bells, arrow keys and clicker support.
  - The target is the speech's own target time. For a case or a Model UN draft, it's the speech's length at 130 words a minute, rounded up to the next half minute (at least a minute).
- **Teacher comments on debate teams** (`/debating/runs/<id>/teams`, migration 0013 `class_run.team_comment_aff` / `_neg`):
  - Both sides' cases and speeches, with the overlap flag and a comment box for each team.
  - Each team sees only its own comment, on its team page.
  - Only staff who can open the run can see the page or comment.
- **Prep overview by saved group, year level or everyone** (`/debating/prep?who=group:<id>|year:<n>|all`; `class_id` still works). It now also shows how much of each case's speech is written and when the student last saved.
- **The head of delegation casts the country's vote** (`chair.service.vote_caster` / `may_cast`):
  - Co-delegates see who casts it, and posting a vote returns 403 with that explanation.
  - If the head hasn't been seen in the session for two minutes, any co-delegate who is here can cast it, so an absence never blocks a vote (as D-079).
  - A country with no head named is voted by any of its students, as before.
- **Already individual:** whip-count predictions and their scores, and friends and foes. A test now checks this for co-delegates.
- **Whip count with few students:** each student predicts up to five other countries, spread to cover as many as possible. Every country without a student is voted by the engine, labelled computed, and scored separately from students' real votes (D-061), so it works with five students or one.

### D-087 Cue cards from any speech; speeches that save themselves; debate teammates read each other's work — Decided (30 Oct 2026, Ben)
Ben asked for something that "will automatically take a written speech, and format it into printable" cue cards, "whether that is dot point or full speech form, with option for both". He also wants a student who does this every lunchtime to save the speech, have it backed up and open it again next club, and he wants it usable in class too. Students in the same debate team should see each other's speech and an overview of their arguments, "to avoid double ups, while being unable to change it".

His answers (30 Oct): usable in class too; a team is the same side of a class debate; dot points are made automatically and then editable; students sharing a Model UN country read each other's drafts (D-086).

- **Cue cards** (`app/modules/debating/cuecards.py`, `/me/cards/<speech|case|mun>/<id>`):
  - **Sources:** prepared speeches, debate cases (the written speech, or the arguments and rebuttals until one is written) and Model UN drafts.
  - **Dot points:** each sentence becomes a point: leading filler ("Firstly,", "I believe that") is dropped and it's cut to 9 words. A test checks that no point contains a word the student didn't write.
  - **Full speech:** sentences are packed into cards of up to 55 words, never split mid-sentence.
  - **Editing:** students can edit any card. Edits are kept per kind of card (`cue_card_set`, migration 0012). The page says when the speech has changed since then, and offers to make the cards fresh.
- **Printing:** four cards to an A4 landscape page, with dashed cut lines, "3 / 8" numbering, and normal or large text.
  - A card that wouldn't fit is split at print time (`fit_for_print`).
  - Measured on 30 Oct with print styles in Chromium: across 1–13 paragraphs, both kinds of card and both text sizes, pages always equalled cards ÷ 4 rounded up, every page was A4 landscape, and no card overflowed.
- **"Write it your way"** (`free` speech template): one box for a whole speech, pasted or typed. A blank line starts a new card.
- **Debate cases have a written-out speech** (`prep_case.speech_text`), with its own cue cards.
- **Saving:**
  - Speech and case pages save themselves every 30 seconds while there are changes, and when the page is hidden or left (`form[data-autosave]` in `app.js`; the server answers 204 to `autosave=1`).
  - The page shows "Saved automatically at …".
  - Prep and practise opens with "Carry on where you left off".
  - Everything is in the database and in the daily backup (`docs/backup-restore.md`).
- **Debate teams** (`app/modules/debating/team.py`, `/me/team/<run>`):
  - A team is the students on the same side of a class debate. Each sees the team's speakers in order, with each speaker's team line, arguments, rebuttals and speech, read-only.
  - The other side's work isn't shown. Students outside the debate get 403. Every edit route still checks the case is the student's own.
  - Arguments from different speakers that share a third or more of their key words are flagged "These might overlap". The page labels this a rough word match, not a judgement.
- **Usable in class:** any student can use all of this (`require_student`, nothing club-only).
- **Privacy:** cue cards are the student's writing, so `erase_student` deletes them.

### D-086 Several students on one country; everything a student does is signed "Ben G, Australia" — Decided (30 Oct 2026, Ben)
Ben: multiple students on one country should each "access everything about their country and all tabs", and messages, speeches "or otherwise" should note the names, for example "Ben G, Australia : Jarryd R, Australia", across the whole page. Some countries have one delegate and others up to four. Numbers needn't be even, and nothing should break if they aren't.

- **Several students per country already worked** (head of delegation and delegates, no limit, and nothing reserved for the head). This change makes it visible and tests it with countries holding 1, 2, 4 and 5 students (`tests/api/test_shared_country.py`).
- **"Name, Country" everywhere a student acts:**
  - messages ("You (Ben G, Australia)" for the sender);
  - points, and the "… is waiting" note for a co-delegate's point;
  - the speakers list and who is speaking now;
  - motions (proposed by, seconded by), on the student page, the chair console, the projector and the minutes;
  - votes ("Australia voted yes (cast by Jarryd R, Australia)") on the student page and the chair's division table;
  - roll call ("Ben G, Australia answered");
  - amendment sponsors, signatures and suggested edits.

  It comes from `app/modules/mun/who.py`. Rows that store the student use that. Motions, amendments and signatures don't, so their author comes from the change log, which already records which account wrote each row; nothing new is stored. Votes, roll-call answers and speakers-list entries now store the signed label when a student acts.
- **One vote per country, as in real Model UN.** Any student holding the country can cast it or change it until voting closes; the page says who cast it.
- **The live page says who you share the country with:** "You are Australia, with Jarryd R and Sam K."
- **Co-delegates' speech drafts:** students holding the same country can read each other's drafts (on the live My speech tab and the prepare page) but not change them. Ben chose this on 30 Oct. Other countries still can't see them.
