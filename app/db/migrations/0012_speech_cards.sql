-- D-087: a debate case can hold the speech itself (teammates read it, read-only), and cue cards a student has
-- edited are kept, so the printout matches what they changed. source: 'speech' (prep_speech), 'case' (prep_case)
-- or 'mun' (speech_draft). cards: JSON list of {heading, body}. fingerprint: the speech text it was made from.
ALTER TABLE prep_case ADD COLUMN speech_text TEXT NOT NULL DEFAULT '';

CREATE TABLE cue_card_set (
    id              INTEGER PRIMARY KEY,
    student_id      INTEGER NOT NULL REFERENCES student(id),
    source          TEXT NOT NULL CHECK (source IN ('speech', 'case', 'mun')),
    source_id       INTEGER NOT NULL,
    mode            TEXT NOT NULL CHECK (mode IN ('dots', 'full')),
    cards           TEXT NOT NULL DEFAULT '[]',
    fingerprint     TEXT NOT NULL DEFAULT '',
    updated_at      TEXT NOT NULL,
    deleted_at      TEXT
);
CREATE INDEX idx_cue_card_set_owner ON cue_card_set (student_id, source, source_id, mode);
