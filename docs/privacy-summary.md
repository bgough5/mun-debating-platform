# Privacy summary — for school sign-off

**What this is:** a summary of what the South Oakleigh debating and Model UN platform stores about students, where, who can see it, and for how long. It is written for the school's privacy and ICT staff to review before any pilot (spec §8.8). It describes the software as built on 22 Oct 2026 (branch `platform-build`). It is not legal advice, and the school's own privacy policy takes precedence; anything below that conflicts with it should be changed in the software.

**Status:** not yet reviewed by the school. Hosting is the coordinator's laptop only (D-002); any other hosting needs written school sign-off first.

## 1. Where the data lives

- One SQLite database file on the coordinator's laptop, in the `data/` folder next to the app. Nothing is stored on any outside server or cloud service.
- Students' browsers connect to the laptop over the school Wi-Fi. Traffic is plain HTTP on the local network (no HTTPS certificate on a laptop). Anyone on the same network who can capture traffic could read page contents. **Decision needed from the school:** whether plain HTTP on the school network is acceptable for a pilot.
- Nightly backups go to `data/backups/` on the same laptop (14 kept). A downloaded backup is a zip of the database: treat it like the laptop itself (encrypted drive, not emailed).
- The laptop's own security (disk encryption, screen lock, school account) is outside the software and is assumed. **Not verified.**

## 2. What is stored about a student

| Data | Why | Notes |
|---|---|---|
| First name; last initial only when two students in a class share a first name | So teachers know who is who, and to print each student's sign-in card | Full names typed in are cut to first name + initial automatically. No surnames, emails, dates of birth, photos, phone numbers, IP addresses or device details are stored. |
| Class; house (for debating) | Grouping and house points | |
| Delegation, team and role | Running MUN and debates | |
| Votes in class divisions; speakers-list entries; motions proposed | The record of a live session (minutes) | |
| Debating speaker scores and adjudicator comments | Ladders, speaker tabs, feedback to the student | Students see only their own. |
| Practice speeches: timings, self-scores, a short reflection, teacher comments | Speaking practice and feedback | |
| Pathway milestones (e.g. "first speech", "chaired a committee") with an optional teacher note | The student's progress through the program | |
| AI practice chats (practice negotiation with an AI "delegation") | Practice | Only if used. With AI off (the default), the "AI" is an offline script on the laptop. |
| A personal sign-in code per student; for each signed-in laptop, a random token's hash, the date it was created and last used | Signs the student in as themselves, on one laptop at a time (D-079) | No IP address, browser details or fingerprint. |
| Change history (who changed what, when) | Undo, version history, minutes, accountability for scores and house points | Names of students who acted appear here; see retention. |

Staff: a display name and a hashed passphrase (scrypt). The coordinator's passphrase hash and any API keys are in `data/config.json` on the laptop, not in the database or the code repository.

## 3. Who can see what (enforced on the server)

- **Coordinator:** everything, including admin, backups, data reset and student erasure.
- **Staff:** the classes they are assigned to, plus school-wide debating events (carnivals). They can't see other classes' students, change reference data, restore backups or erase students.
- **Students:** their own class's live sessions, their own delegation's private material, public documents, and only their own scores, feedback and practice records. A student can't see another class.
- **Projector:** a session or event's public view only, through an unguessable link.

These rules are checked by an automated test that tries every page and action as every role (see `docs/permissions.md`).

## 4. Signing in and impersonation (D-079)

Each student has a personal sign-in code (six letters and numbers) printed on their own card; there is no list of names to pick from, so nobody can choose an absent classmate's name. Signing in on a laptop signs the student out of any other laptop. A code works like a password: anyone who sees a card could sign in as that student, so cards stay with the class set. Wrong codes are throttled. A teacher can give a student a new code at any time, which stops the old one and signs the student out. Everything that affects scores or house points is recorded with who did it and can be reversed. Codes are never exported in CSV files.

## 5. Retention and deletion (D-019, D-054, D-055)

- Deleted items can be restored for 30 days, then they are permanently removed by a nightly job, including the copies of them in the change history.
- The change history is kept for one year, then deleted.
- At the end of the year the coordinator archives each class: students are signed out and records become read-only.
- On request, or when a student leaves the program, the coordinator can **erase** the student: their name becomes "Erased", their own writing is deleted, their devices are signed out and their name is removed from the change history. Their scores and votes stay, unnamed, so other students' results don't change.
- Backups made before an erasure still contain the student's data until they age out (14 days). **Decision needed from the school:** whether that is acceptable or whether erasure must also delete older backups.

## 6. AI features (Phase 4)

- Off by default. The platform ships with an offline provider that calls nothing outside the laptop.
- An outside AI service (an adapter for Anthropic's Claude exists) can be switched on only by the coordinator, only after recording the school's approval and its reference, and only with an API key set on the laptop. It has never been switched on or tested against the live service.
- If switched on: suggestions of a country's position send only the country, the resolution text and already-recorded public sources. Practice chats and speech coaching send the student's message or reflection, **without their name**. Every AI call is logged (purpose, provider and whether it had sources; no student names).
- AI never writes a student's speech, clause or amendment. AI-suggested positions are shown as "AI estimate — verify" with their sources, or stored as unknown if there are none.

## 7. Development and testing

- No real student data is ever in the code repository. All development and testing uses generated fake names (`app/fakedata.py`). A pre-commit check rejects database files and data folders, and an automated test scans the repository for them.
- The "demo" dataset is entirely fake and is kept separate from the real dataset; a banner shows when demo data is on screen.

## 8. Not verified / open questions for the school

1. Plain HTTP on the school network (section 1).
2. Laptop security: encryption, lock screen, who else uses the laptop.
3. Backups older than an erasure (section 5).
4. Whether the year-end archive should delete rather than keep records for students who have left.
5. Whether parents need to be notified before students use the platform.
6. If AI is ever enabled: whether the school approves sending student writing (without names) to an outside AI service, and under what agreement.
