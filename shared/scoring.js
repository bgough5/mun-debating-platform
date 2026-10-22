// ============================================================
// WHIP COUNT — SCORING MODEL
// The three-axis scoring model from HANDOVER.md section 8. Pure
// functions, no DOM, no network — takes already-known facts (a cast
// vote, a computed true stance, a division tally, message marks) as
// plain inputs, so every client computes identical results from the
// same public event log.
//
// The tension between Axis 1 (did you vote your mandate) and Axis 2
// (did you end up on the winning side) IS the pedagogy — HANDOVER.md
// says to make it visible, not smooth it over. Don't blend these axes
// into a single number anywhere; keep them separate and let the
// Delegate Profile below surface the tension.
// ============================================================
const Scoring = (function () {
  "use strict";

  // ---- Axis 1: Mandate Fidelity (40) ----
  // Distance between the cast vote and the archetype-computed true stance.
  function mandateFidelityPoints(castVote, trueStance) {
    const distance = Math.abs(castVote - trueStance);
    const points = distance === 0 ? 40 : distance === 1 ? 24 : distance === 2 ? 8 : 0;
    return { points, distance };
  }

  // ---- Axis 2: Coalition (30, +15 sponsor/seconder bonus) ----
  // tally: the {passed, ...} shape from Engine.tallyVotes/computeDivision.
  function coalitionPoints(castVote, tally, sponsoredOrSecondedWinningAmendment) {
    let base;
    if (castVote === 0) base = 12;
    else if ((castVote > 0) === tally.passed) base = 30; // voted with the side that carried
    else base = 5;
    const bonus = sponsoredOrSecondedWinningAmendment ? 15 : 0;
    return { points: base + bonus, base, bonus };
  }

  // ---- Axis 3: Diplomacy (30) ----
  // myMessageMarks: this player's own {total, max} rubric marks (shared/rubric.js),
  // across every channel they spoke in. A single strong statement shouldn't
  // max the axis — HANDOVER.md requires at least two to score above half.
  function diplomacyPoints(myMessageMarks) {
    if (!myMessageMarks.length) return { points: 0, average: 0, count: 0 };
    const average = myMessageMarks.reduce((sum, m) => sum + (m.total / m.max) * 30, 0) / myMessageMarks.length;
    const capped = myMessageMarks.length < 2 ? Math.min(average, 15) : average;
    return { points: Math.round(capped), average, count: myMessageMarks.length };
  }

  function totalScore(fidelity, coalition, diplomacy) {
    return fidelity.points + coalition.points + diplomacy.points;
  }

  // ---- Delegate Profile (the payoff — HANDOVER.md section 8) ----
  // Classifies from the axis 1/2 mix (diplomacy doesn't enter the matrix;
  // it's rewarded on its own axis). Thresholds: "high" fidelity means
  // exact or one bucket off (24+); "high" coalition means landing on the
  // side that actually carried (the base 30, not counting the sponsor bonus).
  function classifyProfile(fidelityPoints, coalitionBasePoints) {
    const highFidelity = fidelityPoints >= 24;
    const highCoalition = coalitionBasePoints >= 30;
    if (highFidelity && highCoalition) {
      return { profile: "Statesman", line: "Moved the room without leaving your mandate. This is the job." };
    }
    if (highFidelity && !highCoalition) {
      return { profile: "Principled Isolate", line: "Your position held, but you didn't bring anyone with you." };
    }
    if (!highFidelity && highCoalition) {
      return { profile: "Gone Native", line: "You won the vote by voting against your own country's interest. Your ministry would recall you." };
    }
    return { profile: "Passenger", line: "You were in the room but not in the negotiation." };
  }

  return { mandateFidelityPoints, coalitionPoints, diplomacyPoints, totalScore, classifyProfile };
})();
