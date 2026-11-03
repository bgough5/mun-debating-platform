-- D-094: how a committee's countries are given out, and who is taking part today.
-- country_mode: 'random' (seated at random when the activity starts), 'choose' (students pick while the Chair allows
-- it), 'chair' (the Chair assigns them on the committee page). Committees made before this keep the Chair's way.
ALTER TABLE committee ADD COLUMN country_mode TEXT NOT NULL DEFAULT 'chair';
ALTER TABLE committee ADD COLUMN choosing_open INTEGER NOT NULL DEFAULT 0;

-- The students ticked for an activity. They can open the live session before they have a country, to choose one or
-- wait to be given one. Only ever student ids: no names are copied here.
CREATE TABLE committee_roster (
    id              INTEGER PRIMARY KEY,
    committee_id    INTEGER NOT NULL REFERENCES committee(id),
    student_id      INTEGER NOT NULL REFERENCES student(id),
    deleted_at      TEXT,
    UNIQUE (committee_id, student_id)
);
CREATE INDEX idx_committee_roster_student ON committee_roster (student_id);
