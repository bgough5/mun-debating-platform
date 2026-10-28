-- 0007 MUN committee flow v4 (D-068): six stages with an open floor driven by motions, amendments debated and
-- adopted on the floor, points, delegate messages, speech drafts, friends and foes sheets.

-- Stages: the nine fixed stages become six. Caucus, draft resolution and amendments are now all "the floor";
-- division is part of voting procedure. Missing stages (the floor) are added from the seed on start-up.
CREATE TABLE procedure_stage_v4 (
    id              INTEGER PRIMARY KEY,
    rule_set_id     INTEGER NOT NULL REFERENCES procedure_rule_set(id),
    code            TEXT NOT NULL CHECK (code IN ('roll_call', 'agenda', 'opening_speeches', 'floor', 'voting_procedure', 'debrief')),
    position        INTEGER NOT NULL,
    name            TEXT NOT NULL,
    chair_script    TEXT NOT NULL DEFAULT '',
    chair_next      TEXT NOT NULL DEFAULT '',
    student_prompt  TEXT NOT NULL DEFAULT '',
    deleted_at      TEXT,
    UNIQUE (rule_set_id, code)
);
INSERT INTO procedure_stage_v4 (id, rule_set_id, code, position, name, chair_script, chair_next, student_prompt, deleted_at)
    SELECT id, rule_set_id, code,
           CASE code WHEN 'roll_call' THEN 1 WHEN 'agenda' THEN 2 WHEN 'opening_speeches' THEN 3
                     WHEN 'voting_procedure' THEN 5 ELSE 6 END,
           CASE code WHEN 'opening_speeches' THEN 'Opening statements' WHEN 'voting_procedure' THEN 'Voting procedure' ELSE name END,
           chair_script, chair_next, student_prompt, deleted_at
    FROM procedure_stage WHERE code IN ('roll_call', 'agenda', 'opening_speeches', 'voting_procedure', 'debrief');
DROP TABLE procedure_stage;
ALTER TABLE procedure_stage_v4 RENAME TO procedure_stage;

UPDATE live_session SET stage = 'floor' WHERE stage IN ('caucus', 'draft_resolution', 'amendments');
UPDATE live_session SET stage = 'voting_procedure' WHERE stage = 'division';

-- The draft resolution being debated, and the amendment on the floor (debated for and against, then voted).
ALTER TABLE live_session ADD COLUMN resolution_id INTEGER REFERENCES resolution(id);
ALTER TABLE live_session ADD COLUMN floor_amendment_id INTEGER REFERENCES amendment(id);

-- Amendments start as private drafts (submitted_at NULL) visible only to their sponsors.
ALTER TABLE amendment ADD COLUMN submitted_at TEXT;
UPDATE amendment SET submitted_at = created_at;

-- Speakers for and against the amendment on the floor.
ALTER TABLE speakers_list_entry ADD COLUMN amendment_id INTEGER REFERENCES amendment(id);
ALTER TABLE speakers_list_entry ADD COLUMN side TEXT NOT NULL DEFAULT '' CHECK (side IN ('', 'for', 'against'));

-- Points raised from the floor (or from a device) and the chair's answer.
CREATE TABLE floor_point (
    id              INTEGER PRIMARY KEY,
    session_id      INTEGER NOT NULL REFERENCES live_session(id),
    delegation_id   INTEGER NOT NULL REFERENCES delegation(id),
    student_id      INTEGER REFERENCES student(id),
    kind            TEXT NOT NULL CHECK (kind IN ('order', 'privilege', 'inquiry', 'reply')),
    note            TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'raised' CHECK (status IN ('raised', 'answered', 'granted', 'declined', 'withdrawn')),
    created_at      TEXT NOT NULL,
    decided_at      TEXT
);
CREATE INDEX idx_floor_point_session ON floor_point (session_id, status);

-- Messages between delegations (notes passed across the room). Not assessed; the chair can read and hide them.
CREATE TABLE delegate_message (
    id                  INTEGER PRIMARY KEY,
    session_id          INTEGER NOT NULL REFERENCES live_session(id),
    from_delegation_id  INTEGER NOT NULL REFERENCES delegation(id),
    from_student_id     INTEGER REFERENCES student(id),
    to_delegation_id    INTEGER NOT NULL REFERENCES delegation(id),
    body                TEXT NOT NULL,
    hidden_by           TEXT,                       -- set when the chair hides a message
    created_at          TEXT NOT NULL
);
CREATE INDEX idx_delegate_message_to ON delegate_message (session_id, to_delegation_id);
CREATE INDEX idx_delegate_message_from ON delegate_message (session_id, from_delegation_id);

-- A student's own speech drafts for a committee (opening statement, caucus notes). Private to the student.
CREATE TABLE speech_draft (
    id              INTEGER PRIMARY KEY,
    student_id      INTEGER NOT NULL REFERENCES student(id),
    committee_id    INTEGER NOT NULL REFERENCES committee(id),
    kind            TEXT NOT NULL CHECK (kind IN ('opening', 'speech', 'notes')),
    title           TEXT NOT NULL DEFAULT '',
    body            TEXT NOT NULL DEFAULT '',
    updated_at      TEXT NOT NULL,
    deleted_at      TEXT
);
CREATE INDEX idx_speech_draft_owner ON speech_draft (student_id, committee_id);

-- Friends and foes: a student's own reading of each delegation on each operative clause.
CREATE TABLE ff_entry (
    id              INTEGER PRIMARY KEY,
    student_id      INTEGER NOT NULL REFERENCES student(id),
    paragraph_id    INTEGER NOT NULL REFERENCES paragraph(id),
    delegation_id   INTEGER NOT NULL REFERENCES delegation(id),
    stance          TEXT NOT NULL CHECK (stance IN ('friend', 'undecided', 'foe')),
    note            TEXT NOT NULL DEFAULT '',
    updated_at      TEXT NOT NULL,
    UNIQUE (student_id, paragraph_id, delegation_id)
);

-- Suggested edits to someone else's amendment; the sponsors accept (the amendment's text changes) or decline.
CREATE TABLE amendment_suggestion (
    id              INTEGER PRIMARY KEY,
    amendment_id    INTEGER NOT NULL REFERENCES amendment(id),
    delegation_id   INTEGER NOT NULL REFERENCES delegation(id),
    student_id      INTEGER REFERENCES student(id),
    proposed_text   TEXT NOT NULL,
    note            TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'declined', 'withdrawn')),
    created_at      TEXT NOT NULL,
    decided_at      TEXT
);
CREATE INDEX idx_amendment_suggestion ON amendment_suggestion (amendment_id, status);
