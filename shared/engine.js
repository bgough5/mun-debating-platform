// ============================================================
// WHIP COUNT — ENGINE
// Pure game-logic, ported unchanged from src/engine.v1.html.
// No DOM access. No pack-specific content — every function takes
// a PACK object as an argument, so this file works unmodified
// with any topic pack that matches the pack schema.
//
// Loaded as a plain classic script (no bundler, no build step —
// same distribution model as the pack files). Exposes a single
// global, `Engine`, matching how PACK is exposed by pack files.
// ============================================================
const Engine = (function () {
  "use strict";

  const STANCE_NAME = { 2: "Strongly support", 1: "Support", 0: "Abstain", "-1": "Oppose", "-2": "Strongly oppose" };
  const STANCE_COLOR = { 2: "#0A4527", 1: "#0A6B39", 0: "#8A8078", "-1": "#8C332A", "-2": "#5E1F18" };

  // Compute a country's stance on a tag-set from its archetype blend.
  // Returns { s: -2..2, line: string|null, forced?: true, raw?: number }.
  function stanceOf(country, tags, clauseId, pack) {
    if (clauseId) {
      const o = pack.overrides[country.n + "|" + clauseId];
      if (o) return { s: o.s, line: o.line, forced: true };
    }
    if (!tags.length) return { s: 0, line: null };
    let total = 0, wsum = 0;
    for (const [arch, wt] of Object.entries(country.w)) {
      const aff = pack.archetypes[arch].affinity;
      let sub = 0;
      tags.forEach(t => sub += (aff[t] || 0));
      total += (sub / tags.length) * wt;
      wsum += wt;
    }
    const raw = total / wsum;
    const s = raw >= 1.15 ? 2 : raw >= 0.4 ? 1 : raw > -0.4 ? 0 : raw > -1.15 ? -1 : -2;
    return { s, line: null, raw };
  }

  // In-character reaction line for a computed stance. `tags` is accepted
  // for signature parity with v1 but unused there too — kept as-is.
  function lineFor(country, stance, tags, pack) {
    if (stance.line) return stance.line;
    let top = null, best = -1;
    for (const [a, w] of Object.entries(country.w)) if (w > best) { best = w; top = a; }
    return pack.lines[top][String(stance.s)];
  }

  // Archetype blend as display strings, e.g. ["Industrialised Donor 45%", ...],
  // sorted by descending weight.
  function archNames(country, pack) {
    return Object.entries(country.w)
      .sort((a, b) => b[1] - a[1])
      .map(([a, w]) => pack.archetypes[a].name + " " + w + "%");
  }

  // Fisher-Yates. `rng` defaults to Math.random but is injectable for tests.
  function shuffle(arr, rng) {
    rng = rng || Math.random;
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(rng() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  // Apply an amendment's add/remove lists to a clause's tag set.
  // amendment=null/undefined returns the tags unchanged (unamended text).
  function applyAmendment(tags, amendment) {
    if (!amendment) return [...tags];
    let next = [...tags];
    amendment.remove.forEach(t => { next = next.filter(x => x !== t); });
    amendment.add.forEach(t => { if (!next.includes(t)) next.push(t); });
    return next;
  }

  // Physically rewrites the clause's displayed text per the amendment's
  // textOp (pack content, not engine logic — see pack_climate2026.js).
  // "replaceVerb" swaps the clause's own leading verb; "append" adds a
  // sentence to the end. amendment=null/undefined (or one with no textOp)
  // returns the text unchanged.
  function applyAmendmentText(clauseText, clauseVerb, amendment) {
    const op = amendment && amendment.textOp;
    if (!op) return clauseText;
    if (op.type === "replaceVerb") {
      return clauseText.startsWith(clauseVerb) ? op.with + clauseText.slice(clauseVerb.length) : clauseText;
    }
    if (op.type === "append") return clauseText + op.text;
    return clauseText;
  }

  // Tally a set of already-decided votes ({s: -2..2, ...}). Used both for
  // AI-computed divisions (computeDivision below) and for a room's actual
  // cast player votes, which have no stanceOf to compute — a human chose them.
  function tallyVotes(votes) {
    const yes = votes.filter(v => v.s > 0).length;
    const abstain = votes.filter(v => v.s === 0).length;
    const no = votes.filter(v => v.s < 0).length;
    const passed = yes > no;
    return { votes, yes, abstain, no, passed };
  }

  // Whole-chamber division on a tag-set. Pass clauseId=null for amended text
  // (overrides apply only to the unamended clause — see stanceOf).
  function computeDivision(countries, tags, clauseId, pack) {
    const votes = countries.map(c => ({ country: c, s: stanceOf(c, tags, clauseId, pack).s }));
    return tallyVotes(votes);
  }

  // Generic sponsor/second tallying: the amendment mechanic (sponsor one,
  // second someone else's, most-seconded wins) and the clause-pitch
  // mechanic (HANDOVER.md 11a — a delegation pitches which clause gets
  // debated, others second it) are mechanically identical, just applied to
  // a different candidate set and a different pair of event kinds. This is
  // the shared engine underneath both; see tallyAmendmentEvents/
  // resolveAmendment and tallyClausePitchEvents/resolveClausePitch below
  // for the two concrete instantiations every client actually calls.
  //
  // Sponsoring is exclusive per player (latest sponsorship replaces any
  // earlier one) but co-sponsorship is allowed (multiple players can
  // sponsor the same candidate).
  function tallySponsorship(events, sponsorKind, secondKind, idField) {
    const sponsorsOf = {};          // candidateId -> Set(playerId)
    const currentSponsorship = {};  // playerId -> candidateId | null
    const firstSponsoredAtSeq = {}; // candidateId -> seq of its first sponsorship
    const secondsOf = {};           // candidateId -> Set(playerId)

    for (const e of events) {
      if (e.kind === sponsorKind) {
        const prevId = currentSponsorship[e.playerId];
        if (prevId && sponsorsOf[prevId]) sponsorsOf[prevId].delete(e.playerId);
        const newId = e.payload[idField] || null;
        currentSponsorship[e.playerId] = newId;
        if (newId) {
          sponsorsOf[newId] = sponsorsOf[newId] || new Set();
          sponsorsOf[newId].add(e.playerId);
          if (!(newId in firstSponsoredAtSeq)) firstSponsoredAtSeq[newId] = e.seq;
        }
      } else if (e.kind === secondKind) {
        const id = e.payload[idField];
        secondsOf[id] = secondsOf[id] || new Set();
        if (e.payload.seconded) secondsOf[id].add(e.playerId);
        else secondsOf[id].delete(e.playerId);
      }
    }
    return { sponsorsOf, currentSponsorship, firstSponsoredAtSeq, secondsOf };
  }

  // Deterministically resolve which candidate (if any) wins. Every client
  // replays the same public events, so every client computes the same
  // winner — no server-side game logic needed. A sponsor's own support
  // doesn't also count as a second. Ties go to whichever candidate was
  // sponsored first. candidates/idOf let this work for any list of
  // {id: ...}-shaped objects (amendments, clauses, ...).
  function resolveSponsorship(events, sponsorKind, secondKind, idField, candidates, idOf) {
    const { sponsorsOf, firstSponsoredAtSeq, secondsOf } = tallySponsorship(events, sponsorKind, secondKind, idField);

    const effectiveSeconds = (id) =>
      [...(secondsOf[id] || [])].filter(pid => !(sponsorsOf[id] && sponsorsOf[id].has(pid))).length;

    const sponsoredIds = Object.keys(sponsorsOf).filter(id => sponsorsOf[id].size > 0);
    if (sponsoredIds.length === 0) return null;

    let winnerId = null;
    for (const id of sponsoredIds) {
      if (winnerId === null) { winnerId = id; continue; }
      const count = effectiveSeconds(id), winnerCount = effectiveSeconds(winnerId);
      if (count > winnerCount || (count === winnerCount && firstSponsoredAtSeq[id] < firstSponsoredAtSeq[winnerId])) {
        winnerId = id;
      }
    }
    return candidates.find(c => idOf(c) === winnerId) || null;
  }

  function tallyAmendmentEvents(events) {
    return tallySponsorship(events, "amendment_sponsor", "amendment_second", "amendmentId");
  }
  function resolveAmendment(events, amendments) {
    return resolveSponsorship(events, "amendment_sponsor", "amendment_second", "amendmentId", amendments, a => a.id);
  }
  function tallyClausePitchEvents(events) {
    return tallySponsorship(events, "clause_sponsor", "clause_second", "clauseId");
  }
  function resolveClausePitch(events, clauses) {
    return resolveSponsorship(events, "clause_sponsor", "clause_second", "clauseId", clauses, c => c.id);
  }

  return {
    STANCE_NAME, STANCE_COLOR,
    stanceOf, lineFor, archNames, shuffle, applyAmendment, applyAmendmentText, computeDivision, tallyVotes,
    tallyAmendmentEvents, resolveAmendment, tallyClausePitchEvents, resolveClausePitch,
  };
})();
