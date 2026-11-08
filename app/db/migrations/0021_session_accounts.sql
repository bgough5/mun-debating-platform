-- The Session: player accounts (Ben, 9 Nov 2026; D-103). A username and a password, for people who aren't on a
-- school list, so they can keep their progress. Open sign-up is switched OFF until the coordinator records the
-- school's approval (Admin). Kept apart from staff and students: an account can never reach a student's data.
-- Passwords are scrypt hashes (never logged); a browser holds one random token whose SHA-256 is stored here.
CREATE TABLE player_account (
    id             INTEGER PRIMARY KEY,
    username       TEXT NOT NULL,
    username_key   TEXT NOT NULL UNIQUE,          -- lower case, for case-insensitive uniqueness and sign-in
    pass_hash      TEXT NOT NULL DEFAULT '',
    created_at     TEXT NOT NULL,
    last_login_at  TEXT,
    deleted_at     TEXT
);

CREATE TABLE player_session (
    id             INTEGER PRIMARY KEY,
    token_hash     TEXT NOT NULL UNIQUE,
    account_id     INTEGER NOT NULL REFERENCES player_account(id),
    remember       INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL,
    expires_at     TEXT NOT NULL,
    revoked_at     TEXT
);
CREATE INDEX ix_player_session_account ON player_session(account_id);

-- An account's saved campaigns: the same shape as campaign_save, owned by an account instead of a student.
CREATE TABLE account_save (
    id          INTEGER PRIMARY KEY,
    account_id  INTEGER NOT NULL REFERENCES player_account(id),
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
CREATE INDEX ix_account_save_account ON account_save(account_id, deleted_at);
