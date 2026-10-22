-- 0001 Phase 1: reference data, people, MUN workflow, prediction, event log.
-- Plain SQL, applied in order by app/db/migrate.py. Never edit an applied
-- migration; add a new numbered file instead.

-- ---------- Reference data (admin-editable, seeded from CSV) ----------

CREATE TABLE country (
    iso3        TEXT PRIMARY KEY CHECK (length(iso3) = 3),
    name        TEXT NOT NULL,
    un_member   INTEGER NOT NULL DEFAULT 1 CHECK (un_member IN (0, 1)),
    p5          INTEGER NOT NULL DEFAULT 0 CHECK (p5 IN (0, 1)),
    region      TEXT NOT NULL DEFAULT '',
    flag_svg    TEXT NOT NULL DEFAULT '',
    notes       TEXT NOT NULL DEFAULT '',
    deleted_at  TEXT
);

CREATE TABLE bloc (
    id          INTEGER PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'negotiating_bloc'
                CHECK (kind IN ('regional_group', 'negotiating_bloc', 'political_group', 'economic_group')),
    cohesion    REAL NOT NULL DEFAULT 0.3 CHECK (cohesion >= 0 AND cohesion <= 0.95),
    source      TEXT NOT NULL DEFAULT '',
    verified    INTEGER NOT NULL DEFAULT 0 CHECK (verified IN (0, 1)),
    notes       TEXT NOT NULL DEFAULT '',
    deleted_at  TEXT
);

CREATE TABLE bloc_member (
    id          INTEGER PRIMARY KEY,
    bloc_id     INTEGER NOT NULL REFERENCES bloc(id),
    iso3        TEXT NOT NULL REFERENCES country(iso3),
    from_date   TEXT NOT NULL DEFAULT '',
    to_date     TEXT NOT NULL DEFAULT '',
    source      TEXT NOT NULL DEFAULT '',
    deleted_at  TEXT,
    UNIQUE (bloc_id, iso3)
);

CREATE TABLE voting_rule (
    id              INTEGER PRIMARY KEY,
    code            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    threshold_num   INTEGER NOT NULL DEFAULT 1,
    threshold_den   INTEGER NOT NULL DEFAULT 2 CHECK (threshold_den > 0),
    denominator     TEXT NOT NULL DEFAULT 'voting' CHECK (denominator IN ('voting', 'present', 'members')),
    at_threshold    TEXT NOT NULL DEFAULT 'fail' CHECK (at_threshold IN ('pass', 'fail')),
    min_yes         INTEGER NOT NULL DEFAULT 0,
    veto_iso3       TEXT NOT NULL DEFAULT '',
    notes           TEXT NOT NULL DEFAULT '',
    deleted_at      TEXT
);

CREATE TABLE procedure_rule_set (
    id                      INTEGER PRIMARY KEY,
    code                    TEXT NOT NULL UNIQUE,
    name                    TEXT NOT NULL,
    speaking_time_default   INTEGER NOT NULL DEFAULT 90,
    notes                   TEXT NOT NULL DEFAULT '',
    deleted_at              TEXT
);

CREATE TABLE procedure_motion (
    id                  INTEGER PRIMARY KEY,
    rule_set_id         INTEGER NOT NULL REFERENCES procedure_rule_set(id),
    code                TEXT NOT NULL,
    name                TEXT NOT NULL,
    precedence          INTEGER NOT NULL DEFAULT 50,
    voting_rule_id      INTEGER REFERENCES voting_rule(id),
    needs_second        INTEGER NOT NULL DEFAULT 1,
    has_duration        INTEGER NOT NULL DEFAULT 0,
    has_speaking_time   INTEGER NOT NULL DEFAULT 0,
    description         TEXT NOT NULL DEFAULT '',
    deleted_at          TEXT,
    UNIQUE (rule_set_id, code)
);

CREATE TABLE committee_type (
    id                      INTEGER PRIMARY KEY,
    code                    TEXT NOT NULL UNIQUE,
    name                    TEXT NOT NULL,
    default_rule_id         INTEGER REFERENCES voting_rule(id),
    default_procedure_id    INTEGER REFERENCES procedure_rule_set(id),
    notes                   TEXT NOT NULL DEFAULT '',
    deleted_at              TEXT
);

CREATE TABLE rubric (
    id          INTEGER PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'mun' CHECK (kind IN ('mun', 'debate_speaker', 'speech', 'adjudicator')),
    levels      INTEGER NOT NULL DEFAULT 5 CHECK (levels BETWEEN 2 AND 10),
    notes       TEXT NOT NULL DEFAULT '',
    deleted_at  TEXT
);

CREATE TABLE rubric_criterion (
    id          INTEGER PRIMARY KEY,
    rubric_id   INTEGER NOT NULL REFERENCES rubric(id),
    position    INTEGER NOT NULL DEFAULT 1,
    code        TEXT NOT NULL,
    name        TEXT NOT NULL,
    min_score   REAL NOT NULL DEFAULT 1,
    max_score   REAL NOT NULL DEFAULT 5,
    weight      REAL NOT NULL DEFAULT 1,
    hint        TEXT NOT NULL DEFAULT '',
    deleted_at  TEXT,
    UNIQUE (rubric_id, code)
);

CREATE TABLE rubric_descriptor (
    id              INTEGER PRIMARY KEY,
    criterion_id    INTEGER NOT NULL REFERENCES rubric_criterion(id),
    level           INTEGER NOT NULL,
    descriptor      TEXT NOT NULL,
    deleted_at      TEXT,
    UNIQUE (criterion_id, level)
);

CREATE TABLE template (
    id          INTEGER PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    kind        TEXT NOT NULL CHECK (kind IN ('minutes', 'run_sheet', 'mc_script', 'position_paper', 'certificate', 'other')),
    name        TEXT NOT NULL,
    body        TEXT NOT NULL DEFAULT '',
    deleted_at  TEXT
);

CREATE TABLE topic (
    id          INTEGER PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    notes       TEXT NOT NULL DEFAULT '',
    deleted_at  TEXT
);

CREATE TABLE tag (
    id          INTEGER PRIMARY KEY,
    topic_id    INTEGER NOT NULL REFERENCES topic(id),
    code        TEXT NOT NULL,
    label       TEXT NOT NULL,
    deleted_at  TEXT,
    UNIQUE (topic_id, code)
);

CREATE TABLE archetype (
    id          INTEGER PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    blurb       TEXT NOT NULL DEFAULT '',
    deleted_at  TEXT
);

CREATE TABLE archetype_affinity (
    id              INTEGER PRIMARY KEY,
    archetype_id    INTEGER NOT NULL REFERENCES archetype(id),
    tag_id          INTEGER NOT NULL REFERENCES tag(id),
    value           REAL NOT NULL,
    source          TEXT NOT NULL DEFAULT 'model estimate, unsourced',
    deleted_at      TEXT,
    UNIQUE (archetype_id, tag_id)
);

CREATE TABLE country_archetype (
    id              INTEGER PRIMARY KEY,
    iso3            TEXT NOT NULL REFERENCES country(iso3),
    archetype_id    INTEGER NOT NULL REFERENCES archetype(id),
    topic_id        INTEGER NOT NULL REFERENCES topic(id),
    weight          REAL NOT NULL CHECK (weight >= 0),
    source          TEXT NOT NULL DEFAULT 'model estimate, unsourced',
    deleted_at      TEXT,
    UNIQUE (iso3, archetype_id, topic_id)
);

CREATE TABLE archetype_line (
    id              INTEGER PRIMARY KEY,
    archetype_id    INTEGER NOT NULL REFERENCES archetype(id),
    stance          INTEGER NOT NULL CHECK (stance BETWEEN -2 AND 2),
    line            TEXT NOT NULL,
    deleted_at      TEXT,
    UNIQUE (archetype_id, stance)
);

CREATE TABLE source_type (
    id              INTEGER PRIMARY KEY,
    code            TEXT NOT NULL UNIQUE,
    label           TEXT NOT NULL,
    shown_as        TEXT NOT NULL,
    weight          REAL NOT NULL CHECK (weight >= 0),
    requires_source INTEGER NOT NULL DEFAULT 1,
    notes           TEXT NOT NULL DEFAULT '',
    deleted_at      TEXT
);

CREATE TABLE model_version (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    params_json TEXT NOT NULL,
    active      INTEGER NOT NULL DEFAULT 0,
    notes       TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);

-- ---------- People ----------

CREATE TABLE class (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,
    year            INTEGER NOT NULL,
    code            TEXT NOT NULL UNIQUE,
    code_set_at     TEXT NOT NULL,
    active          INTEGER NOT NULL DEFAULT 1,
    archived_at     TEXT,
    deleted_at      TEXT
);

CREATE TABLE student (
    id              INTEGER PRIMARY KEY,
    class_id        INTEGER NOT NULL REFERENCES class(id),
    first_name      TEXT NOT NULL CHECK (length(first_name) BETWEEN 1 AND 40),
    last_initial    TEXT NOT NULL DEFAULT '' CHECK (length(last_initial) <= 1),
    active          INTEGER NOT NULL DEFAULT 1,
    deleted_at      TEXT
);

CREATE TABLE staff (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT 'staff' CHECK (role IN ('staff')),
    pass_hash   TEXT NOT NULL DEFAULT '',
    active      INTEGER NOT NULL DEFAULT 1,
    deleted_at  TEXT
);

CREATE TABLE staff_class (
    id          INTEGER PRIMARY KEY,
    staff_id    INTEGER NOT NULL REFERENCES staff(id),
    class_id    INTEGER NOT NULL REFERENCES class(id),
    deleted_at  TEXT,
    UNIQUE (staff_id, class_id)
);

-- One row per signed-in browser. Students: this is the spec's session_device
-- (a name locked to a device). No IP address or fingerprint is stored.
CREATE TABLE device_session (
    id              INTEGER PRIMARY KEY,
    token_hash      TEXT NOT NULL UNIQUE,
    kind            TEXT NOT NULL CHECK (kind IN ('coordinator', 'staff', 'student')),
    staff_id        INTEGER REFERENCES staff(id),
    student_id      INTEGER REFERENCES student(id),
    class_id        INTEGER REFERENCES class(id),
    csrf            TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    last_seen_at    TEXT NOT NULL,
    revoked_at      TEXT
);
CREATE INDEX device_session_student ON device_session(student_id);

-- A second device asking for a name already locked to another device.
CREATE TABLE claim_request (
    id              INTEGER PRIMARY KEY,
    class_id        INTEGER NOT NULL REFERENCES class(id),
    student_id      INTEGER NOT NULL REFERENCES student(id),
    token_hash      TEXT NOT NULL UNIQUE,
    created_at      TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'denied', 'used')),
    decided_at      TEXT,
    decided_by      TEXT
);

CREATE TABLE pathway_milestone (
    id          INTEGER PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    track       TEXT NOT NULL DEFAULT 'both' CHECK (track IN ('mun', 'debating', 'speaking', 'both')),
    position    INTEGER NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    deleted_at  TEXT
);

CREATE TABLE student_milestone (
    id              INTEGER PRIMARY KEY,
    student_id      INTEGER NOT NULL REFERENCES student(id),
    milestone_id    INTEGER NOT NULL REFERENCES pathway_milestone(id),
    achieved_on     TEXT NOT NULL,
    evidence_note   TEXT NOT NULL DEFAULT '',
    recorded_by     TEXT NOT NULL DEFAULT '',
    deleted_at      TEXT,
    UNIQUE (student_id, milestone_id)
);

-- ---------- MUN workflow ----------

CREATE TABLE conference (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    starts_on   TEXT NOT NULL DEFAULT '',
    ends_on     TEXT NOT NULL DEFAULT '',
    organiser   TEXT NOT NULL DEFAULT '',
    notes       TEXT NOT NULL DEFAULT '',
    deleted_at  TEXT
);

CREATE TABLE committee (
    id                      INTEGER PRIMARY KEY,
    conference_id           INTEGER NOT NULL REFERENCES conference(id),
    name                    TEXT NOT NULL,
    committee_type_id       INTEGER REFERENCES committee_type(id),
    voting_rule_id          INTEGER NOT NULL REFERENCES voting_rule(id),
    procedure_rule_set_id   INTEGER REFERENCES procedure_rule_set(id),
    topic_id                INTEGER REFERENCES topic(id),
    class_id                INTEGER REFERENCES class(id),
    deleted_at              TEXT
);

CREATE TABLE delegation (
    id              INTEGER PRIMARY KEY,
    committee_id    INTEGER NOT NULL REFERENCES committee(id),
    iso3            TEXT NOT NULL REFERENCES country(iso3),
    deleted_at      TEXT,
    UNIQUE (committee_id, iso3)
);

CREATE TABLE delegation_member (
    id              INTEGER PRIMARY KEY,
    delegation_id   INTEGER NOT NULL REFERENCES delegation(id),
    student_id      INTEGER NOT NULL REFERENCES student(id),
    role            TEXT NOT NULL DEFAULT 'delegate' CHECK (role IN ('head', 'delegate')),
    deleted_at      TEXT,
    UNIQUE (delegation_id, student_id)
);

CREATE TABLE resolution (
    id              INTEGER PRIMARY KEY,
    committee_id    INTEGER NOT NULL REFERENCES committee(id),
    title           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'tabled', 'passed', 'failed', 'withdrawn')),
    deleted_at      TEXT
);

CREATE TABLE paragraph (
    id                  INTEGER PRIMARY KEY,
    resolution_id       INTEGER NOT NULL REFERENCES resolution(id),
    kind                TEXT NOT NULL CHECK (kind IN ('preambular', 'operative')),
    position            INTEGER NOT NULL,
    owner_delegation_id INTEGER REFERENCES delegation(id),
    current_version_id  INTEGER,
    deleted_at          TEXT
);

CREATE TABLE paragraph_version (
    id                  INTEGER PRIMARY KEY,
    paragraph_id        INTEGER NOT NULL REFERENCES paragraph(id),
    text                TEXT NOT NULL,
    tags                TEXT NOT NULL DEFAULT '',
    author_label        TEXT NOT NULL DEFAULT '',
    created_at          TEXT NOT NULL,
    parent_version_id   INTEGER REFERENCES paragraph_version(id),
    note                TEXT NOT NULL DEFAULT ''
);

CREATE TABLE amendment (
    id                      INTEGER PRIMARY KEY,
    paragraph_id            INTEGER NOT NULL REFERENCES paragraph(id),
    base_version_id         INTEGER NOT NULL REFERENCES paragraph_version(id),
    kind                    TEXT NOT NULL CHECK (kind IN ('add', 'delete', 'replace')),
    proposed_text           TEXT NOT NULL DEFAULT '',
    tags                    TEXT NOT NULL DEFAULT '',
    sponsor_delegation_id   INTEGER REFERENCES delegation(id),
    status                  TEXT NOT NULL DEFAULT 'tabled'
                            CHECK (status IN ('tabled', 'passed', 'failed', 'withdrawn', 'friendly')),
    rationale               TEXT NOT NULL DEFAULT '',
    created_at              TEXT NOT NULL,
    deleted_at              TEXT
);

CREATE TABLE amendment_support (
    id              INTEGER PRIMARY KEY,
    amendment_id    INTEGER NOT NULL REFERENCES amendment(id),
    delegation_id   INTEGER NOT NULL REFERENCES delegation(id),
    kind            TEXT NOT NULL CHECK (kind IN ('sponsor', 'second', 'signatory')),
    seq             INTEGER NOT NULL,
    deleted_at      TEXT,
    UNIQUE (amendment_id, delegation_id, kind)
);

CREATE TABLE evidence (
    id                  INTEGER PRIMARY KEY,
    subject_kind        TEXT NOT NULL CHECK (subject_kind IN ('country', 'bloc')),
    iso3                TEXT REFERENCES country(iso3),
    bloc_id             INTEGER REFERENCES bloc(id),
    target_kind         TEXT NOT NULL CHECK (target_kind IN ('paragraph', 'amendment', 'resolution', 'tag', 'topic')),
    target_id           INTEGER,
    tag_code            TEXT NOT NULL DEFAULT '',
    topic_id            INTEGER REFERENCES topic(id),
    position            INTEGER CHECK (position IS NULL OR position BETWEEN -2 AND 2),
    strength            TEXT NOT NULL DEFAULT 'moderate' CHECK (strength IN ('weak', 'moderate', 'strong')),
    conditional         INTEGER NOT NULL DEFAULT 0,
    condition_text      TEXT NOT NULL DEFAULT '',
    source              TEXT NOT NULL DEFAULT '',
    source_type         TEXT NOT NULL REFERENCES source_type(code),
    stated_on           TEXT NOT NULL DEFAULT '',
    recorded_on         TEXT NOT NULL,
    recorded_by         TEXT NOT NULL DEFAULT '',
    summary             TEXT NOT NULL DEFAULT '',
    deleted_at          TEXT,
    CHECK ((subject_kind = 'country' AND iso3 IS NOT NULL) OR (subject_kind = 'bloc' AND bloc_id IS NOT NULL))
);
CREATE INDEX evidence_iso3 ON evidence(iso3);

CREATE TABLE prediction (
    id                  INTEGER PRIMARY KEY,
    target_kind         TEXT NOT NULL,
    target_id           INTEGER NOT NULL,
    committee_id        INTEGER NOT NULL REFERENCES committee(id),
    rule_id             INTEGER NOT NULL REFERENCES voting_rule(id),
    model_version_id    INTEGER NOT NULL REFERENCES model_version(id),
    seed                INTEGER NOT NULL,
    runs                INTEGER NOT NULL,
    inputs_hash         TEXT NOT NULL,
    inputs_json         TEXT NOT NULL,
    p_pass              REAL NOT NULL,
    mc_se               REAL NOT NULL,
    yes_mean            REAL NOT NULL,
    yes_lo              INTEGER NOT NULL,
    yes_hi              INTEGER NOT NULL,
    unknown_share       REAL NOT NULL,
    created_at          TEXT NOT NULL,
    label               TEXT NOT NULL DEFAULT ''
);

CREATE TABLE prediction_country (
    id              INTEGER PRIMARY KEY,
    prediction_id   INTEGER NOT NULL REFERENCES prediction(id),
    iso3            TEXT NOT NULL,
    p_yes           REAL NOT NULL,
    p_abstain       REAL NOT NULL,
    p_no            REAL NOT NULL,
    mu              REAL NOT NULL,
    sigma           REAL NOT NULL,
    unknown         INTEGER NOT NULL DEFAULT 0,
    UNIQUE (prediction_id, iso3)
);

CREATE TABLE actual_vote (
    id              INTEGER PRIMARY KEY,
    target_kind     TEXT NOT NULL,
    target_id       INTEGER NOT NULL,
    iso3            TEXT NOT NULL REFERENCES country(iso3),
    vote            TEXT NOT NULL CHECK (vote IN ('yes', 'abstain', 'no', 'absent')),
    context         TEXT NOT NULL CHECK (context IN ('conference', 'real_un')),
    prediction_id   INTEGER REFERENCES prediction(id),
    recorded_by     TEXT NOT NULL DEFAULT '',
    recorded_at     TEXT NOT NULL,
    UNIQUE (target_kind, target_id, iso3, context)
);

CREATE TABLE task (
    id                  INTEGER PRIMARY KEY,
    delegation_id       INTEGER NOT NULL REFERENCES delegation(id),
    assignee_student_id INTEGER REFERENCES student(id),
    target_iso3         TEXT REFERENCES country(iso3),
    target_bloc_id      INTEGER REFERENCES bloc(id),
    amendment_id        INTEGER REFERENCES amendment(id),
    paragraph_id        INTEGER REFERENCES paragraph(id),
    title               TEXT NOT NULL,
    talking_points      TEXT NOT NULL DEFAULT '',
    notes               TEXT NOT NULL DEFAULT '',
    status              TEXT NOT NULL DEFAULT 'todo' CHECK (status IN ('todo', 'doing', 'done')),
    due_on              TEXT NOT NULL DEFAULT '',
    created_at          TEXT NOT NULL,
    deleted_at          TEXT
);

-- ---------- History and audit ----------

CREATE TABLE event_log (
    seq             INTEGER PRIMARY KEY AUTOINCREMENT,
    at              TEXT NOT NULL,
    actor_kind      TEXT NOT NULL,
    actor_id        INTEGER,
    actor_label     TEXT NOT NULL DEFAULT '',
    entity          TEXT NOT NULL,
    entity_id       TEXT NOT NULL,
    action          TEXT NOT NULL,
    before_json     TEXT,
    after_json      TEXT,
    channel         TEXT NOT NULL DEFAULT '',
    action_group    TEXT NOT NULL DEFAULT '',
    undo_of         INTEGER REFERENCES event_log(seq),
    undone_by       INTEGER REFERENCES event_log(seq)
);
CREATE INDEX event_log_group ON event_log(action_group);
CREATE INDEX event_log_entity ON event_log(entity, entity_id);
CREATE INDEX event_log_channel ON event_log(channel, seq);
CREATE INDEX event_log_actor ON event_log(actor_kind, actor_id, seq);

CREATE TABLE app_setting (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);
