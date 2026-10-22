-- 0004 Phase 4: voting-history data (licence-gated), backtests, AI provider log and practice.

-- A dataset that may be imported. Import is refused until the coordinator records
-- that its licence has been checked (D-014). Synthetic test data is marked as such.
CREATE TABLE data_source (
    id                  INTEGER PRIMARY KEY,
    code                TEXT NOT NULL UNIQUE,
    name                TEXT NOT NULL,
    url                 TEXT NOT NULL DEFAULT '',
    licence_found       TEXT NOT NULL DEFAULT '',
    licence_confirmed   INTEGER NOT NULL DEFAULT 0,
    confirmed_by        TEXT NOT NULL DEFAULT '',
    confirmed_on        TEXT NOT NULL DEFAULT '',
    confirmation_note   TEXT NOT NULL DEFAULT '',
    synthetic           INTEGER NOT NULL DEFAULT 0,
    attribution         TEXT NOT NULL DEFAULT '',
    notes               TEXT NOT NULL DEFAULT '',
    deleted_at          TEXT
);

CREATE TABLE un_resolution (
    id              INTEGER PRIMARY KEY,
    source_id       INTEGER NOT NULL REFERENCES data_source(id),
    external_id     TEXT NOT NULL,
    symbol          TEXT NOT NULL DEFAULT '',
    title           TEXT NOT NULL DEFAULT '',
    voted_on        TEXT NOT NULL DEFAULT '',
    session         INTEGER,
    subjects        TEXT NOT NULL DEFAULT '',
    tags            TEXT NOT NULL DEFAULT '',
    topic_id        INTEGER REFERENCES topic(id),
    UNIQUE (source_id, external_id)
);
CREATE INDEX un_resolution_date ON un_resolution(voted_on);

CREATE TABLE un_vote (
    resolution_id   INTEGER NOT NULL REFERENCES un_resolution(id),
    iso3            TEXT NOT NULL,
    vote            TEXT NOT NULL CHECK (vote IN ('yes', 'abstain', 'no', 'absent')),
    PRIMARY KEY (resolution_id, iso3)
);
CREATE INDEX un_vote_iso3 ON un_vote(iso3);

-- Maps words in a resolution's subjects or title to a topic's tags (admin-editable).
CREATE TABLE history_tag_rule (
    id          INTEGER PRIMARY KEY,
    topic_id    INTEGER NOT NULL REFERENCES topic(id),
    tag_code    TEXT NOT NULL,
    keyword     TEXT NOT NULL,
    deleted_at  TEXT,
    UNIQUE (topic_id, tag_code, keyword)
);

CREATE TABLE backtest_report (
    id              INTEGER PRIMARY KEY,
    source_id       INTEGER REFERENCES data_source(id),
    created_at      TEXT NOT NULL,
    params_json     TEXT NOT NULL,
    results_json    TEXT NOT NULL,
    synthetic       INTEGER NOT NULL DEFAULT 0
);

-- Every AI call, without student names or text unless the school has approved that use (spec §8.7).
CREATE TABLE ai_call (
    id              INTEGER PRIMARY KEY,
    provider        TEXT NOT NULL,
    purpose         TEXT NOT NULL CHECK (purpose IN ('position', 'roleplay', 'coach')),
    actor_kind      TEXT NOT NULL,
    summary         TEXT NOT NULL DEFAULT '',
    sources         INTEGER NOT NULL DEFAULT 0,
    stored_as       TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL
);

CREATE TABLE ai_practice (
    id              INTEGER PRIMARY KEY,
    student_id      INTEGER NOT NULL REFERENCES student(id),
    iso3            TEXT NOT NULL REFERENCES country(iso3),
    paragraph_id    INTEGER REFERENCES paragraph(id),
    created_at      TEXT NOT NULL,
    deleted_at      TEXT
);

CREATE TABLE ai_practice_message (
    id              INTEGER PRIMARY KEY,
    practice_id     INTEGER NOT NULL REFERENCES ai_practice(id),
    role            TEXT NOT NULL CHECK (role IN ('student', 'ai')),
    text            TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
