"""Saved groups (D-085): a named list of students, such as "Debating Jr BGO", ticked in one go.

A student can be in any number of saved groups. Groups are shared among staff, so anyone can tick one, but only the
person who made it (or the coordinator) can rename, change or delete it. They don't change who can see whom: each
person sees and ticks only the members they could see anyway (teacher access, `class`/`staff_class`).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.db import one, rows
from app.errors import UserError
from app.util import now_iso
from app.web.auth import require_staff
from app.web.http import form_data, form_int, redirect
from app.web.templating import render

router = APIRouter(prefix="/people")
NAME_LIMIT = 60


def _visible_ids(conn, actor) -> set[int]:
    from app.modules.people.routes import visible_students
    return {st["id"] for st in visible_students(conn, actor)}


def can_edit(actor, group: dict) -> bool:
    return actor.is_coordinator or (actor.kind == "staff" and group["staff_id"] == actor.id)


def saved_groups(conn, actor) -> list[dict]:
    """Every saved group with at least one member this person can see, with those members' ids, by name."""
    seen = _visible_ids(conn, actor)
    out = []
    for g in rows(conn, "SELECT g.*, s.name AS owner FROM student_group g LEFT JOIN staff s ON s.id = g.staff_id "
                        "WHERE g.deleted_at IS NULL ORDER BY g.name COLLATE NOCASE"):
        ids = {r["student_id"] for r in rows(conn, "SELECT m.student_id FROM student_group_member m JOIN student st ON st.id = m.student_id "
                                                   "WHERE m.group_id = ? AND m.deleted_at IS NULL AND st.deleted_at IS NULL AND st.active = 1",
                                             (g["id"],))}
        g["members"] = ids & seen
        g["n"] = len(g["members"])
        g["owner"] = g["owner"] or "Coordinator"
        g["mine"] = can_edit(actor, g)
        if g["n"] or g["mine"]:
            out.append(g)
    return out


def get_group(conn, actor, gid: int) -> dict:
    g = next((x for x in saved_groups(conn, actor) if x["id"] == gid), None)
    if not g:
        raise UserError("That group doesn't exist.", 404)
    return g


def _clean_name(conn, name: str, gid: int | None = None) -> str:
    name = " ".join((name or "").split())[:NAME_LIMIT]
    if not name:
        raise UserError("Give the group a name, for example “Debating Jr BGO”.")
    clash = one(conn, "SELECT id FROM student_group WHERE name = ? COLLATE NOCASE AND deleted_at IS NULL AND id != ?", (name, gid or 0))
    if clash:
        raise UserError(f"There's already a group called “{name}”. Choose another name, or open that group to change it.")
    return name


def save_group(w, actor, name: str, ticked: set[int], gid: int | None = None) -> tuple[int, str]:
    """Create a group, or rename it and set its members. Members this person can't see are left as they are."""
    seen = _visible_ids(w.conn, actor)
    want = ticked & seen
    if gid is None:
        if not want:
            raise UserError("Tick the students to save in the group first.")
        name = _clean_name(w.conn, name)
        gid = w.insert("student_group", {"name": name, "staff_id": actor.id if actor.kind == "staff" else None, "created_at": now_iso()})
        have: dict = {}
        verb = "Saved"
    else:
        g = one(w.conn, "SELECT * FROM student_group WHERE id = ? AND deleted_at IS NULL", (gid,))
        if not g:
            raise UserError("That group doesn't exist.", 404)
        if not can_edit(actor, g):
            raise UserError("Only the person who made this group, or the coordinator, can change it. You can still tick it.", 403)
        name = _clean_name(w.conn, name, gid)
        if name != g["name"]:
            w.update("student_group", gid, {"name": name})
        have = {r["student_id"]: r["id"] for r in rows(w.conn, "SELECT id, student_id FROM student_group_member "
                                                               "WHERE group_id = ? AND deleted_at IS NULL", (gid,))}
        verb = "Saved changes to"
    for sid in want - set(have):
        w.insert("student_group_member", {"group_id": gid, "student_id": sid})
    for sid, mid in have.items():
        if sid in seen and sid not in want:
            w.soft_delete("student_group_member", mid)
    n = len(want | {s for s in have if s not in seen})
    return gid, f"{verb} “{name}”: {n} student{'' if n == 1 else 's'}."


def picker_op(db, actor, form, ticked: set[int]) -> tuple[set[int], str] | None:
    """The tick list's own buttons, shared by every page that shows it: add first-timers, tick a saved group, or save
    the ticked students as a new group. Returns the new ticks and a message, or None when the form is for the page."""
    if form.get("op") == "add":
        from app.modules.people.routes import add_to_list
        with db.write(actor) as w:
            msg, new = add_to_list(w, actor, (form.get("new_names") or "").splitlines(), form.get("new_year_level"))
        return ticked | set(new), msg + " They're ticked below."
    gid = form_int(form.get("tick_group"))
    if gid:
        with db.read() as conn:
            g = get_group(conn, actor, gid)
        return ticked | g["members"], f"Ticked {g['name']}: {g['n']} student{'' if g['n'] == 1 else 's'}."
    if form.get("op") == "save_group":
        with db.write(actor) as w:
            _, msg = save_group(w, actor, form.get("group_name"), ticked)
        return ticked, msg
    return None


# ---------- People → Groups ----------

def _tabs_ctx(conn, request, extra: dict) -> dict:
    from app.modules.core.start import picker
    return {**picker(conn, request.state.actor), "saved": saved_groups(conn, request.state.actor), **extra}


@router.get("/groups")
def groups_page(request: Request, s=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        ctx = _tabs_ctx(conn, request, {"title": "Groups", "ticked": set(), "group_name": ""})
    return render(request, "people/groups.html", ctx)


@router.post("/groups")
def groups_create(request: Request, s=Depends(require_staff), form=Depends(form_data)):
    actor, db = request.state.actor, request.app.state.db
    ticked = {int(x) for x in form.getlist("student_id") if str(x).isdigit()}
    done = picker_op(db, actor, form, ticked)
    if done is None:
        with db.write(actor) as w:
            gid, msg = save_group(w, actor, form.get("group_name"), ticked)
        return redirect(f"/people/groups/{gid}", msg)
    with db.read() as conn:
        ctx = _tabs_ctx(conn, request, {"title": "Groups", "ticked": done[0], "group_name": form.get("group_name") or "",
                                        "flash": done[1]})
    return render(request, "people/groups.html", ctx)


@router.get("/groups/{gid}")
def group_page(request: Request, gid: int, s=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        g = get_group(conn, request.state.actor, gid)
        ctx = _tabs_ctx(conn, request, {"title": g["name"], "g": g, "ticked": set(g["members"])})
    return render(request, "people/group.html", ctx)


@router.post("/groups/{gid}")
def group_save(request: Request, gid: int, s=Depends(require_staff), form=Depends(form_data)):
    actor, db = request.state.actor, request.app.state.db
    ticked = {int(x) for x in form.getlist("student_id") if str(x).isdigit()}
    if form.get("op") == "delete":
        with db.write(actor) as w:
            g = one(w.conn, "SELECT * FROM student_group WHERE id = ? AND deleted_at IS NULL", (gid,))
            if not g:
                raise UserError("That group doesn't exist.", 404)
            if not can_edit(actor, g):
                raise UserError("Only the person who made this group, or the coordinator, can delete it.", 403)
            w.soft_delete("student_group", gid)
        return redirect("/people/groups", f"Deleted the group “{g['name']}”. The students are still on the list.")
    done = picker_op(db, actor, form, ticked)
    if done is None:
        with db.write(actor) as w:
            _, msg = save_group(w, actor, form.get("group_name"), ticked, gid)
        return redirect(f"/people/groups/{gid}", msg)
    with db.read() as conn:
        g = get_group(conn, actor, gid)
        ctx = _tabs_ctx(conn, request, {"title": g["name"], "g": g, "ticked": done[0], "flash": done[1]})
    return render(request, "people/group.html", ctx)
