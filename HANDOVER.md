# HANDOVER — "Whip Count" Model UN Caucus Simulator, v1 → v2

**To the Claude Code session picking this up:** read this whole file before writing anything. `src/` contains a working v1. Your job is v2 — multiplayer, typed negotiation with marking, and a three-axis scoring model. Section 10 lists things you must not change.

**Owner:** Benjamin Gough, South Oakleigh College. Teaches Model UN to high-achieving secondary students.
**Handover written:** 27 July 2026.

---

## 1. What this is

A classroom tool that trains the hardest Model UN skill: predicting how other delegations will vote, and then negotiating a text that both carries the room and keeps your own country's mandate intact.

Its governing design constraint, stated by the owner: **it must not be specific to one resolution or one set of countries.** It has to work for next year's topic and next year's roster without a rewrite. Everything below inherits that constraint.

Secondary constraint: this is a **preparation** tool. The conference organiser (UNAA Victoria) asks delegates not to use AI during the assembly itself. It must build student capability, never generate submittable student work. Keep the footer notice.

## 2. Current state (v1 — working, shipped)

A single self-contained HTML file. No build step, no dependencies, no network, no storage. Opens by double-click.

| File | What it is |
|---|---|
| `src/engine.v1.html` | Engine with `<script src="PACK_PLACEHOLDER">` where the pack gets injected |
| `src/pack_climate2026.js` | The topic pack — archetypes, clauses, countries, overrides, reaction lines |
| `src/WhipCount_v1_built.html` | Built artifact: engine + pack + base64 logo inlined. This is what students currently open. |

Build step is trivial — string-replace the pack and logo into the engine (see section 9 of the original build, or just re-derive it; it's three lines of Python).

**v1 game loop, single player:** choose delegation + clause → predict how 5/7/9 named delegations will vote (scored) → reveal with in-character justifications → pick one of six preset amendments → whole 31-country chamber divides → result shows whether it carried and whether your own mandate held.

## 3. The core engine — understand this before touching anything

This is the intellectual property of the tool. **Port it; do not redesign it.**

### The insight
The engine never stores "Vanuatu opposes clause 2.6." Storing country-specific positions is exactly what makes a tool die when the topic changes. Instead it stores **diplomatic archetypes** with affinities for **clause attributes**, and computes positions.

### The three data structures

**Archetypes** (8): `FRONTLINE`, `EXTRACTIVE`, `DONOR`, `EMERGING`, `REFORMER`, `DEVPRIORITY`, `SOVEREIGNTY`, `BROKER`. Each has an `affinity` map scoring −2..+2 against each clause tag.

**Tags** (10, closed vocabulary): `cost_wealthy`, `curb_fossil`, `binding`, `human_right`, `agriculture`, `adapt_finance`, `indigenous`, `lifestyle`, `ecosystems`, `tech_transfer`. Chosen to generalise past climate — the same vocabulary carries a refugee, AI-governance or disarmament topic.

**Countries** are **weighted blends** of archetypes, e.g. `Australia: { DONOR: 45, EXTRACTIVE: 40, BROKER: 15 }`. This is deliberate: it produces authentic internal tension students can feel. Do not flatten countries to a single archetype.

### The computation

```js
stanceOf(country, tags, clauseId) → { s: -2..2 }
```
Weighted average of each archetype's affinity across the clause's tags, then bucketed:
`≥1.15 → +2`, `≥0.4 → +1`, `>−0.4 → 0`, `>−1.15 → −1`, else `−2`.

An **overrides** table (~16 entries, keyed `"Country|clauseId"`) forces a stance where real diplomacy defies the maths — the US withdrawal from Paris, Costa Rica's authorship of clause 2.9, France objecting to nuclear being grouped with coal. Overrides apply only to the *unamended* clause; once a player amends the text, the maths takes over. Preserve that behaviour, it is correct.

**Reaction lines are layered** to avoid combinatorial explosion: a generic line per archetype per stance (8 × 5 = 40), overridden by a country-specific line only where it matters. Keep this pattern when you add more content.

## 4. What v2 must add

Three features, specified by the owner:

1. **Multiplayer for 3, 5, 7 or 9 students.** (Odd numbers — no tied divisions. This is deliberate; preserve it.)
2. **A typed negotiation phase** where students write as their delegation, and that writing is marked.
3. **A three-axis scoring model:** quality of typed negotiation, fidelity to how their country would actually vote, and whether they landed in the majority.

## 5. Architecture decision you must make first

v1 is a single offline HTML file. Multiplayer breaks that. **Surface this to Benjamin before building** — it changes deployment, and he is a teacher, not an ops engineer.

**Option A — Hot-seat (one device, passed around).** Zero infrastructure, stays a single HTML file, works on a projector. But typed negotiation is painfully slow when nine students share one keyboard. *Verdict: preserves simplicity, fails the typing requirement.*

**Option B — Local server, students on their own devices (RECOMMENDED).** Node + Express + WebSocket (`ws` or Socket.IO). Teacher runs one command, gets a room code, students join over school wifi at `http://<teacher-ip>:3000`. Real simultaneous typing, real negotiation, teacher dashboard on the projector. Requires Node installed on the teacher's laptop and same-network access — both normally fine in a school, but **verify before committing.**

**Option C — Hosted (Cloudflare Workers + Durable Objects, or similar).** Works anywhere, no local setup, survives school network restrictions. But it is a deployed service the school now depends on, with an account and possibly a cost. *Probably v3.*

**Recommendation: build B, structured so the game logic is transport-agnostic** — pure functions in `shared/engine.js` imported by both client and server. That keeps a path to C without a rewrite, and lets you keep shipping a single-player offline build from the same core.

## 6. Feature spec — multiplayer

### Round structure
1. **Lobby.** Teacher picks player count (3/5/7/9), topic pack, and clause (or random). Room code generated. Students join, are assigned a delegation — random by default, teacher-assignable.
2. **Private brief.** Each player sees only their own country: archetype blend, signature fact, and a plain-language summary of what their country needs from this clause. Other players' briefs stay hidden — that hidden information is what makes negotiation real.
3. **Whip count** (keep from v1, now scored per player). Each player predicts how the *other players'* delegations will vote. This is the core learning mechanic — do not drop it.
4. **Negotiation** (new). Timed, typed, shared feed. See section 7.
5. **Amendment.** Each player may sponsor one amendment; players second them; the most-seconded goes to the floor. (Fallback: teacher selects, mirroring how the real UNAA secretariat picks which amendments are debated.)
6. **Division.** Every player casts a vote. Their vote is their own choice — this is essential, because scoring depends on whether they voted as their country would have.
7. **Scoring + delegate profile.** See section 8.

### Whose votes count?
**Recommendation: the players are the chamber.** With 3 players and 28 AI delegations, nothing a student does affects the outcome and agency collapses. Keep the division among players only. Odd counts guarantee a result.

Offer a teacher toggle for **"Full Assembly"** mode, where the remaining delegations from the pack vote via `stanceOf()` alongside the players — useful for showing a realistic 31-state division once students have the hang of it.

### Teacher view
A projector-facing dashboard: who has joined, phase timer, live negotiation feed, division result, and a post-round scoreboard broken down by axis. The teacher must be able to advance phases manually — lessons never run to the clock.

## 7. Feature spec — typed negotiation and marking

### The interaction
A shared feed. Each player writes short statements **as their delegation** (suggest 60–120 words, hard cap ~150). They can reply to a named delegation. Timer, typically 6–10 minutes. Optionally a private direct-message channel between two delegations — real caucusing happens in corridors, and it rewards students who go find the swing vote.

### Marking it — the honest constraint
Free-text marking has two possible implementations. **Build the first; design for the second.**

**Rubric heuristics in plain JS (build this).** Deterministic, offline, instant, free, and — importantly — *explainable to a student*. Six criteria, 5 points each, 30 total:

| Criterion | What to detect |
|---|---|
| **Protocol register** | Third person, no first-person "I", addresses "the Honourable Secretary-General" or "fellow delegates". The UNAA pack explicitly requires delegates never say "I" and refer to countries by name — so this is real protocol, not invented. Regex-checkable. |
| **National interest** | References their own country's interest terms — derive a keyword set from their archetype blend and their pack `fact`. |
| **Specificity** | Cites a clause id (`2.6`), a named mechanism (Green Climate Fund, Paris Agreement), or a concrete figure. |
| **Engagement** | Names another delegation present in the room, or quotes/answers a position someone actually posted. |
| **Trade** | Conditional or exchange language — "in exchange", "provided that", "if the Assembly", "we could support ... should". This is the negotiation skill itself. |
| **Concision** | Within word limit and above a substance floor. Penalise padding and one-line non-answers. |

Show students the per-criterion breakdown after the round. The rubric being visible is what makes it teach rather than just score.

**Optional LLM marking (design for, ship later).** If an API key is present in server env, send the statement plus the student's country brief for a qualitative mark and one line of feedback. Must degrade gracefully to heuristics when absent — a lesson cannot fail because the wifi did. Never let it write text *for* the student; it marks only.

### Make typing matter mechanically
Strong negotiation should change outcomes, not just score. **Recommended mechanic:** a statement scoring ≥4/5 on both *Engagement* and *Trade*, directed at a specific delegation, lets that delegation's player see a "you have been lobbied" prompt — and in Full Assembly mode, shifts one *abstaining* AI delegation by a single bucket toward the sponsor. Cap the shift at one bucket and never let it move a delegation off a hard mandate. Students must learn that rhetoric moves the undecided, not the committed.

## 8. Feature spec — scoring model

Three axes, 100 per round. The tension between axes 1 and 2 **is the pedagogy** — make it visible rather than smoothing it out.

### Axis 1 — Mandate Fidelity (40)
Compare the player's cast vote against `stanceOf(theirCountry, finalTags)`:

| Distance from computed stance | Points |
|---|---|
| Exact | 40 |
| 1 bucket off | 24 |
| 2 buckets | 8 |
| 3+ | 0 |

Show the reasoning afterward — "Saudi Arabia would have opposed this; you voted for it" — with the archetype logic that produced it, so a disagreeing student can argue back. (They sometimes will, and sometimes they'll be right. That's a good lesson too. Consider letting the teacher override a fidelity score.)

### Axis 2 — Coalition (30)
- On the winning side of the division: **30**
- Abstained: **12**
- On the losing side: **5**
- Sponsored or seconded the amendment that carried: **+15 bonus**

### Axis 3 — Diplomacy (30)
The rubric total from section 7, averaged across their statements (minimum two statements to score above half — one-and-done shouldn't max it).

### Delegate Profile — the payoff
Classify each student from their axis mix and show it at round end. This is the bit they'll talk about afterward:

| Profile | Condition | Feedback line |
|---|---|---|
| **Statesman** | High fidelity + high coalition | Moved the room without leaving your mandate. This is the job. |
| **Principled Isolate** | High fidelity, low coalition | Your position held, but you didn't bring anyone with you. |
| **Gone Native** | Low fidelity, high coalition | You won the vote by voting against your own country's interest. Your ministry would recall you. |
| **Passenger** | Low both | You were in the room but not in the negotiation. |

Persist scores across rounds so a squad leaderboard is possible. Note v1 had no storage; the server makes this trivial — keep it simple (a JSON file or SQLite is plenty, this is 9 students).

## 9. Suggested build order

1. Extract v1 game logic into `shared/engine.js` as pure, testable functions (`stanceOf`, `lineFor`, `applyAmendment`). Unit test `stanceOf` against v1 behaviour — same inputs must give same outputs. **Do this first; everything else depends on it.**
2. Node + WebSocket server with room/lobby/phase state machine. No UI yet.
3. Player client: join, brief, whip count, vote. Reuse v1 CSS wholesale.
4. Negotiation feed + rubric marker (`shared/rubric.js`), independently unit-tested against sample statements — write good and bad examples as fixtures.
5. Scoring, delegate profiles, teacher dashboard.
6. Re-emit the offline single-player build from the same shared core, so the artifact Benjamin already has keeps working.

Ship a runnable thing at each step. He is a teacher with a conference deadline, not a stakeholder waiting for a big reveal.

**Status: all six steps complete.** Steps 1-5 are the multiplayer system (`shared/`, `server/`, `client/player.html`, `client/teacher.html`), reworked mid-build per section 11b's redesign and clause-pitch decisions. Step 6 is `src/WhipCount_v2_solo_built.html` — built by `python build_solo.py` from `src/engine.v2.html` + `shared/engine.js` + `shared/flags.js` + `src/pack_climate2026.js` + the SOC logo, the same one-file "no server, opens by double-click" artifact as `WhipCount_v1_built.html`, now carrying the v2 visual identity, flags, and the physically-rewritten amendment text. Verified end-to-end (setup → whip count → reveal → amendment → division → results) by serving it over a local HTTP server rather than opening it directly via `file://` — see the note at the end of this section.

`WhipCount_v1_built.html` is left in place, untouched, as a historical fallback — it is no longer the artifact to hand students, but nothing depends on deleting it.

*A note on verifying the built file*: opening `WhipCount_v2_solo_built.html` (or the original v1 build) via a `file://` URL in an automated browser-testing tool may show the inlined `<script>` tags as empty and globals as undefined — this was tested and traced to a limitation of that specific tool's handling of local files outside its project sandbox, not a defect in the build. Serving the same file over a plain local HTTP server (`python -m http.server`) and loading it there executed correctly in every respect, which is a valid proxy since the file makes no network calls and behaves identically regardless of protocol. Opening the file normally by double-click in a real browser is unaffected by this and was not itself in question.

## 10. Do not change

- **The archetype engine.** Port it, don't redesign it. It is the reason the tool generalises.
- **Weighted archetype blends.** Do not simplify countries to one archetype.
- **The pack schema contract.** A new topic must be a new data file, never a code change. If you find yourself editing engine code to support a topic, the design has failed.
- **Odd player counts.** 3/5/7/9 prevents tied divisions.
- **Branding.** Maroon `#8C332A`, dark maroon `#2A1512`, green `#0A6B39` / `#0A4527`, gold `#B8960C` / `#D4B441`, cream `#F4F0E6`, card `#FBFAF6`, ink `#2A2320`. Cambria/Georgia serif headings, Calibri body. South Oakleigh College diamond logo is base64-inlined in the built v1 — extract it from there.
- **The footer notice**: "PREP TOOL — BUILD YOUR OWN ARGUMENTS. NOT FOR USE DURING THE ASSEMBLY."
- **The tone.** Feedback is direct and a bit dry, never gamified-cheerful. No confetti, no "Great job!!". These are able 15–18 year olds being trained in something serious; the restraint is why they'll take it seriously.

## 11. Open questions for Benjamin — ask, don't assume

1. Can he run Node on the classroom machine, and can student devices reach it over the school network? **This gates the whole architecture.** Ask before building.
2. Should the whip count stay compulsory each round, or become an optional warm-up once students are fluent?
3. Should the teacher be able to override a Mandate Fidelity score when a student makes a good case for an unexpected vote?
4. Does he want scores persisted into a squad leaderboard across sessions, or wiped each lesson?
5. Year levels — is this the senior MUN squad only, or Years 9–12? Affects word limits and timer lengths.

## 11a. Answers from Benjamin (28 July 2026)

The open questions above have been answered. These are now decisions, not open questions:

1. **Architecture — Python, not Node.** Benjamin's network has had success with Python-served apps; use Python for the server rather than Node/Express. Given that, the server should be a **thin relay**: rooms/lobby state, connection handling, and broadcasting messages/votes over WebSockets — no game-logic duplication. The archetype engine, `stanceOf()`, and the rubric marker stay as **one JS engine, loaded client-side and shared by every client**. Python does not re-implement scoring. This is a low-stakes classroom tool, not an adversarial context, so client-computed scoring is an acceptable trade for not maintaining the engine in two languages. (Section 5's "shared/engine.js imported by both client and server" recommendation no longer applies as written — the shared engine is JS-only, imported by clients; the Python side only needs a corresponding pack/room JSON contract, not the engine itself.)
2. **Whip count** — teacher toggle per lesson, not fixed compulsory and not auto-gated by fluency. Build it as a lobby/session setting.
3. **Mandate Fidelity override** — yes, build teacher override capability (with a note/reason attached to the override, so the disagreement is visible on the record, not just a silent score change).
4. **Leaderboard** — wiped each lesson. No cross-session persistence. (Scores can still accumulate across rounds *within* one lesson's session.)
5. **Year levels / word limits & timers** — must be **adjustable settings**, not fixed to one cohort. This tool needs to serve both the senior MUN squad and, at times, a younger cohort being introduced to it as an accessible entry-point game.
6. **Tone for the younger-cohort mode — overrides Section 10.** Section 10's "never gamified-cheerful, always dry and direct" tone rule stands as the default/standard mode, but Benjamin wants it **relaxed for a younger-cohort mode** specifically: a lighter, more game-like tone/copy is allowed when running that mode. Implement as a selectable tone mode (standard/dry vs. younger/game-like) rather than changing the default — the standard mode keeps Section 10's tone intact for the senior squad.

## 11b. Further decisions from Benjamin (28 July 2026, after steps 1-5 were built)

Having seen steps 1-5 working live, Benjamin asked for a visual redesign and one structural change. These are now decisions, layered on top of 11a:

1. **Visual identity — supersedes Section 10's exact palette/fonts.** He wants the app to look distinctive and "like its own standalone game" — a combination of formal UN blue and modern conference-tech, professional rather than a reskinned school page, with South Oakleigh's branding pulled back to a subtle badge rather than the header identity. Implemented: a navy/blue/gold identity with Segoe UI (headings bold, body regular) and Consolas for room codes/score numbers, a new app mark (diamond + checkmark SVG), and the real SOC diamond logo (extracted from `src/WhipCount_v1_built.html`'s inlined base64 into `assets/soc_logo.png`) as a small corner badge. **Deliberate compromise**: South Oakleigh's actual maroon and green are *kept*, not replaced — they're now the semantic AGAINST/FOR (fail/pass) accent pair rather than the dominant brand colour, which is how the branding stays present without being the headline identity. The exact footer prep-tool notice and structure are untouched (that's a policy notice, not a style choice, and stays out of scope for any branding relaxation).
2. **Clause selection is now an open pitch + second, not the teacher choosing directly.** A new `clause_pitch` phase sits between `lobby` and `brief`: any player can pitch a clause, others second it, most-seconded wins — mechanically identical to the existing amendment sponsor/second mechanic, just applied to clauses instead of amendments (see `Engine.resolveSponsorship`, the generalised helper both now share). Falls back to a random clause if nobody pitches. The teacher can still force a specific clause manually (relabelled "Clause override" in the dashboard) — that always takes precedence over the pitch outcome if set. `new_round()` now returns to `clause_pitch`, not `brief`, so each round gets its own fresh pitch.
3. **Amendments now physically rewrite the clause text**, not just show a "detail" note beside the unamended original. Each amendment carries a `textOp` in the pack (`replaceVerb` for strengthen/soften, since every clause already declares its own leading `verb`; `append` for the other four) — see `Engine.applyAmendmentText`. This is pack content, not an engine change, so a future topic pack reusing this amendment schema needs its own `textOp` per amendment but no engine work.
4. **Country flags** — small inline SVGs (`shared/flags.js`), not Unicode flag emoji, since a lot of Windows configurations still render flag emoji as two-letter codes rather than actual flags. Simplified, not vexillologically exact — correct colours/stripes, coats of arms reduced to simple shapes, which is the standard, honest trade-off at this size.
5. **The clause-visibility gap Benjamin actually flagged turned out to be a real bug, not a misunderstanding**: the Whip Count and Negotiation screens never re-displayed the clause under debate after the Brief screen — fixed with a persistent clause reminder box on both.

## 12. Context worth having

Full design rationale, the archetype taxonomy with justifications, and success measures live in the project doc `claude/caucus-simulator-design-brief.md` on Benjamin's claude.ai project, alongside `claude/resolution-and-country-analysis.md` (the substantive climate research the pack was built from).

The seeded topic is the 2026 UNAA Victoria conference, "Combating Climate Change: Committing to Global Action", with the 31-country Caulfield Grammar roster. Benjamin's own students represent **Vanuatu** and **Costa Rica** — both are in the pack with override lines, and they make good demo delegations because they pull in opposite directions: Vanuatu is legal and confrontational, Costa Rica technical and consensus-seeking.
