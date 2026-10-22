# Spec — South Oakleigh Debating & Model UN Platform

Status: **approved by Ben, 22 October 2026.** Class size updated by D-022: 1–25 live students per session. Where this spec and `decisions.md` differ, `decisions.md` wins. Decisions and assumptions are logged in `decisions.md`; the evidence behind every "retire" or "keep" is in `audit.md`.

---

## 1. Purpose and scope

One browser-based platform for South Oakleigh's Model UN and debating work, usable live by a class of 25, editable by the coordinator without code, and honest about what it knows.

Three layers:

1. **Evidence and prediction:** support probabilities per country per paragraph or amendment, with the evidence behind each. Pass probability by simulation, sensitivity analysis, and calibration against real outcomes.
2. **Workflow:** whip output becomes lobbying tasks. A resolution workspace with versions and amendments. Chair tools (speakers list, timers, motions, voting, minutes). Debating tools (draws, rubric scoring, ladders, house points, run sheets, MC scripts).
3. **People:** roster, delegation allocation, roles, and each student's pathway from first speech to competition.

**Out of scope:** generating student work. The platform supports preparation and running events. AI features (Phase 4) estimate, coach and role-play opponents, but never write a student's speech, clause or amendment for them. The existing prep-tool notice stays.

## 2. Users and roles

| Role | Who | Can |
|---|---|---|
| **Coordinator** (admin) | Ben | Everything: admin data, classes, rosters, rubrics, procedure rules, templates, exports, demo mode, calibration. |
| **Staff** | Other teachers or chairs Ben adds | Run sessions (chair tools, debating rounds) for classes they're given. No admin data. |
| **Student** | Class members | Join with a class code and pick their name. See public documents and their own delegation's private material, and act in their own role (speak, table amendments, vote, complete tasks). |
| **Viewer** (projector) | Any screen | Read-only live display of a session: speakers list, timer, vote, draw. No sign-in. |

Students are minors. The data held about them is first name (plus last initial if two share a name), class, delegation and role, and pathway records. Nothing else (§8).

## 3. User stories

IDs are stable so later docs and tests can refer to them. Ⓟ marks the phase that delivers each story.

### 3.1 The end-to-end workflow (from real practice)

**W-1.** As a delegation, we table an amendment to one operative paragraph, see which countries and blocs decide whether it passes, get lobbying tasks for those blocs (e.g. the African Group and AOSIS), record what we learn, and see the predicted pass probability update before we introduce it. Ⓟ1 (single user), Ⓟ2 (shared)

Acceptance:
1. Choose resolution → operative paragraph → "Table amendment" (add, delete or replace text). The amendment is stored against that paragraph version with sponsors.
2. The prediction panel shows P(pass) for the original paragraph and for the amended one, each with a 90% interval and the voting rule used.
3. The swing list ranks countries and blocs by how much moving them changes P(pass). Each row shows its evidence and how stale it is.
4. "Create lobbying tasks" turns the top swing blocs and countries into tasks, assigned to delegation members, each with its target, the amendment and a talking-points field.
5. When a student records new evidence (e.g. "AOSIS chair indicated support if a review clause is added", source: conversation, date), the prediction updates and the change is logged.
6. After the vote, the actual result is recorded and stored next to the prediction for calibration.

### 3.2 Coordinator

- **C-1** Ⓟ1 Create a conference (name, dates, committee, voting rule) and allocate delegations to students.
- **C-2** Ⓟ1 Edit countries, blocs, bloc memberships, committees, voting rules, rules of procedure, rubrics and templates in admin screens, with no code.
- **C-3** Ⓟ1 Import and export any table as CSV. Export documents to Word and PDF.
- **C-4** Ⓟ1 See and restore any earlier version of any document. Undo my last change.
- **C-5** Ⓟ1 Switch to demo mode (separate fake dataset) to train staff without exposing real students.
- **C-6** Ⓟ1 Record actual votes after a conference and see the calibration report: Brier score, reliability table and sample size, against simple baselines.
- **C-7** Ⓟ2 Create a class, get a class code, see who's connected, lock claimed names, release a name, remove a device.
- **C-8** Ⓟ3 Set up a debating event: teams, rooms, adjudicators, rounds, house points rules.
- **C-9** Ⓟ5 Download a backup and restore it on another machine.

### 3.3 Student

- **S-1** Ⓟ2 Join from any school device by typing a class code and tapping my name. No password, no install.
- **S-2** Ⓟ2 See my delegation, my role and my tasks.
- **S-3** Ⓟ2 Draft and edit the paragraphs my delegation owns. Others' paragraphs I can only amend.
- **S-4** Ⓟ2 Add evidence about a country's position, with a source. It shows as "student intel", not fact.
- **S-5** Ⓟ2 Get on the speakers list, see my turn coming, and vote in a division.
- **S-6** Ⓟ3 See my debating scores against the rubric, and my pathway progress.
- **S-7** Ⓟ4 Practise against an AI delegation clearly labelled as AI, with positions labelled as estimates.

### 3.4 Chair or staff running a session

- **CH-1** Ⓟ2 Run a speakers list (add, reorder, next, yield) with a timer the projector shows.
- **CH-2** Ⓟ2 Run timers that can be paused and extended. Extension is an accessibility requirement.
- **CH-3** Ⓟ2 Entertain motions from a configurable list (moderated caucus, unmoderated caucus, close debate…) and put them to a vote.
- **CH-4** Ⓟ2 Run a division under the committee's voting rule (GA simple majority; Security Council 9 votes with no P5 veto) and record the result.
- **CH-5** Ⓟ2 Minutes are generated automatically from session events. I can edit them, then export.
- **CH-6** Ⓟ2 If my laptop browser closes or drops, I reopen the page and I'm back in control of the same session.
- **CH-7** Ⓟ3 Generate a debating draw, enter ballots against a rubric, publish the ladder, update house points, print the run sheet and MC script.

## 4. Requirements that cut across everything

| # | Requirement | How it's met |
|---|---|---|
| R1 | Runs in a browser on any school device; no installs for students | Server-rendered HTML; works without JavaScript for reading, and JS enhances live features |
| R2 | Configurable things are data | All lists, rules, rubrics and templates are database tables with admin screens and CSV import/export (§6) |
| R3 | Autosave, undo, version history | Every edit is an event in an append-only log. Documents keep full version chains; undo reverts the last own event |
| R4 | Destructive actions confirm | Delete or reset needs a confirmation that names the item. Deletes are soft (restorable) for 30 days, then purged |
| R5 | Export PDF, Word, CSV | CSV via `csv`, Word via `python-docx`, PDF via the browser's print-to-PDF from print stylesheets (no server PDF engine) |
| R6 | Demo mode | A separate database file seeded from a fake-data generator. A banner on every page says "DEMO". It can never be switched to while real data is open |
| R7 | Accessibility from the start | WCAG 2.2 AA target (§9) |
| R8 | 1–25 live students per session (25 is a hard cap); every activity works with fewer | Server enforces the cap. Countries or roles without a student are filled by computed delegations, clearly labelled. Load-tested with 30 connections (25 students + staff + projector); small-group tests with 1, 2 and 3 students (D-022) |
| R9 | Foolproof | Chair reconnect, autosave, and the server owns all state and scores. Clear errors in plain English. No dead buttons |

## 5. Prediction engine (Layer 1)

### 5.1 What it predicts

For a **target** (a paragraph version, an amendment, or a whole draft resolution) in a **committee** with a **voting rule**, it predicts, for each voting country, P(yes), P(abstain), P(no). From those it derives:

- **P(pass)** by Monte Carlo simulation under the voting rule, with a Monte Carlo standard error and a 90% interval on the yes count.
- **Swing ranking**: for each country and bloc, ΔP(pass) if it moves one step toward yes, weighted by how uncertain we are about it.
- **Amendment comparison**: ΔP(pass) for each tabled amendment against the original, plus which countries move.
- **Unknown share**: how much of the outcome rests on countries with no evidence. This is shown, not hidden.

### 5.2 Model

The model is an ordered latent score per country, deliberately simple enough to explain to a student:

```
μ(country, target) = prior(country, target) + Σ evidence shifts
vote latent        = μ + bloc shock (shared within bloc) + individual noise
yes if latent > c_yes;  no if latent < c_no;  else abstain
```

- **Priors** come from up to three sources, each shown separately:
  1. **Archetype prior.** The existing `stanceOf` raw score, ported to Python unchanged (no bucketing). Labelled "model estimate (archetype)".
  2. **Bloc prior.** The bloc's stated or historical position, weighted by bloc cohesion.
  3. **Voting-history prior** (Phase 4). Similarity of past recorded votes on resolutions with the same tags.
- **Evidence items** each shift μ by a signed amount set by their type and strength (§5.3).
- **Bloc correlation.** Members of a bloc share part of their noise, so the simulation doesn't assume 30 independent coin flips. Ignoring correlation makes P(pass) look far more certain than it is.
- **All constants are data, not code:** weights, noise scale, cut-points c_yes and c_no, and cohesion. They are stored per model version and tuned only by calibration (§5.6).
- **No evidence and no prior means unknown.** That country is shown as "unknown" with a wide default distribution, never as a confident number.

### 5.3 Evidence

Each item records: country (or bloc), what it's about (target, paragraph or tag), direction (support / oppose / conditional), strength, **source** (URL or citation), **source type**, date of the statement, date recorded, and who recorded it.

| Source type | Example | Default weight | Shown as |
|---|---|---|---|
| Recorded vote | UN vote on a similar resolution | High | "Voting record" |
| Official statement | Statement in GA debate, national policy | High | "Official statement" |
| Treaty status | Ratified or not | High | "Treaty status" |
| Bloc position | AOSIS or African Group communiqué | Medium | "Bloc position" |
| Class intel | What a delegate said in caucus | Medium (at conference) | "Student intel" |
| Model estimate | Archetype prior | Low | "Model estimate" |
| AI estimate | AI-suggested position (Phase 4) | Low, **only with ≥1 source**; otherwise stored as unknown | "AI estimate — verify" |

Nothing is ever displayed as fact without a source. Evidence older than a configurable age is flagged as stale.

### 5.4 Voting rules (data)

| Rule | Passes when | Tie |
|---|---|---|
| GA simple majority | yes > no among members present and voting (abstentions don't count) | Rejected |
| GA two-thirds (important questions) | yes ≥ ⅔ of yes + no | Rejected |
| Security Council substantive | ≥ 9 yes **and** no P5 member votes no (a P5 abstention is not a veto) | n/a |
| Custom | Configurable threshold, denominator and veto list | Configurable |

Evatt (UN Youth Australia) is a Security Council simulation with 15 members. The UNAA conference used a 31-delegation General Assembly. Both are needed from day one, which is why rules are data.

### 5.5 Determinism and tie-breaking

- The simulation uses a seeded generator; the seed is stored with each prediction. The same inputs and seed must give byte-identical output.
- Every ranking breaks ties by score (descending), then country ISO-3 code (ascending). Sponsorship ties break by earliest sponsorship sequence number (existing rule).
- Each prediction snapshot stores the model version and a hash of its inputs, so a past prediction can be reproduced exactly.

### 5.6 Calibration

- Each prediction is stored as a snapshot. After a vote, the coordinator records the actual result per country.
- Reports: multi-class Brier score, log loss, and a reliability table (predicted bands against observed frequency). Each shows **sample size** and a bootstrap interval.
- Every report compares against baselines: "everyone votes with their bloc majority", "everyone votes yes", and the archetype prior alone. If the model doesn't beat the baselines, the report says so.
- There are two separate targets, because they are different questions: **conference** outcomes (how student delegates actually voted) and **real UN** outcomes (backtesting priors on historical votes, Phase 4).
- Honest limit: one conference yields a few hundred country-votes at most. Early calibration will be noisy and the report must say so.

### 5.7 Data sources for priors (to verify before use)

| Source | Coverage | Status |
|---|---|---|
| UN Digital Library (Dag Hammarskjöld Library) GA voting dataset, CSV | Recorded GA resolution votes, 1946 to 2025 | **Licence not yet confirmed.** Excludes votes on individual paragraphs and failed drafts, so it gives resolution-level priors only, not paragraph-level. |
| Voeten, *UN General Assembly Voting Data* (Harvard Dataverse) | GA roll calls; widely used in research | **Licence not yet confirmed** |
| SWP/GESIS GA resolutions with issue categories | Resolutions with topic coding | Older version listed as CC BY 4.0; current version unconfirmed |
| Bloc membership (regional groups, AOSIS, African Group, G77, EU, Arab Group, LDCs) | Public lists | Entered by hand as reference data, each with a source |

Most GA resolutions are adopted without a recorded vote, so recorded-vote data over-represents contested issues. The priors will carry that bias and the UI will say so.

### 5.8 Tests required (Phase 1 exit)

- **Parity:** the Python port of `stanceOf` reproduces the JS output for all 279 country × clause cells and all 54 amendment cases (fixture generated from the frozen JS).
- **Voting rules:** every rule, including SC veto, P5 abstention, GA ties and the two-thirds edge cases.
- **Determinism:** same seed gives an identical result. Every ranking tie is broken by the documented rule; tested with deliberately equal scores.
- **Calibration maths:** Brier, log loss and reliability bins checked against hand-computed small examples. A perfectly calibrated synthetic dataset scores as calibrated; a deliberately over-confident one is flagged.
- **Unknown handling:** a country with no evidence is reported as unknown and its share of uncertainty is non-zero.
- **Simulation accuracy:** for a case with an exact analytic answer (independent countries, simple majority), simulated P(pass) is within 3 Monte Carlo standard errors of the exact value.

## 6. Data model

SQLite, one file per dataset (real and demo). Plain SQL migrations, numbered. Reference tables (countries, blocs, rules, rubrics, templates) are seeded from CSV in the repo. **No real student data is ever in the repo.**

### 6.1 Reference data (admin-editable)

| Table | Key fields |
|---|---|
| `country` | iso3, name, flag_svg, un_member, p5 |
| `bloc` | id, name, kind (regional group / negotiating bloc), source |
| `bloc_member` | bloc_id, iso3, from, to, source |
| `committee_type` | id, name (GA plenary, GA Third Committee, Security Council…), default_rule_id |
| `voting_rule` | id, name, threshold, denominator, veto_iso3_list, tie_result |
| `procedure_rule_set` | id, name, motions (list with precedence and majority), speaking_time_default |
| `rubric` | id, name, scale, criteria (name, descriptor per level, weight) |
| `template` | id, kind (minutes, run sheet, MC script, position paper), body with placeholders |
| `tag` | id, label, topic (tags are per topic, not one global vocabulary) |
| `archetype` | id, name, blurb; `archetype_affinity` (archetype, tag, value, source) |
| `country_archetype` | iso3, archetype, weight, topic, source |

### 6.2 People

| Table | Key fields |
|---|---|
| `class` | id, name, year, code (rotatable), active |
| `student` | id, class_id, first_name, last_initial (only if needed), active |
| `staff` | id, name, role |
| `session_device` | id, student_id, created, last_seen, locked (no IP address stored) |
| `pathway_milestone` | id, name, order (first speech → … → state final) |
| `student_milestone` | student_id, milestone_id, date, evidence_note |

### 6.3 MUN workflow

| Table | Key fields |
|---|---|
| `conference` | id, name, dates, organiser |
| `committee` | id, conference_id, type, voting_rule_id, procedure_rule_set_id, topic |
| `delegation` | id, committee_id, iso3; `delegation_member` (delegation_id, student_id, role) |
| `resolution` | id, committee_id, title, status |
| `paragraph` | id, resolution_id, kind (preambular / operative), number, owner_delegation_id, current_version_id |
| `paragraph_version` | id, paragraph_id, text, author, created, parent_version_id |
| `amendment` | id, paragraph_id, base_version_id, kind (add / delete / replace), proposed_text, sponsor_delegation_id, status |
| `amendment_support` | amendment_id, delegation_id, kind (sponsor / second / signatory) |
| `evidence` | id, iso3 or bloc_id, target_kind, target_id or tag_id, direction, strength, source, source_type, stated_on, recorded_on, recorded_by |
| `prediction` | id, target_kind, target_id, rule_id, model_version, seed, inputs_hash, p_pass, mc_se, created |
| `prediction_country` | prediction_id, iso3, p_yes, p_abstain, p_no, unknown |
| `actual_vote` | target_kind, target_id, iso3, vote, context (conference / real UN), recorded_by |
| `task` | id, delegation_id, assignee_student_id, target_iso3 or bloc_id, amendment_id, notes, status, due |

### 6.4 Live session (chair tools)

`session` (id, committee_id, chair, state), `speakers_list_entry`, `timer`, `motion`, `division`, `division_vote`, `minutes` (generated, then edited, versioned).

### 6.5 Debating

`debate_event`, `house`, `team`, `team_member`, `adjudicator`, `room`, `round`, `draw_pairing` (round, affirmative, negative, room, adjudicators), `ballot` (pairing, adjudicator, rubric_id, per-criterion scores, winner), `ladder` (derived view), `house_points_rule`, `house_points_entry`, `run_sheet`, `mc_script`.

### 6.6 History and audit

`event_log`: seq, at, actor (role + id), entity, entity_id, action, before, after. This is the source of version history, undo, minutes, and the "who changed what" record. Retained for one school year, then archived or purged (§8).

## 7. Architecture

### 7.1 Options

| | A. Extend current relay | **B. Python app, server-owned state** | C. JavaScript full stack | D. School Microsoft 365 / Power Apps | E. Hosted backend service (e.g. Supabase) |
|---|---|---|---|---|---|
| Shape | Keep thin WebSocket relay, browsers hold logic | FastAPI + SQLite + server-rendered HTML (Jinja2) + htmx + one small WebSocket script | Node + React + DB | Lists + Power Apps forms | Hosted Postgres, realtime, auth |
| Persistence and roles | Would have to be added to a design built to avoid them | Native | Native | Native | Native |
| Runs on the laptop (pilot) | Yes | Yes | Yes | No (cloud) | No (cloud) |
| Build step | None | **None** | npm toolchain | None | Some |
| Accessibility effort | Retrofit 51 `innerHTML` builders | Semantic HTML by default | Depends on discipline | Limited control | Depends |
| Testability | Browser-only JS tests today | pytest for engine and server; Playwright + axe for UI | Good | Weak | Good |
| Fits Ben maintaining alone (Python, SQL, HTML/JS) | Poor | **Good** | Medium | Medium | Medium |
| Hosting sign-off | None for laptop | None for laptop; ready for a server later | Same as B | Already approved platform | **Required**, data with a third party |
| Simulation and calibration | In browser JS | Python, with numpy available if needed | JS | Impractical | Separate service needed |

### 7.2 Recommendation: B

The case for B rests on four measured gaps in the current shell (from `audit.md`):

1. **No persistence:** zero file or database writes. Layers 2 and 3 are mostly stored records.
2. **Client authority:** scores are computed and broadcast by browsers, which rules out role-based access.
3. **UI built from strings:** 51 `innerHTML` builders and one ARIA attribute. Making it accessible means rewriting it.
4. **Room cap and loop:** a 9-player cap and an 8-phase game loop sit at the heart of `rooms.py`.

Fixing all four inside the relay would replace its role, its state model and its UI. That is a rewrite either way, but a hidden one. B does it openly and keeps what works:

- **Ported and carried over:** the archetype maths (parity-tested), sponsor/second resolution, room-code generation, the static allowlist approach, the event-log-with-sequence pattern, flags, pack data (migrated with "unsourced" labels), the rubric criteria, and the branding tokens.
- **Frozen, not deleted:** the whole v2 game stays runnable from tag `pre-platform-baseline` and is linked as a "Practice game" module. It isn't extended.
- **What that amounts to:** about 10–15% of the existing 4,651 lines carry over as logic or data. The rest is retired, unchanged and still in the repo.

**B in detail:**

- Python 3.12, FastAPI + Uvicorn (one process: pages, API and WebSocket on one port).
- SQLite in WAL mode, plain SQL migrations, a nightly copy-backup to a configurable folder.
- Jinja2 templates, htmx for in-page updates, and one small vanilla JS module for live events (speakers list, timers, votes, paragraph locks). No npm, no bundler.
- Engine as a pure Python package (`app/engine/`), standard-library `random` with a seed. Add numpy only if a measured GA simulation (193 countries × 10,000 runs) takes over 1 second.
- Admin login: one coordinator passphrase set at first run, stored hashed (`hashlib.scrypt`). Staff get their own passphrases.
- Student join: class code + tap name (decided). Mitigations for impersonation are in §8.
- Hosting: the laptop on school Wi-Fi for the pilot (decided; already proven). The same app runs unchanged on a school server or an Australian-region VM later, **only with school sign-off** (nothing decided).

### 7.3 Repository layout (proposed)

```
app/                 new app (engine/, web/, db/, templates/, static/) — not named `platform`, which would shadow Python's stdlib module
legacy/              (later) pointer + launcher for the frozen v2 game; original files stay where they are until Phase 2
docs/                audit.md, spec.md, decisions.md
tools/               fake-data generator, audit scripts, parity fixture generator
tests/               pytest (engine, rules, calibration, API), Playwright + axe (UI)
data/                gitignored — real and demo databases, backups
```

Each module (`mun`, `chair`, `debating`, `people`, `engine`) is a package with its own routes, templates and tests, and can be switched off in config. That's how each can be shipped alone.

## 8. Privacy rules (non-negotiable)

1. **Minimise.** Students: first name, last initial only if needed to disambiguate, class, delegation and role, pathway milestones. No surnames, emails, dates of birth, photos, IP addresses or device fingerprints.
2. **Never in git.** `data/` is gitignored. A pre-commit check rejects `.db` files and any CSV in a real-data folder. Development and tests use only the fake-data generator.
3. **Role-based access** is enforced on the server for every route and WebSocket message. Students see only their class, their delegation's private material, and public documents.
4. **Impersonation risk accepted for joining (code + pick name), and contained:**
   - A name, once claimed, is locked to that device until the teacher releases it.
   - A second device trying to claim a locked name needs teacher approval.
   - Anything that affects scores or house points is attributable in the event log and reversible by staff.
   - Class codes rotate per term and can be regenerated instantly.
5. **No secrets in the repo.** The passphrase hash and any API keys live in a local config file that is gitignored.
6. **Retention.** Class data is archived at year end. Pathway records are kept while the student is in the program, then deleted on request or at exit. Soft-deleted items are purged after 30 days.
7. **AI (Phase 4).** No student names or student-written text are sent to an external AI service unless the school approves that use. AI output is always labelled and never stored as fact.
8. **Hosting.** Laptop only for the pilot. Any server or cloud hosting needs written school sign-off first. A privacy summary for that sign-off is a Phase 5 deliverable.
9. **Demo mode** uses only generated fake people.

## 9. Accessibility (from the start)

- **Target:** WCAG 2.2 AA. Every phase's exit includes an automated axe check (zero serious or critical issues) and a manual keyboard-only and NVDA screen-reader pass of that phase's new screens.
- **Semantic HTML:** real buttons, labels, landmarks and headings. No clickable `div` or `li`.
- **Never colour alone:** stance is shown as text and icon as well as colour (e.g. "Support ▲").
- **Live regions** for the speakers list, timers and vote results, rate-limited so screen readers aren't flooded.
- **Timers** can be paused and extended per student (WCAG 2.2.1). "Reduce motion" is respected.
- **Text and zoom:** works at 200% zoom and 320 px width. An optional dyslexia-friendly font setting.
- **Plain-English errors** that say what to do next.

## 10. Roadmap

Ben's decision: build and design everything before piloting with students; no pilot date. Each phase ends with a tag (`phase-N-complete`) and exit criteria that are measured, not asserted.

**My recommendation:** run a **staff dry-run in demo mode** at the end of Phases 2 and 3 (fake data, no students). Building every phase before any real use risks building the wrong thing; a dry-run catches that cheaply without involving students.

| Phase | Delivers | Exit criteria (measured) | Relative size |
|---|---|---|---|
| **1 Coordinator spine** (single user) | App skeleton; DB and migrations; admin login; admin screens for reference data; conferences, committees, delegations, roster (fake data); resolution workspace (paragraphs, versions, amendments, sponsors, autosave, undo, history); prediction engine v2 (§5) with evidence entry, swing list and amendment comparison; tasks from whip output; actual-vote entry and calibration report; exports; demo mode; frozen legacy game linked | All §5.8 tests pass. Parity fixture 100%. W-1 completed end-to-end by Ben in demo mode. axe: 0 serious. Every export opens in Word, Excel and a PDF viewer | L |
| **2 Class mode** | Class code join; roles enforced; live updates; paragraph ownership locks; speakers list, timers, motions, divisions (GA and SC rules), minutes; chair reconnect | 30 simulated clients for 45 min: no lost events, p95 update latency under 1 s on the laptop. Chair browser killed mid-session recovers to the same state. Staff dry-run done | L |
| **3 Debating** | Events, houses, teams, adjudicators; deterministic draws (random first round, then power-paired, seeded); rubric ballots; ladders; house points; run sheets and MC scripts from templates | Draw tests (no repeat pairings where avoidable, side balance, determinism). Ladder maths tests. A 325-student carnival generated from fake data runs end-to-end. Staff dry-run done | M–L |
| **4 Intelligence** | Licence-checked UN voting data import; voting-history priors; backtest calibration; AI practice delegations and AI-suggested positions (labelled, sourced or unknown); rubric-anchored feedback coaching | Backtest report against baselines published in docs. Any AI output without a source is stored as unknown (tested). AI use approved by the school before it's switched on | L |
| **5 Hardening** | Permissions audit, backup and restore drill, full accessibility audit, privacy summary for school sign-off, performance check, staff guide, then the **pilot with a class of 25** | Restore from backup on a second machine. Accessibility audit with no AA failures outstanding. Pilot go/no-go checklist signed off by Ben | M |

**First pilot (scoped):** one MUN class of about 25, laptop on school Wi-Fi, one resolution workspace, a whip count with evidence, a live session (speakers list, timers, motions, a division), and a debating round with rubric ballots. Measured on:

- zero data-loss incidents,
- chair recovery time,
- the share of students who could join unaided in under 2 minutes,
- calibration of any votes predicted,
- a student and staff usability survey.

## 11. What carries over, exactly

| Existing | Destination | How |
|---|---|---|
| `shared/engine.js` `stanceOf` maths | `app/engine/priors/archetype.py` | Port; parity-tested against a JSON fixture generated from the JS |
| `resolveSponsorship` / `tallySponsorship` | `app/engine/sponsorship.py` | Port with its tests. Clause single-sponsor rule kept as an option |
| `src/pack_climate2026.js` | Seed tables (`tag`, `archetype`, `archetype_affinity`, `country_archetype`, demo committee/resolution) | One-off migration script. Every value labelled `source_type = model estimate, unsourced` |
| Country facts and overrides | `evidence` rows | `source_type = unsourced note` until a source is attached. Overrides become strong evidence items, so they no longer vanish when any amendment is applied |
| `shared/flags.js` | `country.flag_svg` | Data copy; admin can add flags for new countries |
| `shared/rubric.js` criteria | `rubric` row "MUN negotiation" | Descriptors written per level. The regex scorer is optional "checklist hints" only, never a grade |
| `shared/scoring.js` profiles | Phase 2 session summary | Concept kept; fidelity is judged against the evidence-based prediction, with a staff override, not the archetype bucket |
| `rooms.py` code generation, event log `seq` | `app/db` | Ported patterns |
| `server.py` static allowlist | Not needed (framework static mount) | The principle, serve only `static/`, stays |
| Visual tokens, SOC logo, footer notice | `app/web/static` | Copied; contrast re-checked for AA |
| Everything else (v2 game, clients, relay, solo build) | Stays in place at its current paths, frozen | Reachable as "Practice game". Not extended |
