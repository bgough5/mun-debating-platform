// ============================================================
// WHIP COUNT — RUBRIC MARKER
// Deterministic heuristic marking for typed negotiation statements
// (HANDOVER.md section 7). Six criteria, 5 points each, 30 total.
// No DOM. No network. No pack-specific content beyond the closed
// vocabulary of clause tags (PACK.tags) — the keyword map below is a
// function of that fixed vocabulary, not of any one topic pack, so it
// keeps working when the topic pack changes (see HANDOVER.md section 3).
//
// LLM marking (HANDOVER.md section 7, "ship later") is NOT built here —
// this is the deterministic fallback it must degrade to, and stands on
// its own for now.
// ============================================================
const Rubric = (function () {
  "use strict";

  // Generic English terms associated with each closed-vocabulary tag.
  // Deliberately topic-agnostic phrasing (no country/mechanism names),
  // so a future non-climate pack reusing these same tags still works.
  const TAG_KEYWORDS = {
    cost_wealthy:  ["wealthy", "cost", "funding", "finance", "afford", "pay for"],
    curb_fossil:   ["fossil fuel", "coal", "oil", "gas", "emissions", "phase out", "phase down"],
    binding:       ["binding", "obligation", "legally binding", "enforce", "mandatory"],
    human_right:   ["human right", "rights", "right to"],
    agriculture:   ["agriculture", "farming", "farmers", "crops"],
    adapt_finance: ["adaptation", "resilience", "green climate fund", "climate finance"],
    indigenous:    ["indigenous"],
    lifestyle:     ["lifestyle", "diet", "behaviour", "behavior", "consumption"],
    ecosystems:    ["ecosystem", "forest", "biodiversity", "reforestation"],
    tech_transfer: ["technology transfer", "technology", "know-how"],
  };

  const FIRST_PERSON = /\b(i|i'm|i've|i'll|i'd|my|me|mine)\b/i;
  const FORMAL_ADDRESS = /\b(fellow delegates|honourable|honorable|secretary-general|mister chair|madam chair|the assembly|the chair)\b/i;
  const CLAUSE_ID = /\b\d\.\d+\b/;
  const NUMERIC_FIGURE = /\$\d|\d+\s?%|\b\d+\s?(billion|million|degrees|years|percent)\b/i;
  const NAMED_PHRASE = /\b([A-Z][a-z]+(?:\s+(?:of|the|for)?\s?[A-Z][a-z]+){1,4})\b/;
  const TRADE_LANGUAGE = /\b(in exchange|provided that|if the assembly|should the assembly|we could support|would support .* if|on condition that|in return for|so long as|in return|conditional on)\b/i;

  function wordCount(text) {
    return (text.trim().match(/\S+/g) || []).length;
  }

  function tier(hitCount, thresholds) {
    // thresholds: [t1, t2] -> hitCount>=t2 => 5, >=t1 => 3, else 1
    if (hitCount >= thresholds[1]) return 5;
    if (hitCount >= thresholds[0]) return 3;
    return 1;
  }

  function factKeywords(country) {
    return [...new Set((country.fact.match(/[A-Za-z]+/g) || [])
      .map(w => w.toLowerCase())
      .filter(w => w.length >= 6))];
  }

  // Crude lexical-overlap proxy for "actually responded to what they said" —
  // shared words of length >=5, which filters out common short connectives
  // without needing real NLP.
  function sharesSubstantiveWord(a, b) {
    const words = s => new Set((s.toLowerCase().match(/[a-z]+/g) || []).filter(w => w.length >= 5));
    const wa = words(a), wb = words(b);
    for (const w of wa) if (wb.has(w)) return true;
    return false;
  }

  // ---- individual criteria ----

  function markProtocolRegister(text) {
    if (FIRST_PERSON.test(text)) {
      return { score: 1, detail: "Uses first person ('I'/'my') — delegates speak in third person only." };
    }
    if (FORMAL_ADDRESS.test(text)) {
      return { score: 5, detail: "Third person throughout, with formal address to the chamber." };
    }
    return { score: 4, detail: "Third person throughout, but no formal address to the chamber." };
  }

  function markNationalInterest(text, country, clauseTags, pack) {
    const lower = text.toLowerCase();
    let hits = 0;
    const tagHit = clauseTags.some(t => (TAG_KEYWORDS[t] || []).some(kw => lower.includes(kw)));
    if (tagHit) hits++;
    const facts = factKeywords(country);
    const factHit = facts.some(kw => lower.includes(kw));
    if (factHit) hits++;
    return {
      score: tier(hits, [1, 2]),
      detail: hits === 0 ? "Does not engage the clause's subject matter or this country's specific circumstances."
        : hits === 1 ? "Engages either the clause's subject matter or this country's circumstances, not both."
        : "Engages both the clause's subject matter and this country's specific circumstances.",
    };
  }

  function markSpecificity(text, clauseId) {
    let hits = 0;
    if (clauseId && CLAUSE_ID.test(text)) hits++;
    if (NUMERIC_FIGURE.test(text)) hits++;
    if (NAMED_PHRASE.test(text)) hits++;
    return {
      score: tier(hits, [1, 2]),
      detail: hits === 0 ? "No clause reference, figure, or named mechanism cited."
        : hits === 1 ? "One concrete reference (clause id, figure, or named mechanism)."
        : "Multiple concrete references (clause id, figures, named mechanisms).",
    };
  }

  // Negotiation is a private 1:1 channel (see PROTOCOL.md), so "who is
  // this addressed to" is no longer something the text needs to prove —
  // the channel itself guarantees that. What's worth marking instead is
  // whether the statement actually engages with what the other side said,
  // versus reading like a canned opening statement dropped into their inbox.
  // counterpartCountry: who this channel is with.
  // priorCounterpartMessage: their most recent message in this channel, or
  // null if this is the first message (either party's).
  function markEngagement(text, counterpartCountry, priorCounterpartMessage) {
    if (!priorCounterpartMessage) {
      return { score: 3, detail: `Opens a direct channel with ${counterpartCountry} — a reasonable opening move, but not yet a response to anything.` };
    }
    if (sharesSubstantiveWord(text, priorCounterpartMessage)) {
      return { score: 5, detail: `Directly responds to what ${counterpartCountry} raised in this channel.` };
    }
    return { score: 3, detail: `Continues the channel with ${counterpartCountry} without clearly addressing their last point.` };
  }

  function markTrade(text) {
    const hit = TRADE_LANGUAGE.test(text);
    return {
      score: hit ? 5 : 1,
      detail: hit ? "Uses conditional or exchange language — an actual negotiating move."
        : "No conditional or exchange language — states a position without offering a trade.",
    };
  }

  function markConcision(text, wordLimitMin, wordLimitMax) {
    const n = wordCount(text);
    let score;
    if (n < wordLimitMin) score = n < wordLimitMin * 0.4 ? 1 : 3;
    else if (n <= wordLimitMax) score = 5;
    else score = n <= wordLimitMax * 1.3 ? 3 : 1;
    return { score, wordCount: n, detail: `${n} words (target ${wordLimitMin}-${wordLimitMax}).` };
  }

  // ---- aggregate ----

  // context: { country, clause: {id, tags}, pack, counterpartCountry,
  //            priorCounterpartMessage, wordLimitMin, wordLimitMax }
  function markStatement(text, context) {
    const { country, clause, pack, counterpartCountry, priorCounterpartMessage, wordLimitMin, wordLimitMax } = context;
    const criteria = {
      protocolRegister: markProtocolRegister(text),
      nationalInterest: markNationalInterest(text, country, clause ? clause.tags : [], pack),
      specificity: markSpecificity(text, clause ? clause.id : null),
      engagement: markEngagement(text, counterpartCountry, priorCounterpartMessage),
      trade: markTrade(text),
      concision: markConcision(text, wordLimitMin, wordLimitMax),
    };
    const total = Object.values(criteria).reduce((sum, c) => sum + c.score, 0);
    return { total, max: 30, criteria };
  }

  // ---- negotiation mechanics (HANDOVER.md section 7, "make typing matter") ----

  function isLobbySuccess(mark) {
    return mark.criteria.engagement.score >= 4 && mark.criteria.trade.score >= 4;
  }

  // stanceResult: the {s, forced} shape returned by Engine.stanceOf.
  // direction: sign of the sponsor's own stance (positive nudges the
  // target toward support, negative toward opposition). Only ever moves
  // an abstaining, non-forced delegation, and only by one bucket —
  // rhetoric moves the undecided, never a hard mandate.
  function applyLobbyShift(stanceResult, direction) {
    if (!direction || stanceResult.forced || stanceResult.s !== 0) return stanceResult.s;
    return direction > 0 ? 1 : -1;
  }

  return {
    wordCount,
    markProtocolRegister, markNationalInterest, markSpecificity,
    markEngagement, markTrade, markConcision,
    markStatement, isLobbySuccess, applyLobbyShift,
  };
})();
