-- D-090: real-world alliances and groupings shown on the world map (NATO, African Union, ASEAN, G20, BRICS).
-- Kept apart from `bloc` on purpose: blocs feed the prediction model and its calibration; these only colour the map.
CREATE TABLE alignment (
    id          INTEGER PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT '',
    source      TEXT NOT NULL DEFAULT '',
    verified    INTEGER NOT NULL DEFAULT 0,
    notes       TEXT NOT NULL DEFAULT '',
    deleted_at  TEXT
);
CREATE TABLE alignment_member (
    id            INTEGER PRIMARY KEY,
    alignment_id  INTEGER NOT NULL REFERENCES alignment(id),
    iso3          TEXT NOT NULL REFERENCES country(iso3),
    deleted_at    TEXT,
    UNIQUE (alignment_id, iso3)
);
