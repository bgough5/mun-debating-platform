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
