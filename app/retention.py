"""Retention (D-019, spec R4 and §8.6).

- Soft-deleted rows are purged 30 days after deletion. Purging also blanks the
  copies of that row kept in the change history, so the data is really gone.
  A row that something still points to (for example a student still on a team)
  is kept and reported, never force-deleted.
- Change-history entries older than one school year (365 days) are deleted.

The nightly loop runs this after the nightly backup, so a purge is always
preceded by a backup that still holds the purged rows (kept for 14 days).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from app.db import Actor, pk_of
from app.util import now

SOFT_DELETE_DAYS = 30
EVENT_LOG_DAYS = 365
SYSTEM = Actor("system", None, "Retention")


def _cutoff(days: int) -> str:
    return (datetime.fromtimestamp(now(), timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")


def soft_deleted_tables(conn) -> list[str]:
    names = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    return [t for t in names if any(c[1] == "deleted_at" for c in conn.execute(f"PRAGMA table_info({t})"))]


def purge(db, soft_days: int = SOFT_DELETE_DAYS, log_days: int = EVENT_LOG_DAYS) -> dict:
    """Run both purges. Returns counts for the admin page and the tests."""
    report = {"purged": {}, "kept_referenced": {}, "event_log_deleted": 0}
    soft_cut, log_cut = _cutoff(soft_days), _cutoff(log_days)
    with db.write(SYSTEM) as w:
        conn = w.conn
        for table in soft_deleted_tables(conn):
            pk = pk_of(table)
            keys = [r[0] for r in conn.execute(
                f"SELECT {pk} FROM {table} WHERE deleted_at IS NOT NULL AND deleted_at < ?", (soft_cut,))]
            for key in keys:
                conn.execute("SAVEPOINT purge_row")
                try:
                    conn.execute(f"DELETE FROM {table} WHERE {pk} = ?", (key,))
                except sqlite3.IntegrityError:
                    conn.execute("ROLLBACK TO purge_row")
                    conn.execute("RELEASE purge_row")
                    report["kept_referenced"][table] = report["kept_referenced"].get(table, 0) + 1
                    continue
                conn.execute("RELEASE purge_row")
                conn.execute("UPDATE event_log SET before_json = NULL, after_json = NULL "
                              "WHERE entity = ? AND entity_id = ?", (table, str(key)))
                report["purged"][table] = report["purged"].get(table, 0) + 1
        # Old history: drop links into the rows being removed, then the rows.
        old = "SELECT seq FROM event_log WHERE at < ?"
        conn.execute(f"UPDATE event_log SET undo_of = NULL WHERE undo_of IN ({old})", (log_cut,))
        conn.execute(f"UPDATE event_log SET undone_by = NULL WHERE undone_by IN ({old})", (log_cut,))
        report["event_log_deleted"] = conn.execute("DELETE FROM event_log WHERE at < ?", (log_cut,)).rowcount
        # Names typed into a class run that never matched the roster stay one school year, like the history (D-075).
        report["run_names_cleared"] = conn.execute(
            "UPDATE class_run_speaker SET name = 'Speaker ' || position, comment = '' WHERE student_id IS NULL "
            "AND name NOT LIKE 'Speaker %' AND run_id IN (SELECT id FROM class_run WHERE created_at < ?)", (log_cut,)).rowcount
        if report["purged"] or report["event_log_deleted"]:
            # A record that a purge happened, with counts only (no data).
            w.log("retention", "purge", "purge", None,
                  {"purged": report["purged"], "event_log_deleted": report["event_log_deleted"]})
    return report


ERASED = "Erased"


def erase_student(w, student_id: int) -> dict:
    """Erase a student on request or at exit (spec §8.6), keeping other students' results intact.

    The name goes; the student's own writing (practice reflections, AI practice
    chats, milestone notes, speaker comments about them, speech drafts, friends
    and foes sheets) is deleted, and the text of their messages to other
    delegations is replaced with "[erased]"; their
    devices are signed out; their debate cases, rebuttals and speech drafts are
    deleted, and their name and comments are removed from class debates and
    speaking rounds; and the change history is scrubbed of their name and
    of copies of the deleted rows. What stays, under the name "Erased": team
    membership, speaker scores and votes, because removing them would change
    other students' ladders and house points. Paragraphs written together with a
    class stay as class work.
    """
    conn = w.conn
    st = conn.execute("SELECT * FROM student WHERE id = ?", (student_id,)).fetchone()
    if st is None:
        raise ValueError("no such student")
    scrub: list[tuple[str, int]] = [("student", student_id)]

    def take(table: str, where: str, params: tuple) -> list[int]:
        ids = [r[0] for r in conn.execute(f"SELECT id FROM {table} WHERE {where}", params)]
        scrub.extend((table, i) for i in ids)
        return ids

    practice = take("ai_practice", "student_id = ?", (student_id,))
    if practice:
        marks = ",".join("?" * len(practice))
        take("ai_practice_message", f"practice_id IN ({marks})", tuple(practice))
        conn.execute(f"DELETE FROM ai_practice_message WHERE practice_id IN ({marks})", tuple(practice))
        conn.execute(f"DELETE FROM ai_practice WHERE id IN ({marks})", tuple(practice))
    counts = {"ai_practice": len(practice)}
    for table in ("practice_speech", "student_milestone", "claim_request", "speech_draft", "ff_entry"):
        ids = take(table, "student_id = ?", (student_id,))
        conn.execute(f"DELETE FROM {table} WHERE student_id = ?", (student_id,))
        counts[table] = len(ids)
    # Committee writing other delegations received or acted on stays as a record, with the student's words removed.
    ids = take("delegate_message", "from_student_id = ?", (student_id,))
    conn.execute("UPDATE delegate_message SET body = '[erased]', from_student_id = NULL WHERE from_student_id = ?", (student_id,))
    counts["delegate_message"] = len(ids)
    take("floor_point", "student_id = ?", (student_id,))
    conn.execute("UPDATE floor_point SET note = '', student_id = NULL WHERE student_id = ?", (student_id,))
    take("amendment_suggestion", "student_id = ?", (student_id,))
    conn.execute("UPDATE amendment_suggestion SET note = '', student_id = NULL WHERE student_id = ?", (student_id,))
    take("ballot_score", "speaker_student_id = ?", (student_id,))
    conn.execute("UPDATE ballot_score SET comment = '' WHERE speaker_student_id = ?", (student_id,))
    take("adjudicator", "student_id = ?", (student_id,))
    conn.execute("UPDATE adjudicator SET name = ? WHERE student_id = ?", (ERASED, student_id))
    take("task", "assignee_student_id = ?", (student_id,))
    # Prep studio (D-076, D-077): the student's own cases, rebuttals and speech drafts go.
    cases = take("prep_case", "student_id = ?", (student_id,))
    if cases:
        marks = ",".join("?" * len(cases))
        counts["prep_point"] = len(take("prep_point", f"case_id IN ({marks})", tuple(cases)))
        conn.execute(f"DELETE FROM prep_point WHERE case_id IN ({marks})", tuple(cases))
    conn.execute("DELETE FROM prep_case WHERE student_id = ?", (student_id,))
    counts["prep_case"] = len(cases)
    counts["prep_speech"] = len(take("prep_speech", "student_id = ?", (student_id,)))
    conn.execute("DELETE FROM prep_speech WHERE student_id = ?", (student_id,))
    # Class debates and speaking rounds (D-075): the place in the running order stays, without the name or comment.
    take("class_run_speaker", "student_id = ?", (student_id,))
    conn.execute("UPDATE class_run_speaker SET name = ?, comment = '', topic = '' WHERE student_id = ?", (ERASED, student_id))
    conn.execute("DELETE FROM device_session WHERE student_id = ?", (student_id,))
    from app.web.auth import forget_sessions
    forget_sessions()
    conn.execute("UPDATE student SET first_name = ?, last_initial = '', active = 0 WHERE id = ?", (ERASED, student_id))
    for table, key in scrub:
        conn.execute("UPDATE event_log SET before_json = NULL, after_json = NULL WHERE entity = ? AND entity_id = ?",
                     (table, str(key)))
    conn.execute("UPDATE event_log SET actor_label = ? WHERE actor_kind = 'student' AND actor_id = ?", (ERASED, student_id))
    w.log("student", student_id, "erase", None, {"deleted": counts}, f"class:{st['class_id']}")
    return counts
