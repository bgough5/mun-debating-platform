-- D-089: placards students raise from their screen, and breaking-news updates the chair sends to the room.

-- A raised placard: a student asking to be recognised. Lowered by the student, or by the chair (recognised).
CREATE TABLE placard (
    id              INTEGER PRIMARY KEY,
    session_id      INTEGER NOT NULL REFERENCES live_session(id),
    delegation_id   INTEGER NOT NULL REFERENCES delegation(id),
    student_id      INTEGER NOT NULL REFERENCES student(id),
    raised_at       TEXT NOT NULL,
    lowered_at      TEXT,
    lowered_by      TEXT NOT NULL DEFAULT ''
);
CREATE INDEX idx_placard_session ON placard (session_id, lowered_at);

-- Scripted updates for a fictional crisis (the Evatt Veloria scenario), in order. Editable in Admin.
CREATE TABLE crisis_script (
    id              INTEGER PRIMARY KEY,
    topic_code      TEXT NOT NULL,
    position        INTEGER NOT NULL DEFAULT 1,
    headline        TEXT NOT NULL,
    body            TEXT NOT NULL DEFAULT '',
    deleted_at      TEXT
);

-- An update sent during a session: from the script, or written by the chair.
CREATE TABLE crisis_update (
    id              INTEGER PRIMARY KEY,
    session_id      INTEGER NOT NULL REFERENCES live_session(id),
    script_id       INTEGER REFERENCES crisis_script(id),
    headline        TEXT NOT NULL,
    body            TEXT NOT NULL DEFAULT '',
    label           TEXT NOT NULL DEFAULT '',
    sent_at         TEXT NOT NULL,
    deleted_at      TEXT
);
CREATE INDEX idx_crisis_update_session ON crisis_update (session_id);
