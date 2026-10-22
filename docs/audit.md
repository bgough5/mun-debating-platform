# Audit — Whip Count v2 (state at tag `pre-platform-baseline`)

Phase 0, written 22 October 2026. Every number below was measured against the code at commit `67543a3`. The measurement scripts are described in section 7 so they can be re-run.

## 1. Summary

Whip Count v2 is a working classroom game, not a planning tool. Its core idea is sound and worth keeping: countries are weighted blends of diplomatic archetypes, and a clause is a set of tags. Almost everything built around that idea falls short of the platform brief. The engine produces one hand-tuned verdict per vote with no evidence, uncertainty or follow-up check (55 to 78 of 263 computed stances (21–30%), depending on whether stances exactly 0.10 from a boundary are counted, sit within ±0.10 of a boundary where a small weight change flips the verdict), and the app keeps nothing once the server stops.

All four of Ben's guesses about why it fell short are confirmed (section 4). The audit found four more reasons (section 5). The most serious is that the model is used as the answer key: 40 of each student's 100 points depend on matching it, and it has never been checked against a real vote.

## 2. What exists

| Part | Files | Lines | What it does |
|---|---|---|---|
| Prediction engine | `shared/engine.js` | 193 | `stanceOf` (bucketed archetype maths), amendment tag/text rewriting, division tally, sponsor/second resolution |
| Topic pack | `src/pack_climate2026.js` | 165 | 10 tags, 8 archetypes, 9 clauses, 6 amendments, 31 countries, 16 overrides, 40 reaction lines |
| Rubric marker | `shared/rubric.js` | 184 | Regex/keyword scoring of negotiation messages, 6 criteria × 5 points |
| Scoring | `shared/scoring.js` | 73 | Fidelity / coalition / diplomacy points; four "delegate profiles" |
| Flags | `shared/flags.js` | 133 | Hand-drawn simplified SVG flags for the 31 pack countries |
| Server | `server/server.py`, `server/rooms.py` | 699 | Python WebSocket relay; rooms, 8-phase state machine, event log, static-file allowlist |
| Clients | `client/player.html`, `client/teacher.html` | 1,729 | Delegate and chair screens, all UI built as HTML strings in JavaScript |
| Solo build | `src/engine.v2.html`, `build_solo.py`, built HTML | 491 + build | Offline single-player version |
| Tests | `test/*.py`, `test/*.test.html` | 850 | 37 Python tests (pass); 3 JS test pages that only run by opening them in a browser |
| Docs | `README.md`, `HANDOVER.md`, `server/PROTOCOL.md` | — | Original brief, decisions, protocol |

Total: 4,651 lines.

### Where the data came from

- **Archetype affinities (80 numbers), country blends (31), overrides (16), country facts (31):** all hand-entered. `HANDOVER.md` §12 says the pack was built from `resolution-and-country-analysis.md` in Ben's claude.ai project. That file is not in the repo, so I could not check it.
- **Sources:** none. 0 of 31 country facts carry a source field. Several facts state 2026 events (e.g. the US leaving the UNFCCC in February 2026) that I have not verified.
- **Clause text:** taken from the UNAA Victoria 2026 draft resolution, per `HANDOVER.md`.
- **No voting records** of any kind are used.

## 3. Disposition: keep, fix or retire

| Item | Verdict | Reason |
|---|---|---|
| Archetype blend model (`stanceOf` maths) | **Keep, demoted to one prior among several** | Cheap and explainable, it generalises across topics, and it gives a sensible starting point. It is not evidence and must stop being presented as a verdict. |
| Pack data (countries, archetypes, clauses) | **Keep as seed data**, every value labelled "estimate, unsourced" until sourced | It's real work and a fair demo set, but it carries no provenance. |
| Sponsor/second resolution (`resolveSponsorship`) | **Keep** (port) | Deterministic, tested, matches procedure. Tie-break rule (earliest sponsor) is already explicit. |
| Amendment text rewriting (`applyAmendmentText`) | **Replace** | The idea is right (amendments change text), but the two generic operations can't express real amendments. The workspace will hold real paragraph versions instead. |
| Flags | **Keep** | Data, works offline, no emoji dependency. |
| Event log with sequence numbers (`rooms.py`) | **Keep the pattern** | Append-only log is the natural basis for version history, undo and an audit trail. |
| Room-code generation, static-file allowlist | **Keep** | Small, correct, tested live. |
| Rubric *criteria* (protocol, interest, specificity, engagement, trade, concision) | **Keep as rubric data** | Good criteria for MUN feedback. |
| Rubric *auto-scorer* (regex) | **Retire as a grade**; keep only as an optional checklist hint | Gameable; see 5.1. |
| Scoring axes and delegate profiles | **Keep the concept**, re-base on teacher-validated inputs | Profiles were popular. Fidelity must not be scored against an unvalidated model. |
| Thin relay, client-computed scores | **Retire** | No persistence or roles, and any client can broadcast a score. See 5.3. |
| Player/teacher UI | **Retire** (frozen, still runnable) | 51 `innerHTML` string builders, 1 ARIA attribute in total, clickable `<li>` that a keyboard can't reach. |
| Whole v2 game | **Freeze as "Practice game" module** | It works and students used it. Keep it runnable from the tag; don't extend it. |

## 4. Ben's four guesses, checked

| Guess | Verdict | Evidence |
|---|---|---|
| Computes from hand-entered guesses | **Confirmed** | Every input is a hand-typed integer (section 2). Nothing comes from voting records, statements or treaties. |
| One number per vote, no evidence | **Confirmed, and worse than it looks** | `stanceOf` returns one of five buckets. The "reason" shown is a generic archetype sentence. 55 to 78 of 263 (21–30%), depending on whether stances exactly 0.10 from a boundary are counted, sit within ±0.10 of a bucket boundary (corrected 22 Oct 2026; see §7), so a small change in a hand-typed weight flips the verdict, yet each is shown as certain. Germany and Spain have identical blends, so they get identical predictions on every clause. |
| Doesn't say what to do next | **Confirmed** | No swing-vote ranking, lobbying targets or amendment comparison. The lever barely exists in the model anyway: across 54 clause × amendment combinations in the 31-country Full Assembly, an amendment changes pass/fail only **2 times**. |
| Never checks whether it was right | **Confirmed** | There are no file or database writes anywhere in the server, so nothing survives a restart. No actual votes are recorded and no calibration exists. Instead, the model is used **as ground truth**: Mandate Fidelity (40/100 points) grades students on agreeing with it. |

## 5. Further reasons it fell short

### 5.1 The rubric marks vocabulary, not argument

Measured with `shared/rubric.js` on clause 2.6, playing Kenya:

| Statement | Score |
|---|---|
| "Honourable delegates, wealthy finance adaptation renewable geothermal 2.6 5% Green Climate Fund pay provided that in exchange." (no argument at all) | **30/30** |
| "Kenya cannot back new obligations it cannot fund. We would back this text if donors commit the money first, because our grid is already clean and our farmers need help now." (a real conditional offer) | **15/30** |
| A proposal mentioning sub-clause "(i)" | Penalised as first person ("i") |

A student who learns to game it learns the wrong thing. This is the "measure rather than assert" failure in miniature: it was tested on fixtures I wrote, never on adversarial input.

### 5.2 Overrides and averaging behave inconsistently

- Overrides apply only to unamended text. In 51 of 96 override × amendment cases (53%), any amendment, even an unrelated one, discards the override and the country's stance changes. Example: the US's −2 on clause 2.1 (Paris withdrawal) becomes −1 if the verb is softened, although the stated reason still applies.
- Support is averaged across a clause's tags. Adding a tag a country likes can therefore lower its support: there are 28 cases where an amendment adds only tags the country's main archetype favours and its stance drops.
- 83 of 279 cells (30%) come out as abstain. That is plausible but unvalidated.

### 5.3 Built as a game for 9, not a tool for 25

- `VALID_PLAYER_COUNTS = (3, 5, 7, 9)` caps a room at 9. A class of 25 is not supported.
- There is one clause per round and a fixed 8-phase loop. There is no resolution document, no sponsors list, no operative paragraphs, no blocs, no roster and no history.
- All state is in memory. If the teacher's browser drops, there is no way back into the room (no chair reconnect exists). If the server stops, everything is lost.
- Scores are computed in each student's browser and broadcast. Any client could send any score.
- **The pack contract is broken in two places.** `HANDOVER.md` says a new topic is "a new data file, never a code change", and that the tag vocabulary "carries a refugee, AI-governance or disarmament topic". Neither holds. The rubric's tag keywords are hard-coded in `rubric.js` (coal, oil, forest…), and flags for new countries need code in `flags.js`. A disarmament topic would need new tags (`curb_fossil` and `agriculture` don't apply), which means editing code.

### 5.4 Accessibility was never designed in

Across `player.html`, `teacher.html` and `engine.v2.html` there is **1** ARIA attribute (a decorative `aria-hidden` added in July), **0** `role` attributes and **0** `tabindex`. The negotiation channel list is a clickable `<li>`, so a keyboard can't reach it. Stance is shown largely by colour. Banners aren't announced to screen readers. Timers can't be extended (WCAG 2.2.1).

### 5.5 Process

- Verification was mostly hand-driven browser sessions. Bugs kept surfacing after features were called done: the malformed `onclick` that blocked negotiation, the static server exposing the whole project, unlimited co-sponsorship.
- The JS tests only run by opening an HTML page; nothing runs them automatically.
- The Python suite passes (37 tests) but took 51 s today against about 3 s in July. I haven't investigated why.
- Documentation drifted. `README.md` and `HANDOVER.md` don't record the 29 July changes (file allowlist, single-sponsor clause pitch, unread badges, emblem). There was no `CLAUDE.md`. Session notes were saved under the old `Downloads` path.
- The folder was not a git repository. It is now (this session), with the baseline tagged.

## 6. My own account of the decisions

Asked for honesty rather than defence:

- I accepted "port the archetype engine, don't redesign it" as a constraint and kept building on top of it instead of asking whether a deterministic bucket was the right output. Everything downstream (fidelity scoring, the reveal, the result screen) inherited that.
- I recommended client-computed scoring to avoid two languages. It made the server simple and the system untrustworthy and stateless.
- I wrote the rubric fixtures myself, so the tests confirmed my own assumptions. I never tried to break it.
- I repeated the handover's claim that the tag vocabulary generalises to other topics without testing it.
- I spent effort on polish (badges, an emblem, flags) while known foundational gaps (no persistence, no chair reconnect, no accessibility) stayed open. I flagged the reconnect gap only when asked for a final review.

## 7. How the numbers were produced

Two Node scripts (kept outside the repo, in the session scratchpad) load `shared/engine.js`, `shared/rubric.js` and `src/pack_climate2026.js` unchanged:

- **Engine:** every country × clause stance, distance of each raw score from the bucket thresholds (1.15, 0.4, −0.4, −1.15), identical blends, 31-country divisions for each clause, unamended and under each of the 6 amendments, and override survival under amendment.
- **Rubric:** scores the three probe statements above.

Other checks used `grep` on the source (ARIA attributes, `innerHTML`, file writes, player-count constant) and `python -m unittest discover -s test`. The scripts were added to the repo in Phase 1: `node tools/audit/engine_audit.js` reproduces every engine figure (output in `tools/audit/engine_audit_output.json`).

**Correction (22 Oct 2026).** This audit first said "62 of 263 computed stances (24%)" were within ±0.10 of a bucket boundary. The correct statement is 55 to 78 of 263 (21–30%), depending on whether stances exactly 0.10 from a boundary are counted: 55 strictly inside 0.10, 78 including the 23 that sit exactly 0.10 away. The original 62 came from floating-point rounding of those exact ties. The original script used `<= 0.10` with no tolerance; re-run on 22 Oct and confirmed: the same test in `tools/audit/engine_audit.js` (`near_boundary_within_0_10_no_tolerance`) gives 62, because some exact ties compute as slightly under 0.10 and others slightly over. The conclusion is unchanged: a fifth to a third of stances sit on a knife-edge.

## 8. Not verified

- The provenance of the pack values (source document not in the repo).
- The 2026 country facts in the pack.
- Whether the UN voting datasets proposed in `spec.md` §5.7 may be used: licence terms were not found.
- Evatt's current rules: public descriptions I found date from 2015 to 2023.
- The cause of the slower Python test run.
