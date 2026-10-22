"""Who may see and run a debating event (server-side, spec §8.3).

- coordinator: everything;
- staff: events for their classes, and school-wide events (carnivals and competitions
  with no class), since every staff member helps run those;
- students: events they are in (team member or adjudicator), or their class's events.
"""
from __future__ import annotations

from app.db import one
from app.web.auth import can_run_class


def debate_access(conn, actor, event_id: int) -> str:
    e = one(conn, "SELECT class_id FROM debate_event WHERE id = ? AND deleted_at IS NULL", (event_id,))
    if not e or actor is None:
        return "none"
    if actor.is_coordinator:
        return "manage"
    if actor.kind == "staff":
        return "manage" if e["class_id"] is None or can_run_class(conn, actor, e["class_id"]) else "none"
    if actor.kind == "student":
        if e["class_id"] is not None and e["class_id"] == actor.class_id:
            return "participate"
        if one(conn, "SELECT 1 FROM team_member tm JOIN team t ON t.id = tm.team_id WHERE tm.student_id = ? AND t.event_id = ? "
                     "AND tm.deleted_at IS NULL", (actor.id, event_id)):
            return "participate"
        if one(conn, "SELECT 1 FROM adjudicator WHERE student_id = ? AND event_id = ? AND deleted_at IS NULL", (actor.id, event_id)):
            return "participate"
    return "none"


def adjudicates(conn, actor, pairing_id: int) -> int | None:
    """The adjudicator id if this student is on the panel for that debate."""
    if actor is None or actor.kind != "student":
        return None
    r = one(conn, "SELECT a.id FROM adjudicator a JOIN pairing_adjudicator pa ON pa.adjudicator_id = a.id "
                  "WHERE a.student_id = ? AND pa.pairing_id = ? AND pa.deleted_at IS NULL", (actor.id, pairing_id))
    return r["id"] if r else None
