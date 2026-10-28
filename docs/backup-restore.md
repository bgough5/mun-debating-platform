# Backups and restore

## What happens automatically

- Every hour the platform checks whether today's backup exists; if the newest is more than a day old it copies the
  open dataset to `data/backups/<dataset>-<date>-<time>.db` (SQLite's online backup, so it is consistent even
  while a class is using the platform). The newest 14 are kept.
- Straight after that backup, the retention job runs (D-054): items deleted more than 30 days ago are removed for
  good, and change history older than a year is removed.
- Every change is written to the database as it happens. Closing the window or a crash loses nothing that was saved.

Backups sit on the same laptop as the data. **They don't protect against losing the laptop.** Download a backup to
school storage (not email, not a personal drive) at least weekly and before every event.

## Download a backup

Admin → Data → **Download a backup (.zip)**. You get `soc-real-backup-<date>.zip` holding the database and a manifest (when
it was made, how many classes and students). The coordinator passphrase is **not** in the backup.

## Restore (same laptop, or a new one)

1. On the machine to restore onto, install and start the platform (`start_platform.bat`). On a new machine, set a
   coordinator passphrase when asked.
2. Admin → Data. Make sure the dataset you want to replace is the open one (real or demo).
3. Under Backups, choose the zip, tick the confirmation box, **Restore**.
4. The platform checks the file (it must be a platform backup and pass SQLite's integrity check), keeps the current
   data as a file in `data/backups/` first, then swaps the restored data in. Everyone else is signed out; students
   rejoin with the class code.

If the restored file came from an older version of the platform, it is upgraded automatically (migrations run on open).

## Drill (Phase 5) — measured

`python tools/restore_drill.py` runs two separate copies of the platform, each its own process and data folder,
standing in for the laptop and a second machine: A is set up and used through its pages (class, students, staff,
conference), then a backup is downloaded; B is a fresh install that restores A's backup. Result in
`test-results/restore-drill.json`:

| Check | Result (22 Oct 2026, cloud build container) |
|---|---|
| Every table's row count identical after restore | **Yes**: 79 tables, 973 rows, 0 differences |
| Class and all 5 students visible on B's pages | **Yes** |
| SQLite integrity check on B | **ok** |
| B's data before the restore kept as a file | **Yes** (`real-before-restore-<time>.db`) |
| B's own coordinator passphrase still works (passphrase isn't in the backup) | **Yes** |
| Time to restore | 0.07 s (46 KB zip); whole drill 2.1 s |

Also tested in `tests/api/test_backup_restore.py`: restoring needs the confirmation box; a non-zip, a zip without a
backup, a zip from another app and a damaged database are each refused **without** touching the open data; a
student signed in when the backup was made has to sign in again afterwards.

**Not verified:** a restore onto a genuinely different computer (the drill runs on one machine), and on Windows.
Ben should do it once (pilot checklist item C3): download a backup on the laptop, restore it on another computer
with the platform installed, and check the class list.
