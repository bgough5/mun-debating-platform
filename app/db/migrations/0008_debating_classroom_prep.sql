-- 0008 Debating and public speaking as a classroom and preparation tool (D-074 to D-077): class runs (a debate or a
-- speaking round, projected with a timer), likely arguments for each motion, impromptu topics, speech templates,
-- and students' own cases, rebuttals and speech drafts.

-- A class debate or speaking round run by a teacher (D-075). The run order is computed from these settings.
CREATE TABLE class_run (
    id                  INTEGER PRIMARY KEY,
    kind                TEXT NOT NULL CHECK (kind IN ('debate', 'speeches')),
    title               TEXT NOT NULL DEFAULT '',
    class_id            INTEGER REFERENCES class(id),
    staff_id            INTEGER REFERENCES staff(id),
    motion              TEXT NOT NULL DEFAULT '',
    aff_name            TEXT NOT NULL DEFAULT 'Affirmative',
    neg_name            TEXT NOT NULL DEFAULT 'Negative',
    speakers_per_side   INTEGER NOT NULL DEFAULT 3 CHECK (speakers_per_side BETWEEN 1 AND 4),
    speech_seconds      INTEGER NOT NULL DEFAULT 240,
    reply               INTEGER NOT NULL DEFAULT 0,
    reply_seconds       INTEGER NOT NULL DEFAULT 120,
    warning_seconds     INTEGER NOT NULL DEFAULT 60,
    prep_seconds        INTEGER NOT NULL DEFAULT 0,
    topic_mode          TEXT NOT NULL DEFAULT 'prepared' CHECK (topic_mode IN ('prepared', 'impromptu')),
    think_seconds       INTEGER NOT NULL DEFAULT 60,
    level               TEXT NOT NULL DEFAULT 'middle' CHECK (level IN ('junior', 'middle', 'senior')),
    step                INTEGER NOT NULL DEFAULT 0,
    timer_state         TEXT NOT NULL DEFAULT 'idle' CHECK (timer_state IN ('idle', 'running', 'paused')),
    timer_started_at    REAL,
    timer_elapsed       REAL NOT NULL DEFAULT 0,
    timer_extra         REAL NOT NULL DEFAULT 0,
    step_seconds        TEXT NOT NULL DEFAULT '{}',
    winner              TEXT NOT NULL DEFAULT '' CHECK (winner IN ('', 'aff', 'neg')),
    comment             TEXT NOT NULL DEFAULT '',
    status              TEXT NOT NULL DEFAULT 'ready' CHECK (status IN ('ready', 'running', 'finished')),
    projector_token     TEXT NOT NULL UNIQUE,
    created_at          TEXT NOT NULL,
    deleted_at          TEXT
);
CREATE INDEX idx_class_run_class ON class_run (class_id);

-- A speaker in a run: first name (plus initial) as typed, linked to the roster when it matches (D-075).
CREATE TABLE class_run_speaker (
    id          INTEGER PRIMARY KEY,
    run_id      INTEGER NOT NULL REFERENCES class_run(id),
    side        TEXT NOT NULL DEFAULT '' CHECK (side IN ('', 'aff', 'neg')),
    position    INTEGER NOT NULL,
    name        TEXT NOT NULL DEFAULT '',
    student_id  INTEGER REFERENCES student(id),
    topic       TEXT NOT NULL DEFAULT '',
    scores      TEXT NOT NULL DEFAULT '{}',
    comment     TEXT NOT NULL DEFAULT '',
    deleted_at  TEXT
);
CREATE INDEX idx_class_run_speaker_run ON class_run_speaker (run_id);
CREATE INDEX idx_class_run_speaker_student ON class_run_speaker (student_id);

-- Likely arguments for each side of a motion: starting points to rebut, not evidence (D-076).
CREATE TABLE motion_argument (
    id          INTEGER PRIMARY KEY,
    motion_id   INTEGER NOT NULL REFERENCES motion_bank(id),
    side        TEXT NOT NULL CHECK (side IN ('aff', 'neg')),
    position    INTEGER NOT NULL DEFAULT 1,
    argument    TEXT NOT NULL,
    deleted_at  TEXT
);
CREATE INDEX idx_motion_argument_motion ON motion_argument (motion_id);

CREATE TABLE impromptu_topic (
    id          INTEGER PRIMARY KEY,
    topic       TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'question' CHECK (kind IN ('question', 'object', 'scenario', 'word', 'opinion')),
    level       TEXT NOT NULL DEFAULT 'any' CHECK (level IN ('junior', 'middle', 'senior', 'any')),
    deleted_at  TEXT
);

-- Speech structures (D-077). sections: JSON list of {"key", "label", "prompt"}.
CREATE TABLE speech_template (
    id          INTEGER PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    kind        TEXT NOT NULL CHECK (kind IN ('prepared', 'impromptu')),
    blurb       TEXT NOT NULL DEFAULT '',
    sections    TEXT NOT NULL DEFAULT '[]',
    position    INTEGER NOT NULL DEFAULT 0,
    deleted_at  TEXT
);

-- A student's own case for one side of a motion (D-076).
CREATE TABLE prep_case (
    id              INTEGER PRIMARY KEY,
    student_id      INTEGER NOT NULL REFERENCES student(id),
    motion_id       INTEGER REFERENCES motion_bank(id),
    motion          TEXT NOT NULL,
    side            TEXT NOT NULL CHECK (side IN ('aff', 'neg')),
    definition      TEXT NOT NULL DEFAULT '',
    team_line       TEXT NOT NULL DEFAULT '',
    staff_comment   TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    deleted_at      TEXT
);
CREATE INDEX idx_prep_case_student ON prep_case (student_id);

-- An argument or a rebuttal in a case. parts: JSON {part key: text}.
CREATE TABLE prep_point (
    id                  INTEGER PRIMARY KEY,
    case_id             INTEGER NOT NULL REFERENCES prep_case(id),
    kind                TEXT NOT NULL CHECK (kind IN ('argument', 'rebuttal')),
    position            INTEGER NOT NULL DEFAULT 1,
    speaker             INTEGER,
    source_argument_id  INTEGER REFERENCES motion_argument(id),
    parts               TEXT NOT NULL DEFAULT '{}',
    self_scores         TEXT NOT NULL DEFAULT '{}',
    staff_scores        TEXT NOT NULL DEFAULT '{}',
    updated_at          TEXT NOT NULL,
    deleted_at          TEXT
);
CREATE INDEX idx_prep_point_case ON prep_point (case_id);

-- A student's prepared speech, written section by section from a template (D-077).
CREATE TABLE prep_speech (
    id              INTEGER PRIMARY KEY,
    student_id      INTEGER NOT NULL REFERENCES student(id),
    template_code   TEXT NOT NULL,
    title           TEXT NOT NULL DEFAULT '',
    sections        TEXT NOT NULL DEFAULT '{}',
    target_seconds  INTEGER NOT NULL DEFAULT 180,
    staff_comment   TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    deleted_at      TEXT
);
CREATE INDEX idx_prep_speech_student ON prep_speech (student_id);
