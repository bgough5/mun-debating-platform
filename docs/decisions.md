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
