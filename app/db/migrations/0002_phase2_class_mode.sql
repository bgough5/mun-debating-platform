-- 0002 Phase 2: live sessions (chair tools), paragraph locks, participants.

CREATE TABLE live_session (
    id                  INTEGER PRIMARY KEY,
    committee_id        INTEGER NOT NULL REFERENCES committee(id),
    title               TEXT NOT NULL DEFAULT '',
    chair_label         TEXT NOT NULL DEFAULT '',
    state               TEXT NOT NULL DEFAULT 'open' CHECK (state IN ('open', 'suspended', 'closed')),
    mode                TEXT NOT NULL DEFAULT 'formal' CHECK (mode IN ('formal', 'moderated', 'unmoderated', 'voting')),
    mode_topic          TEXT NOT NULL DEFAULT '',
    speaking_time_s     INTEGER NOT NULL DEFAULT 90,
    projector_token     TEXT NOT NULL UNIQUE,
    current_entry_id    INTEGER,
    current_motion_id   INTEGER,
    current_division_id INTEGER,
    created_at          TEXT NOT NULL,
    closed_at           TEXT
);

CREATE TABLE session_participant (
    id              INTEGER PRIMARY KEY,
    session_id      INTEGER NOT NULL REFERENCES live_session(id),
    student_id      INTEGER NOT NULL REFERENCES student(id),
    joined_at       TEXT NOT NULL,
    last_seen       REAL NOT NULL,
    UNIQUE (session_id, student_id)
);

CREATE TABLE speakers_list_entry (
    id              INTEGER PRIMARY KEY,
    session_id      INTEGER NOT NULL REFERENCES live_session(id),
    list_kind       TEXT NOT NULL DEFAULT 'general' CHECK (list_kind IN ('general', 'moderated')),
    delegation_id   INTEGER NOT NULL REFERENCES delegation(id),
    student_id      INTEGER REFERENCES student(id),
    position        REAL NOT NULL,
    status          TEXT NOT NULL DEFAULT 'waiting' CHECK (status IN ('waiting', 'speaking', 'done', 'withdrawn')),
    added_by        TEXT NOT NULL DEFAULT '',
    added_at        TEXT NOT NULL,
    spoke_at        TEXT,
    yielded_to      TEXT NOT NULL DEFAULT ''
);
CREATE INDEX sle_session ON speakers_list_entry(session_id, status, position);

CREATE TABLE timer (
    id              INTEGER PRIMARY KEY,
    session_id      INTEGER NOT NULL REFERENCES live_session(id),
    kind            TEXT NOT NULL DEFAULT 'speaker' CHECK (kind IN ('speaker', 'caucus', 'general')),
    label           TEXT NOT NULL DEFAULT '',
    duration_s      REAL NOT NULL,
    extended_s      REAL NOT NULL DEFAULT 0,
    elapsed_s       REAL NOT NULL DEFAULT 0,
    started_at      REAL,
    state           TEXT NOT NULL DEFAULT 'idle' CHECK (state IN ('idle', 'running', 'paused', 'done')),
    entry_id        INTEGER REFERENCES speakers_list_entry(id),
    created_at      TEXT NOT NULL
);

-- Per-student extra speaking time (WCAG 2.2.1 timing adjustable). Applied automatically to their speeches.
CREATE TABLE timing_adjustment (
    id              INTEGER PRIMARY KEY,
    student_id      INTEGER NOT NULL UNIQUE REFERENCES student(id),
    extra_percent   INTEGER NOT NULL DEFAULT 0 CHECK (extra_percent BETWEEN 0 AND 200),
    note            TEXT NOT NULL DEFAULT ''
);

CREATE TABLE motion (
    id                      INTEGER PRIMARY KEY,
    session_id              INTEGER NOT NULL REFERENCES live_session(id),
    procedure_motion_id     INTEGER NOT NULL REFERENCES procedure_motion(id),
    proposer_delegation_id  INTEGER REFERENCES delegation(id),
    seconder_delegation_id  INTEGER REFERENCES delegation(id),
    duration_s              INTEGER,
    speaking_time_s         INTEGER,
    topic                   TEXT NOT NULL DEFAULT '',
    status                  TEXT NOT NULL DEFAULT 'proposed'
                            CHECK (status IN ('proposed', 'voting', 'passed', 'failed', 'withdrawn', 'ruled_out')),
    division_id             INTEGER,
    created_at              TEXT NOT NULL,
    decided_at              TEXT
);

CREATE TABLE division (
    id              INTEGER PRIMARY KEY,
    session_id      INTEGER NOT NULL REFERENCES live_session(id),
    title           TEXT NOT NULL,
    target_kind     TEXT NOT NULL CHECK (target_kind IN ('motion', 'resolution', 'paragraph', 'amendment', 'custom')),
    target_id       INTEGER,
    rule_id         INTEGER NOT NULL REFERENCES voting_rule(id),
    procedural      INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed', 'cancelled')),
    yes             INTEGER NOT NULL DEFAULT 0,
    abstain         INTEGER NOT NULL DEFAULT 0,
    no              INTEGER NOT NULL DEFAULT 0,
    absent          INTEGER NOT NULL DEFAULT 0,
    computed        INTEGER NOT NULL DEFAULT 0,
    passed          INTEGER,
    summary         TEXT NOT NULL DEFAULT '',
    prediction_id   INTEGER REFERENCES prediction(id),
    opened_at       TEXT NOT NULL,
    closed_at       TEXT
);

CREATE TABLE division_vote (
    id              INTEGER PRIMARY KEY,
    division_id     INTEGER NOT NULL REFERENCES division(id),
    iso3            TEXT NOT NULL REFERENCES country(iso3),
    delegation_id   INTEGER REFERENCES delegation(id),
    vote            TEXT NOT NULL CHECK (vote IN ('yes', 'abstain', 'no', 'absent')),
    computed        INTEGER NOT NULL DEFAULT 0,
    cast_by         TEXT NOT NULL DEFAULT '',
    cast_at         TEXT NOT NULL,
    UNIQUE (division_id, iso3)
);

CREATE TABLE minutes (
    id              INTEGER PRIMARY KEY,
    session_id      INTEGER NOT NULL REFERENCES live_session(id),
    version         INTEGER NOT NULL,
    body            TEXT NOT NULL,
    generated       INTEGER NOT NULL DEFAULT 0,
    author          TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    UNIQUE (session_id, version)
);

-- One editor per paragraph at a time (D-004). A lock lapses if its holder stops sending heartbeats.
CREATE TABLE paragraph_lock (
    paragraph_id    INTEGER PRIMARY KEY REFERENCES paragraph(id),
    holder_kind     TEXT NOT NULL,
    holder_id       INTEGER,
    holder_label    TEXT NOT NULL,
    acquired_at     REAL NOT NULL,
    heartbeat_at    REAL NOT NULL
);
