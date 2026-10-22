// ============================================================
// WHIP COUNT — TOPIC PACK
// Schema v1. Any pack matching this shape runs in the engine.
// ============================================================
const PACK = {
  meta: {
    title: "Combating Climate Change: Committing to Global Action",
    committee: "United Nations General Assembly",
    conference: "UNAA Victoria Model UN 2026",
    year: 2026,
  },

  // ---- Closed vocabulary of clause attributes. Generalises past climate. ----
  tags: {
    cost_wealthy:   "Imposes cost on wealthy states",
    curb_fossil:    "Constrains fossil fuel production",
    binding:        "Creates binding obligation",
    human_right:    "Asserts a human right",
    agriculture:    "Targets the agriculture sector",
    adapt_finance:  "Provides adaptation / resilience finance",
    indigenous:     "Concerns Indigenous rights",
    lifestyle:      "Requires behavioural or lifestyle change",
    ecosystems:     "Protects ecosystems",
    tech_transfer:  "Demands technology transfer",
  },

  // ---- Diplomatic archetypes. The engine reasons over THESE, not countries. ----
  archetypes: {
    FRONTLINE: {
      name: "Existential Frontline State",
      blurb: "Bears severe harm, contributed almost nothing to the cause. Argues from survival and, increasingly, from law.",
      affinity: { cost_wealthy: 2, curb_fossil: 2, binding: 2, human_right: 2, agriculture: 0, adapt_finance: 2, indigenous: 1, lifestyle: 0, ecosystems: 1, tech_transfer: 2 },
    },
    EXTRACTIVE: {
      name: "Extractive Incumbent",
      blurb: "National economy tied to the activity being regulated. Wants soft verbs, long timelines, 'transition' not 'phase-out'.",
      affinity: { cost_wealthy: -1, curb_fossil: -2, binding: -2, human_right: -1, agriculture: 0, adapt_finance: -1, indigenous: 0, lifestyle: -1, ecosystems: 0, tech_transfer: -1 },
    },
    DONOR: {
      name: "Industrialised Donor",
      blurb: "Wealthy and expected to pay. Backs ambition in principle, resists open-ended financial obligation.",
      affinity: { cost_wealthy: -1, curb_fossil: 1, binding: 0, human_right: 2, agriculture: 1, adapt_finance: 1, indigenous: 1, lifestyle: 1, ecosystems: 2, tech_transfer: 0 },
    },
    EMERGING: {
      name: "Emerging Industrialiser",
      blurb: "Large and growing. High total output, low per-capita. Invokes differentiated responsibility and the right to develop.",
      affinity: { cost_wealthy: 2, curb_fossil: -1, binding: -1, human_right: 0, agriculture: -1, adapt_finance: 2, indigenous: 0, lifestyle: -1, ecosystems: 0, tech_transfer: 2 },
    },
    REFORMER: {
      name: "Credible Reformer",
      blurb: "Mid-sized, punches above its weight through demonstrated results. Bridge-builder who offers its own model as a template.",
      affinity: { cost_wealthy: 1, curb_fossil: 2, binding: 1, human_right: 2, agriculture: 0, adapt_finance: 1, indigenous: 1, lifestyle: 1, ecosystems: 2, tech_transfer: 1 },
    },
    DEVPRIORITY: {
      name: "Development-Priority State",
      blurb: "Capacity-constrained. Will back ambition only where it is financed. Sensitive about external accountability.",
      affinity: { cost_wealthy: 2, curb_fossil: 0, binding: -1, human_right: 1, agriculture: -1, adapt_finance: 2, indigenous: 0, lifestyle: -1, ecosystems: 1, tech_transfer: 2 },
    },
    SOVEREIGNTY: {
      name: "Sovereignty Guardian",
      blurb: "Resists binding international obligation on principle, largely regardless of topic. Suspicious of rights framings and outside review.",
      affinity: { cost_wealthy: -2, curb_fossil: -1, binding: -2, human_right: -2, agriculture: -1, adapt_finance: -2, indigenous: -1, lifestyle: -1, ecosystems: -1, tech_transfer: -1 },
    },
    BROKER: {
      name: "Regional Broker",
      blurb: "Has hosting or convening ambitions and needs the deal to land. Will trade substance for consensus.",
      affinity: { cost_wealthy: 0, curb_fossil: 0, binding: 0, human_right: 1, agriculture: 0, adapt_finance: 1, indigenous: 0, lifestyle: 0, ecosystems: 1, tech_transfer: 1 },
    },
  },

  clauses: [
    { id: "2.1", verb: "Urges", text: "Urges all nations to commit to the goals and deadlines set by the Paris Climate Agreement and increase emission reduction targets to limit the rise in global temperatures to well below two degrees above pre-industrial levels.", tags: ["binding", "curb_fossil"] },
    { id: "2.2", verb: "Requests", text: "Requests that all wealthy industrialised nations invest heavily in research and technologies, including transfer of these technologies to developing countries, that boost renewable energy sources, and phase out their reliance on non-renewable energy sources.", tags: ["cost_wealthy", "curb_fossil", "tech_transfer"] },
    { id: "2.3", verb: "Calls upon", text: "Calls upon all nations to protect their existing forest and invest heavily in reforestation, to improve the state of the world's forests and help absorb harmful carbon dioxide levels.", tags: ["ecosystems"] },
    { id: "2.4", verb: "Invites", text: "Invites States to consider implementing sustainable agricultural practices, mitigating the agriculture sector's negative impact on biodiversity, water resources and climate, and holding the sector accountable.", tags: ["agriculture", "ecosystems"] },
    { id: "2.5", verb: "Encourages", text: "Encourages all States, together with civil society and the private sector, to commit to gradually moving towards a greater reliance on plant-based diets for their citizens.", tags: ["lifestyle", "agriculture"] },
    { id: "2.6", verb: "Suggests", text: "Suggests all wealthy developed States tackle the causes of climate change and increase their financial support to the Green Climate Fund to promote adaptation, resilience and carbon-neutral development in developing countries.", tags: ["cost_wealthy", "adapt_finance"] },
    { id: "2.7", verb: "Further reminds", text: "Further reminds States to provide decent employment and green jobs when transitioning away from fossil fuel economies, including eliminating inefficient fossil fuel subsidies.", tags: ["curb_fossil", "cost_wealthy"] },
    { id: "2.8", verb: "Appeals to", text: "Appeals to all States to consider ways of increasing the representation of Indigenous peoples when negotiating and implementing climate action agreements.", tags: ["indigenous"] },
    { id: "2.9", verb: "Recommends", text: "Recommends Member States recognise the right to a clean, healthy and sustainable environment as a human right under the principles of international law.", tags: ["human_right", "binding"] },
  ],

  // ---- Amendments available to the player. Each mutates the clause's tag
  // set AND its actual displayed text (textOp), via Engine.applyAmendmentText.
  // "replaceVerb" swaps the clause's own leading verb (every clause above
  // declares one); "append" adds a clause to the end of the sentence. Both
  // are generic operations, not authored per-clause, so they still apply
  // unmodified if a future topic pack reuses this amendment schema. ----
  amendments: [
    { id: "strengthen", label: "Strengthen the verb", detail: "Replace the soft verb with “Demands”, creating a clear obligation.", add: ["binding"], remove: [], textOp: { type: "replaceVerb", with: "Demands" } },
    { id: "soften", label: "Soften the verb", detail: "Downgrade to “Invites States to consider”, removing any sense of obligation.", add: [], remove: ["binding"], textOp: { type: "replaceVerb", with: "Invites States to consider" } },
    { id: "finance", label: "Attach finance to it", detail: "Require wealthy States to fund implementation in developing countries.", add: ["adapt_finance", "cost_wealthy"], remove: [], textOp: { type: "append", text: " Wealthy industrialised States shall bear the costs of implementation in developing countries." } },
    { id: "exempt", label: "Exempt developing States", detail: "Limit the obligation to developed States only.", add: [], remove: ["cost_wealthy"], textOp: { type: "append", text: " This obligation applies to developed States only." } },
    { id: "rights", label: "Add a rights framing", detail: "Ground the clause in the right to a clean, healthy and sustainable environment.", add: ["human_right"], remove: [], textOp: { type: "append", text: " This is grounded in the right to a clean, healthy and sustainable environment." } },
    { id: "review", label: "Add a review mechanism", detail: "Require States to report progress for international scrutiny every two years.", add: ["binding"], remove: [], textOp: { type: "append", text: " States shall report on progress under this clause to the Assembly every two years." } },
  ],

  // ---- Countries as WEIGHTED BLENDS of archetypes. This is what makes it generalise. ----
  countries: [
    { n: "Australia",                 g: "Asia-Pacific", w: { DONOR: 45, EXTRACTIVE: 40, BROKER: 15 }, fact: "Holds the COP31 presidency of negotiations in 2026, while remaining one of the world's largest coal and gas exporters." },
    { n: "Barbados",                  g: "Americas",     w: { FRONTLINE: 70, DEVPRIORITY: 30 }, fact: "Author of the Bridgetown Initiative on reforming climate finance." },
    { n: "Brazil",                    g: "Americas",     w: { EMERGING: 60, EXTRACTIVE: 20, BROKER: 20 }, fact: "Hosted COP30 in Belém in 2025; holds most of the Amazon basin." },
    { n: "Canada",                    g: "Americas",     w: { DONOR: 55, EXTRACTIVE: 45 }, fact: "Combines strong climate rhetoric with major oil sands production." },
    { n: "Central African Republic",  g: "Africa",       w: { DEVPRIORITY: 100 }, fact: "Among the lowest emitters on earth, with minimal capacity to adapt." },
    { n: "Chile",                     g: "Americas",     w: { REFORMER: 60, EMERGING: 25, DEVPRIORITY: 15 }, fact: "Rapid solar build-out in the Atacama; a major supplier of transition minerals." },
    { n: "China",                     g: "Asia-Pacific", w: { EMERGING: 55, SOVEREIGNTY: 30, EXTRACTIVE: 15 }, fact: "The largest total emitter and simultaneously the largest installer of renewable capacity." },
    { n: "Costa Rica",                g: "Americas",     w: { REFORMER: 75, DEVPRIORITY: 25 }, fact: "Co-authored the 2022 UNGA resolution recognising the right to a healthy environment; ~99% renewable electricity." },
    { n: "Denmark",                   g: "Europe",       w: { DONOR: 55, REFORMER: 45 }, fact: "Co-founded the Beyond Oil and Gas Alliance while phasing out North Sea extraction." },
    { n: "Egypt",                     g: "Africa",       w: { BROKER: 40, DEVPRIORITY: 35, EXTRACTIVE: 25 }, fact: "Hosted COP27, where the Loss and Damage Fund was agreed." },
    { n: "Fiji",                      g: "Asia-Pacific", w: { FRONTLINE: 75, DEVPRIORITY: 25 }, fact: "First Pacific state to preside over a COP; already relocating coastal villages." },
    { n: "France",                    g: "Europe",       w: { DONOR: 75, REFORMER: 15, SOVEREIGNTY: 10 }, fact: "Draws roughly 70% of its electricity from nuclear power — which clause 2.2 would phase out." },
    { n: "Gambia",                    g: "Africa",       w: { DEVPRIORITY: 85, FRONTLINE: 15 }, fact: "One of very few states whose climate plan has been rated Paris-compatible." },
    { n: "Germany",                   g: "Europe",       w: { DONOR: 70, REFORMER: 30 }, fact: "A leading contributor to the Green Climate Fund; exited coal power on an accelerated timetable." },
    { n: "Greece",                    g: "Europe",       w: { DONOR: 70, BROKER: 30 }, fact: "Devastated by the 2023 wildfires; now a Mediterranean climate-adaptation advocate." },
    { n: "India",                     g: "Asia-Pacific", w: { EMERGING: 65, DEVPRIORITY: 20, SOVEREIGNTY: 15 }, fact: "Secured the change from 'phase out' to 'phase down' coal at COP26." },
    { n: "Japan",                     g: "Asia-Pacific", w: { DONOR: 75, EXTRACTIVE: 25 }, fact: "Heavily import-dependent for energy; a major financier of overseas gas projects." },
    { n: "Kenya",                     g: "Africa",       w: { DEVPRIORITY: 65, REFORMER: 35 }, fact: "Over 80% renewable electricity, largely geothermal; hosted the Africa Climate Summit." },
    { n: "Madagascar",                g: "Africa",       w: { DEVPRIORITY: 80, FRONTLINE: 20 }, fact: "Suffered what was described as the world's first climate-driven famine conditions in the south." },
    { n: "Mexico",                    g: "Americas",     w: { EMERGING: 50, DONOR: 25, BROKER: 25 }, fact: "A major oil producer that has expanded state refining capacity." },
    { n: "Mongolia",                  g: "Asia-Pacific", w: { DEVPRIORITY: 55, EXTRACTIVE: 45 }, fact: "Coal-dependent economy; severe dzud winters are destroying herding livelihoods." },
    { n: "Morocco",                   g: "Africa",       w: { REFORMER: 45, DEVPRIORITY: 30, BROKER: 25 }, fact: "Home to the Noor Ouarzazate complex, among the largest concentrated solar plants in the world." },
    { n: "Philippines",               g: "Asia-Pacific", w: { FRONTLINE: 50, DEVPRIORITY: 30, EMERGING: 20 }, fact: "Struck by some of the most intense typhoons ever recorded; chaired the Climate Vulnerable Forum." },
    { n: "Saudi Arabia",              g: "Africa/M.East",w: { EXTRACTIVE: 70, SOVEREIGNTY: 30 }, fact: "Has consistently resisted explicit fossil fuel phase-out language in COP texts." },
    { n: "South Africa",              g: "Africa",       w: { EMERGING: 55, EXTRACTIVE: 25, DEVPRIORITY: 20 }, fact: "Around 80% coal-powered; pilot recipient of a Just Energy Transition Partnership." },
    { n: "Spain",                     g: "Europe",       w: { DONOR: 70, REFORMER: 30 }, fact: "Facing severe drought and desertification across its southern regions." },
    { n: "Türkiye",              g: "Europe",       w: { BROKER: 50, EMERGING: 30, SOVEREIGNTY: 20 }, fact: "Hosts COP31 in November 2026 — and needs the conference to be seen to succeed." },
    { n: "Tuvalu",                    g: "Asia-Pacific", w: { FRONTLINE: 90, DEVPRIORITY: 10 }, fact: "Building a digital replica of itself to preserve statehood if the territory becomes uninhabitable." },
    { n: "United Kingdom",            g: "Europe",       w: { DONOR: 75, REFORMER: 25 }, fact: "Closed its last coal-fired power station in 2024." },
    { n: "United States of America",  g: "Americas",     w: { SOVEREIGNTY: 65, EXTRACTIVE: 25, DONOR: 10 }, fact: "Withdrew from the Paris Agreement for a second time in January 2026, and from the UNFCCC in February 2026." },
    { n: "Vanuatu",                   g: "Asia-Pacific", w: { FRONTLINE: 85, DEVPRIORITY: 15 }, fact: "Led the campaign that produced the ICJ's July 2025 advisory opinion on states' climate obligations." },
  ],

  // ---- Overrides: where real diplomacy departs from archetype maths. ----
  // Keyed "Country|clause". Forces a stance and supplies a bespoke line.
  overrides: {
    "United States of America|2.1": { s: -2, line: "The United States has withdrawn from the Paris Agreement and cannot be bound by its deadlines." },
    "United States of America|2.9": { s: -2, line: "The United States does not accept the creation of new human rights through General Assembly resolutions." },
    "United States of America|2.6": { s: -2, line: "The United States will not accept open-ended financial obligations to the Green Climate Fund." },
    "Costa Rica|2.9":  { s: 2,  line: "Costa Rica co-authored this very language in 2022. We do not merely support this clause — we wrote it." },
    "Costa Rica|2.3":  { s: 2,  line: "Our Payments for Environmental Services scheme took forest cover from a quarter of our territory to over half. This works." },
    "Costa Rica|2.4":  { s: 0,  line: "Costa Rica supports accountability, but our pineapple and banana growers require transition finance, not blunt condemnation." },
    "Vanuatu|2.6":     { s: 1,  line: "Adaptation finance is welcome, but it is not compensation. Where is loss and damage in this clause?" },
    "Vanuatu|2.1":     { s: 1,  line: "‘Well below two degrees’ is a retreat. The International Court of Justice has confirmed our obligations run further than this." },
    "France|2.2":      { s: -1, line: "France cannot accept nuclear energy being grouped with coal and oil. Nuclear power emits no greenhouse gases." },
    "Saudi Arabia|2.2":{ s: -2, line: "The Kingdom rejects any text singling out particular energy sources for elimination." },
    "Australia|2.2":   { s: -1, line: "Australia supports the transition, but as COP31 president we must bring resource economies with us, not corner them." },
    "Türkiye|2.1": { s: 1, line: "As host of COP31, Türkiye needs this Assembly to arrive in November with momentum, not division." },
    "India|2.2":       { s: 1,  line: "India welcomes technology transfer — but developed nations must fund it, not merely request it of themselves." },
    "Tuvalu|2.1":      { s: 2,  line: "Two degrees is not a target for Tuvalu. It is a description of our disappearance." },
    "Brazil|2.3":      { s: 2,  line: "Brazil accepts this responsibility, and expects the world to pay for the forest it asks us to keep standing." },
    "China|2.2":       { s: 0,  line: "China notes that it manufactures the very technologies this clause asks to be transferred." },
  },

  // ---- Layered reaction lines: archetype-generic, used when no override exists. ----
  lines: {
    FRONTLINE:   { 2: "This is the minimum our survival requires.", 1: "We support this, though it asks too little too slowly.", 0: "We cannot celebrate a clause this weak.", "-1": "This language fails the states already losing territory.", "-2": "We reject text that treats our disappearance as negotiable." },
    EXTRACTIVE:  { 2: "We can accept this, as it imposes no obligation on production.", 1: "We will not oppose language framed as transition rather than prohibition.", 0: "We reserve our position pending clarification.", "-1": "This clause threatens the livelihoods of our energy sector.", "-2": "This is an attack on our economy and we will oppose it outright." },
    DONOR:       { 2: "This reflects the ambition we have long advocated.", 1: "We support this, consistent with our existing commitments.", 0: "We support the intent but question the mechanism.", "-1": "We cannot accept an open-ended call on our treasury.", "-2": "This asks our taxpayers to underwrite obligations without limit." },
    EMERGING:    { 2: "This properly reflects common but differentiated responsibility.", 1: "We support this, provided developed nations move first.", 0: "Our position depends entirely on who is being asked to pay.", "-1": "This constrains our development without financing our alternative.", "-2": "We will not accept a ceiling on growth the industrialised world never faced." },
    REFORMER:    { 2: "We have done this at home and we commend it to the Assembly.", 1: "We support this and can offer our own experience as a model.", 0: "We would prefer implementation detail before committing.", "-1": "We support the goal but this drafting will not achieve it.", "-2": "We cannot support text this poorly constructed." },
    DEVPRIORITY: { 2: "With finance attached, we support this wholeheartedly.", 1: "We support this if the means of implementation follow.", 0: "We cannot commit to what we cannot afford.", "-1": "This asks of us what wealthier states will not do themselves.", "-2": "We reject obligations imposed without the capacity to meet them." },
    SOVEREIGNTY: { 2: "We accept this only because it binds no one.", 1: "We can live with language this permissive.", 0: "We note this clause without endorsing it.", "-1": "This encroaches on matters properly decided nationally.", "-2": "We reject this as an infringement of national sovereignty." },
    BROKER:      { 2: "This is text the whole Assembly can rally behind.", 1: "We support this as a basis for consensus.", 0: "We would counsel compromise before this divides the room.", "-1": "This will cost us votes we cannot afford to lose.", "-2": "Pressing this will fracture the Assembly." },
  },
};
