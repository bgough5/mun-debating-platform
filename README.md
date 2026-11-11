# Debating & Model UN Platform

A browser-based platform for Model United Nations, debating and public speaking. It combines classroom management, committee simulations, collaborative resolution writing, debating tournaments, speech development and a standalone single-player campaign.

The application runs locally on a host computer and can be accessed by other devices on the same local network through a web browser. It requires no client-side installation.

## Overview

The platform brings together several interconnected tools:

- **Model United Nations:** Committee simulations, delegation management, resolution drafting, amendments, voting and procedural controls.
- **Debating:** Classroom debates, tournament draws, ballots, adjudication, team management and speaker rankings.
- **Public speaking:** Speech preparation, rehearsal, impromptu speaking exercises, timing and assessment.
- **Classroom management:** Student accounts, groups, staff permissions, activity tracking and saved progress.
- **The Session:** A standalone single-player Model UN campaign featuring diplomacy, negotiation, strategic decision-making and scenario progression.
- **Practice game:** A separate, legacy multiplayer and single-player debating simulation.

The platform is designed for local operation, with a central host providing the application and connected devices accessing it through a browser.

## Features

### Model United Nations

A comprehensive Model UN environment supporting:

- Conference, committee and delegation management.
- Country assignments and committee configuration.
- Collaborative resolution drafting, with individual paragraph editing.
- Amendment creation, suggested changes and tracked revisions.
- Version history and undo functionality.
- Clause-level negotiation and delegation positions.
- Evidence-based vote prediction using Monte Carlo simulation.
- Swing-country analysis, lobbying recommendations and amendment comparisons.
- Voting-history calibration and prediction backtesting.
- General Assembly and Security Council voting procedures.
- Security Council veto handling.
- Speakers lists, moderated and unmoderated caucuses.
- Motions, points, divisions, minutes and voting records.
- Committee debriefs and delegate performance analysis.

### Committee management and live sessions

The committee environment provides a structured workflow covering:

1. Roll call.
2. Agenda setting.
3. Opening statements.
4. Committee debate and caucuses.
5. Voting procedure.
6. Debrief and review.

Additional functionality includes:

- Chair controls and editable procedural scripts.
- Live committee updates through WebSockets.
- Individual student workspaces.
- Private speech drafts and delegation preparation.
- Messaging between delegations, visible to the chair.
- Amendment boards and clause-level negotiation tools.
- Whip counts and voting predictions.
- Live voting results and projector displays.
- Practice chambers with simulated delegations.

### Debating and public speaking

A dedicated environment for classroom activities, competition preparation and individual practice.

**Debating tools:**
- Classroom debate scheduling and management.
- Debate preparation using structured arguments and rebuttals.
- Motion libraries and preparation resources.
- Speech drafting using multiple templates.
- Word counts and speech timing.
- Team argument and speech sharing.
- Identification of potential overlap between teammates' arguments.
- Debate practice and rebuttal exercises.

**Public speaking tools:**
- Prepared and impromptu speaking activities.
- Structured speech development.
- Rehearsal and cue-card preparation.
- Speech timing and automated bells.
- Persuasive technique identification.
- Teacher scoring and feedback.
- Speaking rubrics and performance records.

**Classroom runner:**
- Configurable speaking rounds and debate formats.
- Speaker sequencing and time allocation.
- Projector-friendly timers.
- Visual timing indicators and configurable bells.
- Keyboard controls.
- Quick rubric scoring and activity records.

### Speech development and coaching

An integrated speech coach supports students while they write and rehearse.

Features include:

- Live word and sentence counts.
- Estimated speaking duration against a target.
- Reading-level analysis.
- Repeated-word and filler detection.
- Identification of excessively long sentences.
- Persuasive technique tracking.
- Suggested phrases and vocabulary.
- Speech marking and annotation.
- Text-to-speech using the device's available voice.
- Teacher access to read-only coaching information.

Speeches can be converted into editable cue cards, dot points or full-text formats.

Printing options support four cue cards per A4 page.

### Tournaments and competitions

A competition management environment supporting debating tournaments, speaking competitions and multi-activity events.

Features include:

- Event, house, team and room management.
- Adjudicator allocation.
- Random and power-paired draws.
- Rubric-based ballots and adjudication panels.
- Team ladders and individual speaker rankings.
- House points and score reversals.
- Run sheets and MC scripts.
- Projector displays.
- Classroom practice and competition rehearsal.
- Synthetic large-event generation for testing.

### Student and staff management

A shared participant directory supports:

- Student accounts and individual sign-in.
- Year-level categorisation.
- Saved participant groups.
- Staff accounts and permissions.
- Student pathways and milestones.
- Activity tracking and saved progress.
- Teacher access controls.
- Printable sign-in materials.

Participants can be selected for activities individually or through saved groups.

The application also supports guest access to single-player activities. Guest activity is not retained as an individual account record.

### The Session

The Session is a single-player Model UN campaign available at `/session`.

Players assume the role of an ambassador and navigate a series of diplomatic scenarios through negotiation, lobbying, resolution drafting and international summits.

**Campaign structure:**

1. Introduction and onboarding.
2. Scenario chapters involving diplomacy and negotiation.
3. Resolution drafting and delegation lobbying.
4. A structured international summit.
5. Final voting and campaign debrief.

**Gameplay systems:**

- Country dossiers containing real-world development indicators.
- Delegation personalities, interests and diplomatic positions.
- Negotiation and diplomatic agreements.
- Funding, trade, candidacies and sponsorship arrangements.
- Lobbying and coalition-building.
- Intelligence gathering and adviser management.
- Rival delegations with competing objectives.
- Crisis events and changing diplomatic circumstances.
- Political standing and capital confidence.
- Scenario progression and unlockable content.

The summit follows a structured committee process, including statements, draft presentation, caucus, amendments and a final vote.

**Campaign progression:**

- Five scoring pathways.
- Medal-based performance assessment.
- Scenario progression and unlocks.
- Ambassador development and insignia.
- Strategic approaches with different trade-offs.
- A campaign profile available at `/session/profile`.

The game includes optional visual effects and presentation elements that can be disabled independently of the underlying gameplay.

### Intelligence and data analysis

The platform includes an extensible intelligence subsystem supporting:

- Historical voting data.
- Voting-history priors.
- Prediction calibration.
- Backtesting against baseline models.
- Comparative amendment analysis.
- Provider-based AI integration.

External data integrations and AI functionality are optional and are disabled by default unless configured.

### Onboarding and help

The application includes:

- A getting-started wizard.
- Contextual help throughout the interface.
- A glossary.
- Student quick-start guidance.
- Staff documentation.
- Printable instructional materials.

## Architecture

The application uses a modular Python architecture with browser-based interfaces.

### Technology

- **Python:** Application backend and simulation engine.
- **HTML, CSS and JavaScript:** Browser interface.
- **SQLite:** Local application database.
- **WebSockets:** Real-time classroom communication.
- **htmx:** Dynamic browser interactions.
- **Playwright:** Browser automation and UI testing.
- **pytest:** Automated testing.
- **axe-core:** Accessibility testing.

The main application operates without requiring a third-party frontend CDN.

### Repository structure

```
app/
  engine/          Simulation, prediction and rules engines
  db/              Database migrations and seed data
  modules/
    core/          Application infrastructure
    admin/         Administration and configuration
    people/        Participant and staff management
    mun/           Model UN functionality
    chair/         Committee and chair controls
    debating/      Debating and public speaking
    intelligence/  Data analysis and integrations
  templates/       HTML templates
  static/          CSS, JavaScript and static assets

tests/
  engine/          Engine tests
  api/             API tests
  ui/              Browser and accessibility tests
  vendor/          Test dependencies

tools/
  parity/          Simulation parity tools
  windows_smoke.ps1
  restore_drill.py
  loadtest.py
  permissions_report.py
  screenshots.py
  build_icons.py

docs/
  Project specifications and technical documentation
  User guides and operational documentation
  Testing and design documentation

data/              Local application data (not committed)

server/            Legacy practice-game server
client/            Legacy practice-game clients
shared/            Legacy practice-game shared modules
src/               Legacy practice-game source and builds
test/              Legacy practice-game tests
```

## Installation

### Requirements

- Python 3.12.
- Windows for the supplied batch files and PowerShell utilities.
- Internet access for the initial dependency installation.
- A modern browser such as Microsoft Edge or Google Chrome.

The application can also be installed on other operating systems using Python and the standard installation commands.

### Windows installation

Clone the repository or download and extract the ZIP archive.

For a convenient installation, keep the project in a relatively short directory path, such as:

```
C:\Projects\mun-debating-platform
```

Windows installations can encounter path-length limitations when Python dependencies are installed in deeply nested directories.

#### Start the application

Double-click:

```
start_platform.bat
```

Alternatively, run:

```powershell
.\start_platform.ps1
```

On the first run, the application creates a virtual environment and installs the dependencies listed in `requirements.txt`.

The application then starts locally.

### Accessing the application

Once running, open a browser and navigate to:

```
http://localhost:8080/
```

The initial staff visit requires creation of an administrative passphrase.

Other devices on the same local network can access the application through the network address displayed by the startup process.

Student access is managed through individual sign-in credentials.

### Desktop shortcut

A desktop shortcut can be installed using:

```powershell
powershell -ExecutionPolicy Bypass -File tools\install_desktop_shortcut.ps1
```

The shortcut launches the application and opens the relevant browser views.

### Demo mode

Demo mode provides a separate environment for demonstrations and staff training using demonstration data.

Start the application with:

```
start_platform.bat --demo
```

Alternatively, run:

```
python -m app --demo
```

The application also provides controls for switching between available data environments.

### Running on other operating systems

Install the dependencies:

```bash
python -m pip install -r requirements.txt
```

Start the application:

```bash
python -m app
```

Optional arguments:

```bash
python -m app --demo
python -m app --port 8080
```

## The Session: standalone play

The Session can be played independently of the classroom environment.

### Requirements

- Python 3.12.
- Internet access for initial setup.

### Windows

1. Download and extract the repository.
2. Install Python 3.12, ensuring Python is added to PATH.
3. Double-click `play_session.bat`.

The first launch configures the environment and installs the required dependencies. Subsequent launches start the application and open The Session.

Saved games are stored locally in the application's `data` directory.

The standalone launcher is intended for individual play. The main platform remains available through `start_platform.bat`.

## Running the practice game

The repository also includes Whip Count v2, a separate legacy debating simulation.

It is preserved as a standalone practice environment and is not part of the main platform's active development.

### Multiplayer

Start the relay server:

```bash
python server/server.py
```

The server provides the multiplayer WebSocket relay and serves the player and teacher interfaces.

See `server/PROTOCOL.md` for the message contract.

### Single-player

The self-contained single-player build is:

```
src/WhipCount_v2_solo_built.html
```

Open the file directly in a browser. It does not require a server.

To rebuild the single-player version after changing the relevant source files:

```bash
python build_solo.py
```

The earlier version, `src/WhipCount_v1_built.html`, is retained as a historical fallback.

## Testing and development

### Install development dependencies

```bash
python -m pip install -r requirements-dev.txt
```

For browser-based testing, install Chromium:

```bash
python -m playwright install chromium
```

### Run the test suite

Run all tests:

```bash
python -m pytest
```

Run without UI tests:

```bash
python -m pytest -m "not ui"
```

The test suite includes engine, API, browser and accessibility tests.

### Additional development utilities

**Windows smoke test**

```powershell
powershell -ExecutionPolicy Bypass -File tools\windows_smoke.ps1
```

Add `-Browser` to include browser and accessibility checks.

The script creates an isolated test environment, runs checks and reports the results.

**Regenerate the parity fixture**

```bash
node tools/parity/gen_fixture.js
```

**Check exported documents**

```bash
python tools/check_exports.py
```

**Run the load test**

```bash
python tools/loadtest.py --minutes 45
```

**Regenerate the permissions report**

```bash
python tools/permissions_report.py
```

**Run the backup and restore drill**

```bash
python tools/restore_drill.py
```

**Generate application screenshots**

```bash
python tools/screenshots.py
```

**Rebuild the icon sprite**

```bash
python tools/build_icons.py <lucide-static>
```

## Data storage

Application data is stored locally in the `data/` directory.

The main files include:

| File | Purpose |
|---|---|
| `real.db` | Primary application database |
| `demo.db` | Demonstration database |
| `config.json` | Application configuration and authentication settings |
| `backups/` | Local database backups |

The `data/` directory is excluded from version control.

Database backups and configuration files should be treated as sensitive application data. They should not be committed to public repositories or shared through public issue trackers.

## Security and privacy

The application is designed for local operation and supports individual participant accounts, staff permissions and separate demonstration data.

Important considerations:

- Use unique, confidential administrative credentials.
- Keep the application and its dependencies up to date.
- Restrict access to the host computer and its stored data.
- Do not share participant credentials or account links.
- Protect database files and backups.
- Use demonstration data when testing or showcasing the application.
- Review external integrations before enabling them.
- Do not enter confidential or personally identifiable information into external services without appropriate authorisation.
- Avoid including sensitive information in bug reports, screenshots or issue submissions.

Local hosting does not, by itself, guarantee security. Network access, authentication, permissions and data handling should be reviewed before deployment in a live environment.

For further information, consult the security, permissions and privacy documentation.

## Documentation

Additional project documentation is available in the `docs/` directory.

| Document | Description |
|---|---|
| `docs/spec.md` | Project specification |
| `docs/decisions.md` | Architecture and design decisions |
| `docs/audit.md` | Technical audit |
| `docs/phase-reports.md` | Development progress and implementation reports |
| `docs/staff-guide.md` | Application usage and administration |
| `docs/privacy-summary.md` | Privacy and data handling |
| `docs/permissions.md` | Permissions and access controls |
| `docs/backup-restore.md` | Backup and recovery procedures |
| `docs/pilot-checklist.md` | Deployment and operational readiness |
| `docs/design/mun-committee-flow.html` | Committee workflow reference |
| `docs/screens/index.md` | Application screenshot gallery |

## Project status

The main application includes the core Model UN, debating, public speaking, tournament management and single-player campaign functionality.

Development has been organised into successive implementation phases, with supporting reports and testing documentation.

Some optional integrations and deployment capabilities may require additional configuration.

The legacy Whip Count v2 practice game remains available as a separate, frozen implementation.

## Contributing

Contributions, bug reports and suggestions are welcome.

When reporting an issue, include:

- A concise description of the problem.
- The steps required to reproduce it.
- The expected behaviour.
- The actual behaviour.
- Relevant error messages, where available.
- The affected application module.

Please do not include passwords, participant credentials, personal information, database files or confidential application data in public issues.

For changes to the application, run the relevant automated tests before submitting a contribution.

## Licence

No licence has been specified in this repository.

Unless a licence is added, the default copyright rules apply. The source code is not automatically available for unrestricted reuse, modification or redistribution.

---
