# Writing a Model UN scenario pack

A pack is one JSON file that becomes a ready-to-run committee: the countries, a draft resolution, each country's position on each issue, and (for an invented crisis) breaking news. Teachers pick packs on **Start an activity**; students play them alone under **Practice committee → Play a scenario on your own**.

This guide is written so that anyone, including another AI model, can write a pack without knowing the code. Follow it exactly. The file is checked by a validator before it is used.

## The short version

1. Copy `app/db/seed/packs/_template.json` to `app/db/seed/packs/<code>.json`, where `<code>` is a new name in lowercase letters, digits and underscores (for example `tarsany_water`).
2. Replace every `REPLACE:` value. Delete nothing else.
3. Run `python tools/validate_pack.py app/db/seed/packs/<code>.json` and fix every problem it lists until it prints `OK`.
4. Run `python -m pytest tests/api/test_packs.py -q`. It installs every pack and plays it.
5. A teacher reads the whole pack before students see it (see "Before it goes live").

## Rules that are never broken

- **No real students, staff or private people.** No names of anyone at the school. No real private individuals anywhere.
- **Invented crises use invented places.** If `"fictional": true`, the crisis is in an invented country with invented towns, rivers and people. Never set an invented crisis inside a real country, and never make the invented country an obvious stand-in for a real one (no "Ukrainia", no "Gazan Republic"). Real countries still sit on the committee and vote.
- **Positions on a fictional crisis are invented and say so.** The platform labels every one "Unverified demo: not this country's real position". Do not claim they are real.
- **Positions on a real topic need a source, or are left out.** If `"fictional": false`, every country in `positions` needs a link in `sources` to where its stance comes from (an official statement, a recorded UN vote, a government page). The platform stores these as estimates from that source, never as fact. If you are not sure of a country's stance, **leave the country out of `positions`**: the platform treats it as unknown, which is better than a guess.
- **No breaking news on a real topic.** `news` is only allowed when `"fictional": true`. Invented news about real events misleads students.
- **Plain text only.** No HTML, no `<` or `>`, no links inside text fields (links go only in `sources`). The validator rejects them.
- **Suitable for Years 7 to 12.** Serious but not graphic: no detailed violence, no gore, no sexual content, no slurs.
- **Don't write students' speeches.** A pack sets up the committee; it never includes model speeches, opening statements or "what you should say".

## Every field

| Field | What to put | Limits |
|---|---|---|
| `format` | Always `1`. | |
| `code` | The file name without `.json`. | 3–40 of `a-z 0-9 _` |
| `title` | Short title for the picker: "The water crisis in Tarsany". | 5–120 characters |
| `summary` | One or two sentences: what the committee decides and what makes it hard. | 20–300 |
| `level` | `junior` (Years 7–8), `middle` (9–10) or `senior` (11–12). | |
| `fictional` | `true` for an invented crisis, `false` for a real topic. | |
| `committee.type` | `sc` (Security Council: veto, exactly 15 members), `ga_plenary` (General Assembly, simple majority) or `ga_third` (GA Third Committee: human rights and social issues). | |
| `committee.name` | Shown everywhere: "Security Council: the water crisis in Tarsany (practice)". | 5–120 |
| `committee.conference` | The event it sits under: "Practice: the water crisis in Tarsany". | 5–120 |
| `committee.notes` | Optional note for teachers. | up to 400 |
| `topic.code` | Capitals, digits and underscores, starting with a letter, unique to this pack: `SC_TARSANY_WATER`. | 3–41 |
| `topic.name` | Topic as shown to teachers. Add "(fictional scenario)" when fictional. | 5–160 |
| `tags` | The policy levers the resolution pulls: `{"code": "what a clause with this tag does"}`. | 2–12 tags |
| `countries` | ISO-3 codes from `app/db/seed/countries.csv`. A Security Council has exactly 15, including CHN, FRA, GBR, RUS, USA. | 2–60 |
| `resolution.title` | The draft resolution's title. | 5–160 |
| `resolution.preambular` | 1–8 clauses `{"text": ..., "tags": [...]}`. Each ends with a comma. | 20–400 each |
| `resolution.operative` | 2–12 clauses. Each ends with a semicolon; the last may end with a full stop. Each has at least one tag. | 20–400 each |
| `positions` | `{"ISO3": {"tag": -2..2}}`: −2 strongly oppose, −1 oppose, 0 neutral, 1 support, 2 strongly support. Only the pack's countries and tags. | whole numbers only |
| `sources` | `{"ISO3": "https://..."}`, or a list of up to four links when one page doesn't cover all of a country's positions. Required for every positioned country when `fictional` is false. Leave `{}` when fictional. | 1–4 links each |
| `news` | Up to 8 invented updates `{"headline", "body"}`, in the order the Chair will send them. Fictional only. | headline 5–100, body 20–400 |
| `author` | Who wrote it and when: "Claude Haiku, 5 Nov 2026" or a teacher's name. | 2–80 |

## Writing it well

**Tags are the heart of the pack.** The prediction engine works out each country's vote from its position on the tags in a clause. So:
- Make each tag one policy lever that countries genuinely disagree about (ceasefire, sanctions, a UN mission, sovereignty, funding, accountability).
- Write 4–8 tags. Two is too few for an interesting vote; more than ten is hard to reason about.
- Tag every operative clause with what it actually does. A clause that "authorises a mission to protect civilians" is `peacekeeping` and `humanitarian_access`.
- Include at least one tag that splits the permanent members, so the veto matters in a Security Council pack.

**Clauses read like a real resolution.**
- Preambular clauses start with an italicised-style participle and end with a comma: *Recalling*, *Reaffirming*, *Expressing grave concern*, *Welcoming*, *Noting with regret*.
- **Preambular clauses are low stakes.** They recall agreed facts, earlier texts and shared principles that almost every country accepts (the Charter, an earlier resolution, a well-known report). Nothing in the preamble should be worth fighting over: put every contested idea in an operative clause. Give preambular clauses no tags (`"tags": []`).
- Operative clauses start with a verb and end with a semicolon: *Calls upon*, *Demands* (Security Council only), *Decides* (binding, Security Council), *Requests*, *Encourages*, *Urges*, *Authorises*.
- Keep each clause to one idea, so an amendment can change one thing.

**Positions should give a real debate.**
- Spread them: some countries for, some against, some neutral on each tag. If everyone supports everything, the vote is boring.
- Keep each country consistent with its general outlook (a country that values sovereignty is cautious about sanctions and missions), but remember it is invented for a fictional crisis.
- You don't need a position for every country. Unlisted countries vote from the platform's general model of them.

**Real topics (`"fictional": false`).**
- The draft resolution is a practice text written for class. Say so in `committee.notes` ("A practice draft written for class; not an adopted UN text"), and never present a clause as quoting a real resolution.
- Positions must come from something you have actually opened and read. The best sources are recorded UN votes: the UN Digital Library voting record for a resolution, or the UN press release (press.un.org) for the meeting, which lists how each country voted. One page can support many countries, so the same link may appear for several of them in `sources`.
- Map a vote to tags carefully. A country voting yes on a resolution that does X supports X (+1; use +2 only where its statement says it strongly supports it). A no is −1 or −2, and an abstention is 0 or −1. Only set the tags that the source actually covers.
- If you can't open a source that shows a country's stance, leave that country out of `positions`. Never guess, and never write a link you haven't opened.
- A Security Council pack uses the Council's current 15 members. Positions can still come from votes those countries cast elsewhere, such as in the General Assembly.

**News should change the debate.** Each update should give a reason to amend or to vote differently: a ceasefire collapses, a convoy is blocked, mediators offer talks on a condition. Two or three sentences, no graphic detail, no real places.

## The Session: clause cards and events (optional `campaign`)

The Session (the hour-long solo campaign) plays every pack. The optional `campaign` section gives your scenario
its own flavour. Without it, the campaign uses the draft's later clauses as cards and general committee events.

```json
"campaign": {
  "cards": [ {"text": "Calls upon States to ... ;", "tags": ["tag_a"]} ],
  "events": [ {"title": "...", "body": "...", "teaches": "...", "effect": {"spotlight": {"tag": "tag_a", "amount": 0.15}}} ]
}
```

**Cards (up to 10).** Extra operative clauses a student can propose during the campaign, beyond the draft's own.
- Write each as a real operative clause: it starts with a verb and ends with `;` or `.`.
- Give each one to three of the pack's tags, and tag what the clause actually does.
- Offer real choices: a stronger and a weaker version of the same idea, a compromise that bundles two tags, and a
  clause that would win over a group that opposes the draft. Write 5 to 8.
- Make sure every tag appears on at least one card or draft clause.

**Events (up to 8).** Drawn at the start of a turn, about as often as the general events. Each has:
- `title`: 5 to 80 characters;
- `body`: 20 to 300 characters, saying what happens;
- `teaches`: 20 to 200 characters, the true thing about diplomacy it shows;
- exactly one `effect`:

| Effect | What it does | Values |
|---|---|---|
| `ap` | Action points this turn | -1 or 1 |
| `lobby_cost` | Lobbying is cheaper or dearer this turn | -1 or 1 |
| `influence` | Extra Influence | 1 to 3 |
| `region_mood` | A regional group warms to whoever worked hardest with it | 0.1 to 0.2 |
| `spotlight` | Attention turns to one commitment: delegations that support it warm to whoever champions it | `{"tag": ..., "amount": 0.1 to 0.25}` |

Rules for events:
- **On a real topic (`"fictional": false`)**, an event happens *inside the negotiation*: a regional group meets, a
  capital sends new instructions, an expert briefs delegates, an NGO hosts a side event, a co-sponsor wavers. It
  never invents a real-world event, statistic, quote or person, and the game labels it "Hypothetical".
- **On a fictional crisis**, an event may move the crisis on (in invented places, as for `news`).
- **Every event is about this scenario.** General ones (a quiet morning, the speakers list closing) are already built in.
- No real people, nothing graphic, and nothing that tells students what to say.

Write 4 to 6 events, then run the validator.

## Before it goes live

A teacher reads the whole pack and checks:
- Nothing in it is about a real student, staff member or private person.
- A fictional crisis isn't a thinly veiled real conflict.
- Real-topic positions match their sources (open each link).
- The language suits the year level.

Then set `author` to include who checked it ("..., checked by B. Gough, 5 Nov 2026").

## A prompt for another model

Paste this, with the template and this guide attached:

> Write one Model UN scenario pack as JSON for a school platform. Follow docs/pack-authoring.md exactly, starting from _template.json. Scenario: [describe it: committee type, topic, fictional or real, year level]. Output only the JSON, with no comments or explanation. Every value marked REPLACE must be replaced. Use ISO-3 codes from the country list provided. For a fictional crisis, invent the country and every place and person; never base it on a real conflict. For a real topic, give a position only where you can cite a real source link, and leave every other country out of "positions". Do not include speeches or advice to students.

Then run the validator on what comes back and fix what it lists (or paste the list back to the model and ask it to fix exactly those problems).

## How it fits together

- Packs live in `app/db/seed/packs/`. A file whose name starts with `_` is a template and is never offered.
- `app/modules/mun/packfile.py` validates (`validate`), lists (`available`) and installs (`install`) packs. Only packs that pass validation are offered anywhere.
- Installing creates the topic, its tags and the news script once (keyed by `topic.code`), then a new conference, committee, delegations, draft resolution and labelled positions each time.
- `veloria.json` is the reference pack: the Evatt-style Security Council demo (D-063). `comet_halcyon.json` is a second example: a General Assembly pack (20 countries) on an invented comet, where the nuclear-option and mining clauses are the close votes.
