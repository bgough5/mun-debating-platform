-- 0005 Phase 6: guided MUN simulation (D-060), whip-count exercise (D-061), practice v3.

-- The stages of a committee session and what the chair says at each, per rules of procedure.
-- Admin-editable (Admin -> Procedure stages), so Ben can change the script without code.
CREATE TABLE procedure_stage (
    id              INTEGER PRIMARY KEY,
    rule_set_id     INTEGER NOT NULL REFERENCES procedure_rule_set(id),
    code            TEXT NOT NULL CHECK (code IN ('roll_call', 'agenda', 'opening_speeches', 'caucus', 'draft_resolution',
                                                 'amendments', 'voting_procedure', 'division', 'debrief')),
    position        INTEGER NOT NULL,
    name            TEXT NOT NULL,
    chair_script    TEXT NOT NULL DEFAULT '',      -- what the chair says (placeholders: {committee}, {agenda}, {present}, {majority})
    chair_next      TEXT NOT NULL DEFAULT '',      -- what happens next, for the chair
    student_prompt  TEXT NOT NULL DEFAULT '',      -- what students can do now
    deleted_at      TEXT,
    UNIQUE (rule_set_id, code)
);

ALTER TABLE live_session ADD COLUMN stage TEXT NOT NULL DEFAULT 'roll_call';
ALTER TABLE live_session ADD COLUMN agenda TEXT NOT NULL DEFAULT '';

CREATE TABLE roll_call (
    id              INTEGER PRIMARY KEY,
    session_id      INTEGER NOT NULL REFERENCES live_session(id),
    delegation_id   INTEGER NOT NULL REFERENCES delegation(id),
    status          TEXT NOT NULL CHECK (status IN ('present', 'present_and_voting', 'absent')),
    computed        INTEGER NOT NULL DEFAULT 0,   -- a delegation with no student, answered for by the engine (D-041)
    answered_by     TEXT NOT NULL DEFAULT '',
    answered_at     TEXT NOT NULL,
    UNIQUE (session_id, delegation_id)
);

-- Whip-count exercise: before a division, students predict how named delegations will vote.
CREATE TABLE whip_round (
    id              INTEGER PRIMARY KEY,
    session_id      INTEGER NOT NULL REFERENCES live_session(id),
    target_kind     TEXT NOT NULL CHECK (target_kind IN ('paragraph', 'amendment', 'resolution')),
    target_id       INTEGER NOT NULL,
    title           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'locked', 'cancelled')),
    division_id     INTEGER REFERENCES division(id),
    per_student     INTEGER NOT NULL DEFAULT 5,
    created_at      TEXT NOT NULL,
    locked_at       TEXT
);

CREATE TABLE whip_prediction (
    id              INTEGER PRIMARY KEY,
    round_id        INTEGER NOT NULL REFERENCES whip_round(id),
    student_id      INTEGER NOT NULL REFERENCES student(id),
    delegation_id   INTEGER NOT NULL REFERENCES delegation(id),
    vote            TEXT CHECK (vote IN ('yes', 'abstain', 'no')),     -- NULL until the student predicts
    predicted_at    TEXT,
    UNIQUE (round_id, student_id, delegation_id)
);

-- Staff override of the mandate-fidelity judgement in the debrief (D-009).
CREATE TABLE fidelity_override (
    id              INTEGER PRIMARY KEY,
    division_id     INTEGER NOT NULL REFERENCES division(id),
    delegation_id   INTEGER NOT NULL REFERENCES delegation(id),
    consistent      INTEGER NOT NULL,             -- 1 = the vote was consistent with the country's mandate
    reason          TEXT NOT NULL DEFAULT '',
    decided_by      TEXT NOT NULL DEFAULT '',
    decided_at      TEXT NOT NULL,
    UNIQUE (division_id, delegation_id)
);

-- Practice v3: one or a few students run delegations against a computed chamber.
-- Nothing here changes the class's own evidence, amendments or predictions.
CREATE TABLE sim_practice (
    id              INTEGER PRIMARY KEY,
    owner_student_id INTEGER NOT NULL REFERENCES student(id),
    committee_id    INTEGER NOT NULL REFERENCES committee(id),
    paragraph_id    INTEGER NOT NULL REFERENCES paragraph(id),
    tags            TEXT NOT NULL DEFAULT '',     -- the paragraph's tags as the students have amended them
    amendment_note  TEXT NOT NULL DEFAULT '',
    stage           TEXT NOT NULL DEFAULT 'lobbying' CHECK (stage IN ('lobbying', 'voted')),
    seed            INTEGER NOT NULL,
    result_json     TEXT,
    created_at      TEXT NOT NULL,
    deleted_at      TEXT
);

CREATE TABLE sim_practice_member (
    id              INTEGER PRIMARY KEY,
    practice_id     INTEGER NOT NULL REFERENCES sim_practice(id),
    student_id      INTEGER NOT NULL REFERENCES student(id),
    iso3            TEXT NOT NULL REFERENCES country(iso3),
    vote            TEXT CHECK (vote IN ('yes', 'abstain', 'no')),
    UNIQUE (practice_id, student_id),
    UNIQUE (practice_id, iso3)
);

-- Lobbying in practice: a simulated conversation with a computed delegation (what it said, generated
-- from its archetype and its hidden mandate), then the student's own reading of it as a position.
-- Readings are practice-only sources, weighted like class intel; they never touch class evidence.
CREATE TABLE sim_practice_lobby (
    id              INTEGER PRIMARY KEY,
    practice_id     INTEGER NOT NULL REFERENCES sim_practice(id),
    student_id      INTEGER NOT NULL REFERENCES student(id),
    iso3            TEXT NOT NULL REFERENCES country(iso3),
    heard           TEXT NOT NULL DEFAULT '',
    tags            TEXT NOT NULL DEFAULT '',    -- the paragraph's tags when the conversation happened
    position        INTEGER CHECK (position BETWEEN -2 AND 2),   -- NULL until the student records their reading
    note            TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL
);
