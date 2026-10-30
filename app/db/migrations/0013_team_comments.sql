-- D-088: a teacher's comment to each side of a class debate on their preparation, shown on that side's team page.
ALTER TABLE class_run ADD COLUMN team_comment_aff TEXT NOT NULL DEFAULT '';
ALTER TABLE class_run ADD COLUMN team_comment_neg TEXT NOT NULL DEFAULT '';
