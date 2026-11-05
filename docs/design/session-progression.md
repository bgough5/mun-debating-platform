# The Session: stages, breakthroughs and a growing delegation (proposal, 5 Nov 2026)

Status: **proposed; Ben's choices made 5 Nov 2026; numbers to be measured.** Nothing in the engine changes until
Ben's unpushed laptop work (phase 9) is on `main`, so this builds on it. When built, it becomes a section of
`docs/design/solo-campaign.md` and a decision in `docs/decisions.md`.

## What Ben found playing it (5 Nov 2026)

- Every chapter looks the same; you can't tell which part of the game you're in. The bloc chapter doesn't show
  who is in each bloc.
- Chapters end on the clock, not on what you achieve.
- A flat 3 actions a turn feels limiting once there are resources to build.
- The menus should pop out.

Checked in a test game here: pressing only End turn reached the Summit with a passing draft and 41 Influence unspent.
So there is no pressure to act, and Influence has nothing left to buy.

## Ben's choices

| Question | Choice |
|---|---|
| How a chapter ends | **Breakthrough + deadline.** Meeting the breakthrough unlocks the next stage; you choose to move on now (with a momentum bonus) or keep working. Miss it by the deadline and the Chair moves on, with a penalty. |
| Actions per turn | **A combination, like resources and units in Civ:** advisers and their level, the player's experience, Respect and stages. "By the final resolution, there shouldn't be much time to still negotiate but you should have heaps of moves per turn with maximum intel per move, as would happen with a real UN." |
| Menus | **A dock with slide-out panels**, and a country's card pops out beside its token. |

## 1. Four stages, each with its own look

A stage track runs across the top, showing all four stages:
- the one you're in, and its breakthrough as a checklist;
- what the breakthrough unlocks;
- the turns left before the deadline.

| Stage | What the table looks like | Breakthrough (the trigger) | Unlocks |
|---|---|---|---|
| **1. Working group** | The drafting table opens in the centre; the map dims behind it | **Zero draft agreed:** 4+ clauses, at least one yours, and the whole text would pass as it stands | Bloc meetings: the regional-group map, meeting rooms, side events |
| **2. Bloc meetings** | The map is shaded by regional group, and each group has a meeting room (below). One group meets each turn. | **A regional group endorses your draft** (two on Full) | Sponsors: the sign-up sheet, asking to sponsor or sign |
| **3. Sponsors** | The clerk's sign-up sheet sits beside each rival's, filling with flags as they race | **Your draft is tabled as "L.1":** 3 sponsors and enough signatories | The Summit |
| **The Summit** | The hall and the vote board | — | — |

**A meeting room** (stage 2) shows:
- every member of the group, with its flag;
- each member's lean: towards you, a rival, or undecided;
- the group's coordinator (its largest member);
- how many members an endorsement needs, and who is courting the group.

While a group is in session, **Attend the meeting** works like a cheaper side event for that group. The other
groups' rooms can still be visited.

**When a breakthrough lands**, a card asks you to choose:
- **Move on now:**
  - +1 Respect;
  - +2 Influence for each turn left;
  - rivals lose those turns too.
- **Keep working:** strengthen your hand until the deadline.

**Missing the deadline:**
- −1 Respect;
- no chapter bonus;
- the existing knock-ons still apply (for example, a rival draft tabled first is voted on first).

**Deadlines get shorter** (Standard): 6, then 5, then 4 turns. Negotiating time runs out as the delegation grows.

## 2. A delegation that grows

Actions per turn are built from sources, each shown as a pip with its icon. Locked pips say how to earn them.

| Source | Actions | Like |
|---|---|---|
| Base | 2 | — |
| Stage reached | +1 in Bloc meetings, +2 in Sponsors, +3 at the Summit | eras |
| Your staff | +1 for every 4 adviser stars (everyone starts with 4 stars, so +1). Hiring and promotions raise it. | units |
| Your experience | +1 at Expertise 5, +1 at Expertise 10 | tech |
| Respect | +1 at 5, +1 at 8 (replaces today's +1 at 7) | culture |
| Coalition | +1 while two or more regional groups endorse you | territory |
| Overtime | Buy +1 action this turn for Influence: 3, then 4, then 5 in the same turn | gold |

Typical totals:
- **Working group:** about 3 actions a turn.
- **Sponsors:** about 5–6, over fewer turns.
- **Ceiling:** about 9.

**More intel per move as the stages advance:**
- **Bloc meetings:** lobbying a delegation also shows its lean towards each rival.
- **Sponsors:** lobbying also shows how it would vote on the whole text now. Advisers' reports gain a star while
  posted to a delegation in a group that is meeting.
- **The Summit:** every decision card shows the expected vote count.

## 3. Pop-out menus

- **The dock:** a slim icon dock on the right edge, with Brief, Draft, Delegations, Blocs (from stage 2), Sponsors
  (from stage 3), Staff and Record.
- **Panels:**
  - each slides out over the map;
  - Esc closes it, and focus returns to the icon.
- **Country cards:** clicking a country pops its card out beside its token, with every action for it.
- **The map:**
  - it gets the full width;
  - its key folds into a button.

## 4. Other fixes from the test game

- The vote bar can read "would pass" from turn 1, which hides that your instructions aren't in the text yet. Add
  "Your instructions: 1 of 3 in the text" next to it.
- Influence piled up unspent. Overtime gives it a use, and so do the momentum bonus and the shorter deadlines.
- A rival that tables before you gets its draft voted on first. Its sign-up sheet makes the race visible.

## 5. How it will be checked

Re-measure with `python tools/campaign_sim.py --games 20` (2,400 games). The bots need:
- to choose between moving on and keeping working;
- to buy overtime.

Targets as in section 14 of the rules, plus:
- **Pace:** a competent bot reaches each breakthrough before its deadline in most games. A bot that only ends
  turns reaches none.
- **Growth:** average actions per turn rise stage by stage, to about 5–6 in Sponsors.
- **Length:** a Standard game still models at about 60 minutes.
- **Bonuses:** no single action-point source is worth more than the rest combined.
