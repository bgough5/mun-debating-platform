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
| `sources` | `{"ISO3": "https://..."}`. Required for every positioned country when `fictional` is false. Leave `{}` when fictional. | one link each |
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
- Operative clauses start with a verb and end with a semicolon: *Calls upon*, *Demands* (Security Council only), *Decides* (binding, Security Council), *Requests*, *Encourages*, *Urges*, *Authorises*.
- Keep each clause to one idea, so an amendment can change one thing.

**Positions should give a real debate.**
- Spread them: some countries for, some against, some neutral on each tag. If everyone supports everything, the vote is boring.
- Keep each country consistent with its general outlook (a country that values sovereignty is cautious about sanctions and missions), but remember it is invented for a fictional crisis.
- You don't need a position for every country. Unlisted countries vote from the platform's general model of them.

**News should change the debate.** Each update should give a reason to amend or to vote differently: a ceasefire collapses, a convoy is blocked, mediators offer talks on a condition. Two or three sentences, no graphic detail, no real places.

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
