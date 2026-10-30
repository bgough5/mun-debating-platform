-- D-085: saved groups. A named list of students, e.g. "Debating Jr BGO", ticked in one go when starting or resuming an
-- activity. A student can be in any number of saved groups. They don't change who can see whom: that stays with the
-- teacher-access groups (class / staff_class).
CREATE TABLE student_group (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    staff_id    INTEGER REFERENCES staff(id),
    created_at  TEXT NOT NULL,
    deleted_at  TEXT
);

CREATE TABLE student_group_member (
    id          INTEGER PRIMARY KEY,
    group_id    INTEGER NOT NULL REFERENCES student_group(id),
    student_id  INTEGER NOT NULL REFERENCES student(id),
    deleted_at  TEXT
);
CREATE INDEX idx_student_group_member_group ON student_group_member (group_id);
CREATE INDEX idx_student_group_member_student ON student_group_member (student_id);
