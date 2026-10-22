-- 0006 Phase 6 content: prompts that help adjudicators give useful feedback (shown on the ballot, editable in Admin).
CREATE TABLE feedback_prompt (
    id          INTEGER PRIMARY KEY,
    criterion   TEXT NOT NULL CHECK (criterion IN ('matter', 'manner', 'method', 'overall', 'reply')),
    position    INTEGER NOT NULL DEFAULT 0,
    prompt      TEXT NOT NULL,
    deleted_at  TEXT
);
