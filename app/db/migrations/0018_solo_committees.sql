-- D-097: a committee a student made from a scenario pack to play on their own. It belongs to that student: it isn't
-- listed for teachers with the class's committees, and only that student (on its roster) can open it.
ALTER TABLE committee ADD COLUMN solo_student_id INTEGER REFERENCES student(id);
