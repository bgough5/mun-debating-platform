-- 0003 Phase 3: debating — houses, formats, events, teams, adjudicators, rooms,
-- rounds, draws, ballots, house points, run sheets and MC scripts, practice.

CREATE TABLE house (
    id          INTEGER PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    colour      TEXT NOT NULL DEFAULT '',
    deleted_at  TEXT
);

ALTER TABLE student ADD COLUMN house_id INTEGER REFERENCES house(id);

CREATE TABLE debate_format (
    id                  INTEGER PRIMARY KEY,
    code                TEXT NOT NULL UNIQUE,
    name                TEXT NOT NULL,
    speakers_per_team   INTEGER NOT NULL CHECK (speakers_per_team BETWEEN 1 AND 4),
    reply               INTEGER NOT NULL DEFAULT 0,
    speech_seconds      INTEGER NOT NULL DEFAULT 240,
    reply_seconds       INTEGER NOT NULL DEFAULT 120,
    prep_minutes        INTEGER NOT NULL DEFAULT 30,
    roles               TEXT NOT NULL DEFAULT '',
    notes               TEXT NOT NULL DEFAULT '',
    deleted_at          TEXT
);

CREATE TABLE motion_bank (
    id          INTEGER PRIMARY KEY,
    motion      TEXT NOT NULL,
    topic       TEXT NOT NULL DEFAULT '',
    level       TEXT NOT NULL DEFAULT 'junior' CHECK (level IN ('junior', 'middle', 'senior')),
    source      TEXT NOT NULL DEFAULT '',
    deleted_at  TEXT
);

CREATE TABLE debate_event (
    id                  INTEGER PRIMARY KEY,
    name                TEXT NOT NULL,
    kind                TEXT NOT NULL DEFAULT 'carnival' CHECK (kind IN ('carnival', 'competition', 'class', 'practice')),
    format_id           INTEGER NOT NULL REFERENCES debate_format(id),
    rubric_id           INTEGER NOT NULL REFERENCES rubric(id),
    class_id            INTEGER REFERENCES class(id),
    starts_on           TEXT NOT NULL DEFAULT '',
    start_time          TEXT NOT NULL DEFAULT '09:00',
    round_minutes       INTEGER NOT NULL DEFAULT 60,
    break_minutes       INTEGER NOT NULL DEFAULT 10,
    avoid_same_house    INTEGER NOT NULL DEFAULT 1,
    bye_counts_as_win   INTEGER NOT NULL DEFAULT 1,
    status              TEXT NOT NULL DEFAULT 'setup' CHECK (status IN ('setup', 'running', 'finished')),
    seed                INTEGER NOT NULL DEFAULT 1,
    projector_token     TEXT NOT NULL UNIQUE,
    notes               TEXT NOT NULL DEFAULT '',
    deleted_at          TEXT
);

CREATE TABLE team (
    id                  INTEGER PRIMARY KEY,
    event_id            INTEGER NOT NULL REFERENCES debate_event(id),
    name                TEXT NOT NULL,
    house_id            INTEGER REFERENCES house(id),
    needs_accessible    INTEGER NOT NULL DEFAULT 0,
    active              INTEGER NOT NULL DEFAULT 1,
    deleted_at          TEXT
);
CREATE INDEX team_event ON team(event_id);

CREATE TABLE team_member (
    id          INTEGER PRIMARY KEY,
    team_id     INTEGER NOT NULL REFERENCES team(id),
    student_id  INTEGER NOT NULL REFERENCES student(id),
    position    INTEGER NOT NULL DEFAULT 1,
    deleted_at  TEXT,
    UNIQUE (team_id, student_id)
);

CREATE TABLE adjudicator (
    id          INTEGER PRIMARY KEY,
    event_id    INTEGER NOT NULL REFERENCES debate_event(id),
    name        TEXT NOT NULL,
    staff_id    INTEGER REFERENCES staff(id),
    student_id  INTEGER REFERENCES student(id),
    house_id    INTEGER REFERENCES house(id),
    rating      REAL NOT NULL DEFAULT 5 CHECK (rating BETWEEN 0 AND 10),
    active      INTEGER NOT NULL DEFAULT 1,
    deleted_at  TEXT
);

CREATE TABLE room (
    id          INTEGER PRIMARY KEY,
    event_id    INTEGER NOT NULL REFERENCES debate_event(id),
    name        TEXT NOT NULL,
    accessible  INTEGER NOT NULL DEFAULT 1,
    priority    INTEGER NOT NULL DEFAULT 50,
    active      INTEGER NOT NULL DEFAULT 1,
    deleted_at  TEXT
);

CREATE TABLE debate_round (
    id          INTEGER PRIMARY KEY,
    event_id    INTEGER NOT NULL REFERENCES debate_event(id),
    number      INTEGER NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'power' CHECK (kind IN ('random', 'power')),
    motion      TEXT NOT NULL DEFAULT '',
    info        TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'released', 'closed')),
    motion_released INTEGER NOT NULL DEFAULT 0,
    seed        INTEGER NOT NULL,
    created_at  TEXT NOT NULL,
    deleted_at  TEXT,
    UNIQUE (event_id, number)
);

CREATE TABLE pairing (
    id              INTEGER PRIMARY KEY,
    round_id        INTEGER NOT NULL REFERENCES debate_round(id),
    aff_team_id     INTEGER NOT NULL REFERENCES team(id),
    neg_team_id     INTEGER REFERENCES team(id),
    room_id         INTEGER REFERENCES room(id),
    bracket         REAL NOT NULL DEFAULT 0,
    position        INTEGER NOT NULL,
    note            TEXT NOT NULL DEFAULT '',
    deleted_at      TEXT
);
CREATE INDEX pairing_round ON pairing(round_id);

CREATE TABLE pairing_adjudicator (
    id              INTEGER PRIMARY KEY,
    pairing_id      INTEGER NOT NULL REFERENCES pairing(id),
    adjudicator_id  INTEGER NOT NULL REFERENCES adjudicator(id),
    role            TEXT NOT NULL DEFAULT 'chair' CHECK (role IN ('chair', 'panel', 'trainee')),
    deleted_at      TEXT,
    UNIQUE (pairing_id, adjudicator_id)
);

CREATE TABLE ballot (
    id              INTEGER PRIMARY KEY,
    pairing_id      INTEGER NOT NULL REFERENCES pairing(id),
    adjudicator_id  INTEGER REFERENCES adjudicator(id),
    rubric_id       INTEGER NOT NULL REFERENCES rubric(id),
    winner_team_id  INTEGER NOT NULL REFERENCES team(id),
    aff_total       REAL NOT NULL,
    neg_total       REAL NOT NULL,
    margin          REAL NOT NULL,
    comments        TEXT NOT NULL DEFAULT '',
    entered_by      TEXT NOT NULL DEFAULT '',
    entered_at      TEXT NOT NULL,
    deleted_at      TEXT
);
CREATE INDEX ballot_pairing ON ballot(pairing_id);

CREATE TABLE ballot_score (
    id                  INTEGER PRIMARY KEY,
    ballot_id           INTEGER NOT NULL REFERENCES ballot(id),
    team_id             INTEGER NOT NULL REFERENCES team(id),
    speaker_student_id  INTEGER REFERENCES student(id),
    position            INTEGER NOT NULL,
    criterion_id        INTEGER NOT NULL REFERENCES rubric_criterion(id),
    score               REAL NOT NULL,
    comment             TEXT NOT NULL DEFAULT ''
);
CREATE INDEX ballot_score_ballot ON ballot_score(ballot_id);
CREATE INDEX ballot_score_speaker ON ballot_score(speaker_student_id);

CREATE TABLE adjudicator_feedback (
    id              INTEGER PRIMARY KEY,
    pairing_id      INTEGER NOT NULL REFERENCES pairing(id),
    adjudicator_id  INTEGER NOT NULL REFERENCES adjudicator(id),
    team_id         INTEGER NOT NULL REFERENCES team(id),
    scores_json     TEXT NOT NULL DEFAULT '{}',
    comment         TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    UNIQUE (pairing_id, adjudicator_id, team_id)
);

CREATE TABLE house_points_rule (
    id          INTEGER PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    label       TEXT NOT NULL,
    kind        TEXT NOT NULL CHECK (kind IN ('win', 'participation', 'team_place', 'speaker_place')),
    place       INTEGER,
    points      REAL NOT NULL,
    deleted_at  TEXT
);

CREATE TABLE house_points_entry (
    id              INTEGER PRIMARY KEY,
    event_id        INTEGER REFERENCES debate_event(id),
    house_id        INTEGER NOT NULL REFERENCES house(id),
    points          REAL NOT NULL,
    reason          TEXT NOT NULL,
    source_kind     TEXT NOT NULL DEFAULT 'manual',
    source_id       TEXT NOT NULL DEFAULT '',
    entered_by      TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    reverses_id     INTEGER REFERENCES house_points_entry(id),
    reversed_by_id  INTEGER REFERENCES house_points_entry(id)
);

CREATE TABLE event_document (
    id          INTEGER PRIMARY KEY,
    event_id    INTEGER NOT NULL REFERENCES debate_event(id),
    kind        TEXT NOT NULL CHECK (kind IN ('run_sheet', 'mc_script', 'certificates')),
    version     INTEGER NOT NULL,
    body        TEXT NOT NULL,
    generated   INTEGER NOT NULL DEFAULT 0,
    author      TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    UNIQUE (event_id, kind, version)
);

-- Solo and small-group practice (D-022): a student's own practice speech with a self-review.
CREATE TABLE practice_speech (
    id              INTEGER PRIMARY KEY,
    student_id      INTEGER NOT NULL REFERENCES student(id),
    rubric_id       INTEGER NOT NULL REFERENCES rubric(id),
    topic           TEXT NOT NULL DEFAULT '',
    kind            TEXT NOT NULL DEFAULT 'speech' CHECK (kind IN ('speech', 'debate_1v1', 'debate_small')),
    target_seconds  INTEGER NOT NULL DEFAULT 180,
    actual_seconds  INTEGER,
    self_scores     TEXT NOT NULL DEFAULT '{}',
    reflection      TEXT NOT NULL DEFAULT '',
    peer_label      TEXT NOT NULL DEFAULT '',
    peer_scores     TEXT NOT NULL DEFAULT '{}',
    staff_scores    TEXT NOT NULL DEFAULT '{}',
    staff_comment   TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    deleted_at      TEXT
);
