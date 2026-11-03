-- D-096: Model UN contributions. Most points are counted from the session's own records when they are shown
-- (app/modules/mun/points.py); this table holds only the points the Chair adds by hand, with the reason the student sees.
CREATE TABLE mun_award (
    id              INTEGER PRIMARY KEY,
    session_id      INTEGER NOT NULL REFERENCES live_session(id),
    student_id      INTEGER NOT NULL REFERENCES student(id),
    strand          TEXT NOT NULL CHECK (strand IN ('speaking', 'procedure', 'negotiation', 'reading')),
    points          INTEGER NOT NULL CHECK (points BETWEEN 1 AND 3),
    reason          TEXT NOT NULL,
    entered_by      TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    deleted_at      TEXT
);
CREATE INDEX idx_mun_award_session ON mun_award (session_id, student_id);
