-- D-084: one student list. Each student has an optional year level (5 to 12), so groups can mix year levels and
-- an activity's difficulty can be suggested from who is taking part. NULL = not recorded.
ALTER TABLE student ADD COLUMN year_level INTEGER CHECK (year_level IS NULL OR year_level BETWEEN 5 AND 12);
