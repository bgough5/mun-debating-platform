-- The Session (D-101): a signed-in student's saved campaigns. A guest's campaign is never stored here: it lives in
-- their browser, signed by the server so it can't be edited. state_json holds the whole game (it can include the
-- student's own wording of clauses, so erase_student deletes these rows).
CREATE TABLE campaign_save (
    id          INTEGER PRIMARY KEY,
    student_id  INTEGER NOT NULL REFERENCES student(id),
    pack        TEXT NOT NULL,
    iso3        TEXT NOT NULL,
    length      TEXT NOT NULL,
    difficulty  TEXT NOT NULL,
    path        TEXT NOT NULL,
    phase       TEXT NOT NULL,
    chapter     INTEGER NOT NULL DEFAULT 1,
    grade       INTEGER,
    state_json  TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    deleted_at  TEXT
);
CREATE INDEX ix_campaign_save_student ON campaign_save(student_id, deleted_at);
