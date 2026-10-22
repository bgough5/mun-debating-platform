"""First-run wizard for the coordinator (Phase 6 item 4): a class, its roster, a conference and committee, join cards.

Each step is ordinary data entry through the same functions as the full pages, so nothing here is special-cased;
the wizard only shows what is done and what comes next. The roster import keeps first names and an initial only;
in the demo dataset a fake roster can be generated instead.
"""
from __future__ import annotations

import random

from fastapi import APIRouter, Depends, File, Request, UploadFile

from app.db import one, rows, scalar
from app.errors import UserError
from app.web.auth import require_coordinator
from app.web.http import form_int, redirect, form_data
from app.web.templating import render

router = APIRouter(prefix="/welcome")


def _state(conn, class_id: int | None) -> dict:
    classes = rows(conn, "SELECT * FROM class WHERE deleted_at IS NULL AND archived_at IS NULL ORDER BY id DESC")
    c = next((x for x in classes if x["id"] == class_id), classes[0] if classes else None)
    students = scalar(conn, "SELECT COUNT(*) FROM student WHERE class_id = ? AND deleted_at IS NULL", (c["id"],)) if c else 0
    committee = one(conn, "SELECT cm.*, cf.name AS conference FROM committee cm JOIN conference cf ON cf.id = cm.conference_id "
                          "WHERE cm.class_id = ? AND cm.deleted_at IS NULL ORDER BY cm.id DESC LIMIT 1", (c["id"],)) if c else None
    return {"classes": classes, "c": c, "students": students, "committee": committee,
            "steps": [("class", "Create a class", bool(c)), ("roster", "Add the students", students > 0),
                      ("committee", "Set up a conference and committee", bool(committee)), ("cards", "Print join cards", False)]}


@router.get("")
def wizard(request: Request, class_id: int | None = None, sess=Depends(require_coordinator)):
    with request.app.state.db.read() as conn:
        st = _state(conn, class_id)
        types = rows(conn, "SELECT id, name FROM committee_type WHERE deleted_at IS NULL ORDER BY name")
        topics = rows(conn, "SELECT id, name FROM topic WHERE deleted_at IS NULL ORDER BY name")
    current = next((code for code, _, done in st["steps"] if not done), "cards")
    return render(request, "core/wizard.html", {"title": "Getting started", "current": current, "types": types, "topics": topics, **st})


@router.post("/class")
def wizard_class(request: Request, sess=Depends(require_coordinator), form=Depends(form_data)):
    from app.modules.people.routes import create_class
    with request.app.state.db.write(request.state.actor) as w:
        cid, code = create_class(w, form.get("name"), form_int(form.get("year")))
    return redirect(f"/welcome?class_id={cid}", f"Class created. Its class code is {code}.")


@router.post("/roster")
async def wizard_roster(request: Request, file: UploadFile | None = File(None), sess=Depends(require_coordinator)):
    import asyncio
    from app.modules.people.routes import add_students, roster_lines_from_csv
    form = await request.form()
    class_id = form_int(form.get("class_id"))
    data = await file.read() if file is not None else b""
    settings = request.app.state.settings

    def run():
        with request.app.state.db.write(request.state.actor) as w:
            if not one(w.conn, "SELECT 1 FROM class WHERE id = ? AND deleted_at IS NULL", (class_id,)):
                raise UserError("Choose a class first.")
            if form.get("action") == "fake":
                if not settings.is_demo:
                    raise UserError("Fake rosters are only for the demo dataset, so they never mix with real students.")
                from app.fakedata import fake_people
                n = max(1, min(25, form_int(form.get("count"), 12) or 12))
                lines = [f"{f} {i}".strip() for f, i in fake_people(random.Random(class_id), n)]
            elif data:
                lines = roster_lines_from_csv(data)
            else:
                lines = (form.get("names") or "").splitlines()
            return add_students(w, class_id, lines)
    msg = await asyncio.to_thread(run)
    return redirect(f"/welcome?class_id={class_id}", msg)


@router.post("/committee")
def wizard_committee(request: Request, sess=Depends(require_coordinator), form=Depends(form_data)):
    from app.modules.mun import service as M
    class_id = form_int(form.get("class_id"))
    with request.app.state.db.write(request.state.actor) as w:
        if not one(w.conn, "SELECT 1 FROM class WHERE id = ? AND deleted_at IS NULL", (class_id,)):
            raise UserError("Choose a class first.")
        conf = M.create_conference(w, form.get("conference") or "", form.get("starts_on") or "")
        cid = M.create_committee(w, conf, form.get("committee") or "", form_int(form.get("committee_type_id")), None,
                                 form_int(form.get("topic_id")), class_id)
        isos = [x for x in (form.get("delegations") or "").replace(",", " ").split() if x]
        if isos:
            M.add_delegations(w, cid, isos)
    return redirect(f"/welcome?class_id={class_id}", "Conference and committee created. Allocate students to countries on the committee page.")
