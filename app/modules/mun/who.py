"""Who did it, in Model UN (D-086): "Ben G, Australia" wherever a student acts.

A country can hold any number of students (one, or four, or uneven numbers across the committee), so the country
alone doesn't say who sent a message, raised a point, drafted an amendment or cast the vote. Rows that store the
student use it; for the rest (motions, amendments, signatures, roll call) the change log already records which
account wrote the row, so nothing new is stored.
"""
from __future__ import annotations

from app.db import rows
from app.util import display_name


def label(name: str, country: str) -> str:
    """ "Ben G, Australia"; just the country when no student is known (the chair, or the engine)."""
    return f"{name}, {country}" if name and country else (country or name or "")


def student_names(conn, ids) -> dict[int, str]:
    ids = sorted({i for i in ids if i})
    if not ids:
        return {}
    marks = ",".join("?" * len(ids))
    return {r["id"]: display_name(r["first_name"], r["last_initial"])
            for r in rows(conn, f"SELECT id, first_name, last_initial FROM student WHERE id IN ({marks})", ids)}


def acted_by(conn, entity: str, ids, actions=("create",)) -> dict[int, int]:
    """{row id: student id} for rows of `entity` whose latest of `actions` was made by a student (from the change log)."""
    ids = sorted({int(i) for i in ids if i})
    if not ids:
        return {}
    marks, acts = ",".join("?" * len(ids)), ",".join("?" * len(actions))
    out: dict[int, int] = {}
    for r in rows(conn, f"SELECT entity_id, actor_kind, actor_id FROM event_log WHERE entity = ? AND entity_id IN ({marks}) "
                        f"AND action IN ({acts}) ORDER BY seq", [entity, *[str(i) for i in ids], *actions]):
        if r["actor_kind"] == "student" and r["actor_id"]:
            out[int(r["entity_id"])] = r["actor_id"]
        else:
            out.pop(int(r["entity_id"]), None)        # a later action by staff: no student to name
    return out


def name_rows(conn, items: list[dict], country_key: str, entity: str | None = None, student_key: str | None = None,
              out_key: str = "by", actions=("create",)) -> list[dict]:
    """Add item[out_key] = "Ben G, Australia" to each item, from its student column or from the change log."""
    if student_key:
        sids = {it["id"]: it.get(student_key) for it in items}
    else:
        sids = acted_by(conn, entity, [it["id"] for it in items], actions)
    names = student_names(conn, sids.values())
    for it in items:
        it[out_key] = label(names.get(sids.get(it["id"]), ""), it.get(country_key) or "")
    return items


def co_delegates(conn, delegation_id: int) -> list[dict]:
    """Everyone holding a country, head of delegation first."""
    out = rows(conn, "SELECT st.id, st.first_name, st.last_initial, dm.role FROM delegation_member dm JOIN student st ON st.id = dm.student_id "
                     "WHERE dm.delegation_id = ? AND dm.deleted_at IS NULL AND st.deleted_at IS NULL "
                     "ORDER BY dm.role = 'head' DESC, st.first_name, st.last_initial", (delegation_id,))
    for s in out:
        s["name"] = display_name(s["first_name"], s["last_initial"])
    return out
