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
