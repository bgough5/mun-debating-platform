// Generates tests/fixtures/stance_parity.json and app/db/seed/legacy_pack_climate2026.json
// from the FROZEN v2 JavaScript (shared/engine.js, shared/flags.js,
// src/pack_climate2026.js). Those files are only read, never modified.
//
// Run from the repo root:  node tools/parity/gen_fixture.js
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const root = path.resolve(__dirname, "..", "..");
const ctx = {};
vm.createContext(ctx);
for (const f of ["shared/engine.js", "shared/flags.js", "src/pack_climate2026.js"]) {
  // Classic scripts declare top-level const; expose them on the context.
  const src = fs.readFileSync(path.join(root, f), "utf8");
  vm.runInContext(src + "\n;this.__last = true;", ctx, { filename: f });
}
const Engine = vm.runInContext("Engine", ctx);
const PACK = vm.runInContext("PACK", ctx);
const Flags = vm.runInContext("Flags", ctx);

// 279 cells: every country x clause, unamended (overrides apply).
const cells = [];
for (const clause of PACK.clauses) {
  for (const c of PACK.countries) {
    const st = Engine.stanceOf(c, clause.tags, clause.id, PACK);
    cells.push({ country: c.n, clause: clause.id, tags: clause.tags, s: st.s,
                 raw: st.raw === undefined ? null : st.raw, forced: !!st.forced });
  }
}

// 54 amendment cases: every clause x amendment. Overrides do NOT apply to
// amended text in v2 (clauseId=null), which is exactly the behaviour the
// parity port must reproduce; the new engine fixes it at the evidence layer.
const amendmentCases = [];
for (const clause of PACK.clauses) {
  for (const a of PACK.amendments) {
    const tags = Engine.applyAmendment(clause.tags, a);
    const div = Engine.computeDivision(PACK.countries, tags, null, PACK);
    amendmentCases.push({
      clause: clause.id, amendment: a.id, tags,
      stances: div.votes.map(v => {
        const st = Engine.stanceOf(v.country, tags, null, PACK);
        return { country: v.country.n, s: st.s, raw: st.raw === undefined ? null : st.raw };
      }),
      yes: div.yes, abstain: div.abstain, no: div.no, passed: div.passed,
    });
  }
}

// Sponsorship: 300 seeded random event sequences through the frozen
// resolveAmendment, so the Python port can be checked case by case.
function mulberry32(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
const rnd = mulberry32(20261022);
const cands = ["strengthen", "soften", "finance", "12", "3"];
const sponsorshipCases = [];
for (let k = 0; k < 300; k++) {
  const n = Math.floor(rnd() * 12);
  const events = [];
  for (let i = 0; i < n; i++) {
    const player = "p" + (1 + Math.floor(rnd() * 5));
    const id = rnd() < 0.1 ? null : cands[Math.floor(rnd() * cands.length)];
    if (rnd() < 0.5) events.push({ seq: i + 1, playerId: player, kind: "amendment_sponsor", payload: { amendmentId: id } });
    else events.push({ seq: i + 1, playerId: player, kind: "amendment_second", payload: { amendmentId: id, seconded: rnd() < 0.75 } });
  }
  const winner = Engine.resolveAmendment(events, cands.map(id => ({ id })));
  sponsorshipCases.push({ events, winner: winner ? winner.id : null });
}

const fixture = {
  generated_by: "tools/parity/gen_fixture.js",
  source_files: ["shared/engine.js", "src/pack_climate2026.js"],
  cells, amendment_cases: amendmentCases, sponsorship_cases: sponsorshipCases,
};
fs.writeFileSync(path.join(root, "tests/fixtures/stance_parity.json"), JSON.stringify(fixture, null, 1));

const flags = {};
for (const c of PACK.countries) flags[c.n] = { code: Flags.CODE_OF[c.n], svg: Flags.svgFor(c.n, 24) };
const pack = JSON.parse(JSON.stringify(PACK));
pack.flags = flags;
fs.writeFileSync(path.join(root, "app/db/seed/legacy_pack_climate2026.json"), JSON.stringify(pack, null, 1));
console.log(`cells=${cells.length} amendment_cases=${amendmentCases.length} sponsorship_cases=${sponsorshipCases.length}`);
