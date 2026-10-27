-- 0009 Personal sign-in codes (D-079): each student has their own code, so signing in on a laptop needs no list of
-- names to pick from. Codes are filled in on start-up for students that have none.
ALTER TABLE student ADD COLUMN login_code TEXT;
CREATE UNIQUE INDEX idx_student_login_code ON student (login_code) WHERE login_code IS NOT NULL;
