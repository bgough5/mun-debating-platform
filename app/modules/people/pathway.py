"""Student pathway: milestones from first speech to state final (spec Layer 3).

Beyond the spec (D-030): the platform *suggests* milestones it can see in the
records (a speech on a speakers list, a debate spoken in, an amendment tabled,
solo practices), but staff confirm them. A suggestion is never recorded on
its own, so a pathway is always a teacher's judgement.
"""
from __future__ import annotations

from app.db import one, rows, scalar


def _has_table(conn, name: str) -> bool:
    return bool(one(conn, "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)))


def detected(conn, student_id: int) -> dict[str, str]:
    """milestone code -> plain-English evidence found in the records."""
    found: dict[str, str] = {}
    n = scalar(conn, "SELECT COUNT(*) FROM amendment a JOIN delegation_member dm ON dm.delegation_id = a.sponsor_delegation_id "
                     "WHERE dm.student_id = ? AND dm.deleted_at IS NULL AND a.deleted_at IS NULL", (student_id,))
    if n:
        found["first_amendment"] = f"Their delegation sponsored {n} amendment(s)."
    n = scalar(conn, "SELECT COUNT(*) FROM task WHERE assignee_student_id = ? AND status = 'done' AND deleted_at IS NULL", (student_id,))
    if n:
        found["lobbying_task"] = f"{n} lobbying task(s) marked done."
    if _has_table(conn, "speakers_list_entry"):
        n = scalar(conn, "SELECT COUNT(*) FROM speakers_list_entry WHERE student_id = ? AND status = 'done'", (student_id,))
        if n:
            found["first_mun_speech"] = f"Spoke {n} time(s) on a speakers list."
    if _has_table(conn, "team_member"):
        n = scalar(conn, "SELECT COUNT(DISTINCT bs.ballot_id) FROM ballot_score bs JOIN ballot b ON b.id = bs.ballot_id "
                         "WHERE bs.speaker_student_id = ? AND b.deleted_at IS NULL", (student_id,))
        if n:
            found["first_debate"] = f"Scored as a speaker in {n} ballot(s)."
    if _has_table(conn, "practice_speech"):
        n = scalar(conn, "SELECT COUNT(*) FROM practice_speech WHERE student_id = ? AND deleted_at IS NULL", (student_id,))
        if n >= 1:
            found["first_speech"] = f"Recorded {n} practice speech(es)."
        if n >= 5:
            found["solo_practice_5"] = f"Recorded {n} practice speeches."
    return found


def pathway(conn, student_id: int) -> dict:
    ms = rows(conn, "SELECT * FROM pathway_milestone WHERE deleted_at IS NULL ORDER BY position")
    got = {r["milestone_id"]: r for r in rows(conn, "SELECT * FROM student_milestone WHERE student_id = ? AND deleted_at IS NULL",
                                              (student_id,))}
    seen = detected(conn, student_id)
    items = []
    for m in ms:
        a = got.get(m["id"])
        items.append({**m, "achieved": a, "suggested": (seen.get(m["code"]) if not a else None)})
    done = sum(1 for i in items if i["achieved"])
    nxt = next((i for i in items if not i["achieved"]), None)
    return {"milestones": items, "done": done, "total": len(items), "next": nxt}
