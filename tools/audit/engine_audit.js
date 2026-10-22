// Reproduces the engine figures in docs/audit.md §4–5 from the FROZEN v2 files
// (shared/engine.js, shared/rubric.js, src/pack_climate2026.js), read-only.
// Run from the repo root:  node tools/audit/engine_audit.js
"use strict";
const fs = require("fs"), path = require("path"), vm = require("vm");
const root = path.resolve(__dirname, "..", "..");
const ctx = {}; vm.createContext(ctx);
for (const f of ["shared/engine.js", "shared/rubric.js", "src/pack_climate2026.js"])
  vm.runInContext(fs.readFileSync(path.join(root, f), "utf8"), ctx, { filename: f });
const Engine = vm.runInContext("Engine", ctx), PACK = vm.runInContext("PACK", ctx), Rubric = vm.runInContext("Rubric", ctx);

const out = {};
// Computed (non-override) stances and their distance to the bucket thresholds.
const TH = [1.15, 0.4, -0.4, -1.15];
let computed = 0, near = 0, nearStrict = 0, nearRaw = 0, abstain = 0;
for (const cl of PACK.clauses) for (const c of PACK.countries) {
  const st = Engine.stanceOf(c, cl.tags, cl.id, PACK);
  if (st.s === 0) abstain++;
  if (st.forced) continue;
  computed++;
  if (TH.some(t => Math.abs(st.raw - t) <= 0.10 + 1e-12)) near++;
  if (TH.some(t => Math.abs(st.raw - t) < 0.10 - 1e-12)) nearStrict++;
  if (TH.some(t => Math.abs(st.raw - t) <= 0.10)) nearRaw++;   // the original audit's test: no tolerance
}
out.cells = PACK.clauses.length * PACK.countries.length;
out.computed_cells = computed;
out.near_boundary_within_0_10_inclusive = near;
out.near_boundary_within_0_10_strict = nearStrict;
out.near_boundary_within_0_10_no_tolerance = nearRaw;
out.abstain_cells = abstain;

// Identical blends
const key = c => JSON.stringify(Object.entries(c.w).sort());
const groups = {};
for (const c of PACK.countries) (groups[key(c)] = groups[key(c)] || []).push(c.n);
out.identical_blends = Object.values(groups).filter(g => g.length > 1);

// Pass/fail flips under amendment (31-country Full Assembly)
let flips = 0;
for (const cl of PACK.clauses) {
  const base = Engine.computeDivision(PACK.countries, cl.tags, cl.id, PACK).passed;
  for (const a of PACK.amendments)
    if (Engine.computeDivision(PACK.countries, Engine.applyAmendment(cl.tags, a), null, PACK).passed !== base) flips++;
}
out.amendment_cases = PACK.clauses.length * PACK.amendments.length;
out.amendment_flips = flips;

// Overrides discarded under any amendment
let ovCases = 0, changed = 0;
for (const k of Object.keys(PACK.overrides)) {
  const [name, clauseId] = k.split("|");
  const c = PACK.countries.find(x => x.n === name), cl = PACK.clauses.find(x => x.id === clauseId);
  for (const a of PACK.amendments) {
    ovCases++;
    if (Engine.stanceOf(c, Engine.applyAmendment(cl.tags, a), null, PACK).s !== PACK.overrides[k].s) changed++;
  }
}
out.override_amendment_cases = ovCases;
out.override_changed = changed;

// Rubric probes (audit §5.1)
const kenya = PACK.countries.find(c => c.n === "Kenya");
const c26 = PACK.clauses.find(c => c.id === "2.6");
const probes = {
  keyword_salad: "Honourable delegates, wealthy finance adaptation renewable geothermal 2.6 5% Green Climate Fund pay provided that in exchange.",
  real_offer: "Kenya cannot back new obligations it cannot fund. We would back this text if donors commit the money first, because our grid is already clean and our farmers need help now.",
};
out.rubric = {};
for (const [k, text] of Object.entries(probes)) {
  try {
    // Context: replying to a counterpart's message, word limit 5-40 (the audit's original
    // context was not recorded; with no prior message, engagement scores lower).
    const m = Rubric.markStatement(text, { country: kenya, clause: c26, pack: PACK, counterpartCountry: "Fiji",
      priorCounterpartMessage: "Fiji wants wealthy finance for adaptation.", wordLimitMin: 5, wordLimitMax: 40 });
    out.rubric[k] = m && (m.total + "/" + m.max);
  } catch (e) { out.rubric[k] = "could not run: " + e.message; }
}
console.log(JSON.stringify(out, null, 1));
