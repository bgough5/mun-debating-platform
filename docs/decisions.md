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
