# Debating & Model UN platform

A browser-based platform for running Model UN and debating with a class, and The Session, a Model UN campaign for one
player. It runs on one laptop: students join from their own browsers over the local network with a personal sign-in
code. Nothing is installed on student machines and no data leaves the laptop.

## Just want to play The Session?

1. Install **Python 3.12** from [python.org](https://www.python.org/downloads/) (on Windows, tick "Add python.exe to PATH").
2. Get this repository: the green **Code** button → **Download ZIP** (then unzip it), or clone it.
3. Double-click **`play_session.bat`**. The first start sets itself up (it needs the internet once); after that it
   starts the platform in the background and opens The Session in its own window.

Saved games stay in the `data` folder on your computer. Found a bug or have an idea? Open an issue: one per thing,
with the scenario, country and difficulty if it helps.

## What's in it

- **The Session** (`app/modules/sim/`): a one-hour Model UN campaign for one player. Lobby delegations that each have
  their own voice, haggle, make promises you must keep, win regional groups, outplay rival delegations with secret
  instructions, then face a Summit run as the UN runs it (statements, the draft read, caucus, amendments one at a time,
  a final vote). Graded on five paths, with a record, medals and unlockable scenarios. Rules:
  `docs/design/solo-campaign.md`.
- **Model UN with a class** (`mun/`, `chair/`, `floor/`): scenarios as files (`docs/pack-authoring.md`), committees
  and delegations, a shared resolution workspace with amendments and version history, a chair console (speakers list,
  timers, motions, voting, Security Council rules), a projector board with a world map, and evidence-based vote
  prediction.
- **Debating and public speaking** (`debating/`): a classroom runner with timers and bells, a prep studio (cases,
  rebuttals, speech drafts, cue cards), speaking practice, and teacher scoring and comments.
- **Tournaments** (`debating/`, off by default): draws, ballots, ladders, speaker tabs and house points.
- **People** (`people/`): one student list, personal sign-in codes, groups, and role-based access for staff.
- **Practice** (`sim/`): a ten-minute Quick vote, and solo play of any scenario on the board.

## Run it

```
python -m pip install -r requirements.txt
python -m app            # http://localhost:8080 ; add --demo for the demo dataset (fake data only)
```

On Windows, `start_platform.bat` does the same and sets itself up on first run. The first visit to the staff side asks
you to set the coordinator passphrase. Students open the address printed in the window and type their code. Data lives
in `data/` (not in the repository).

It is built for a trusted local network: it serves plain HTTP and must not be exposed to the internet. Demo mode uses
a published demo passphrase, so never use it where real students are signed in.

## Tests

```
python -m pip install -r requirements-dev.txt
python -m playwright install chromium   # once, for the browser tests
python -m pytest                         # engine, API and browser (with axe accessibility checks)
python -m pytest -m "not ui"             # without the browser
```

## Layout

- `app/`: the platform. `engine/` (prediction and rules, pure Python), `db/` (migrations, seeds, scenario packs),
  `modules/<name>/` (routes, services and templates for each part), `templates/` and `static/` (layout, CSS, scripts,
  fonts and icons; no CDN).
- `tests/`: `engine/`, `api/`, `ui/` (Playwright), `security/`.
- `tools/`: build scripts for the map, flags, icons and economic data; the balance simulator for The Session
  (`campaign_sim.py`); load test, backup drill and permissions report.
- `docs/`: design documents, the staff guide, pack authoring, backup and restore, the security review and the
  permissions matrix.
- `server/`, `client/`, `shared/`, `src/`: the original Whip Count game, kept as it was and no longer developed.

Python 3.12, FastAPI, SQLite, Jinja2 and htmx; no JavaScript build step.

## Licence

Copyright © Ben Gough. All rights reserved: see `LICENSE`. Third-party fonts, icons, map, flags and data keep their own
licences: see `THIRD_PARTY.md`.
