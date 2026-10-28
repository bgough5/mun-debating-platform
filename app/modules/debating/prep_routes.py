"""Routes for the prep studio (D-076, D-077): students' cases, rebuttals and speech drafts; the teacher's view to score them."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.db import one, rows
from app.errors import UserError
from app.modules.debating import classroom as R
from app.modules.debating import prep as P
from app.util import display_name
from app.web.auth import require_staff, require_student, staff_class_ids
from app.web.http import form_data, form_int, redirect
from app.web.templating import render

router = APIRouter()


# ---------- students ----------

@router.get("/me/prep")
def prep_home(request: Request, sess=Depends(require_student)):
    sid = sess.actor.id
    with request.app.state.db.read() as conn:
        motions = rows(conn, "SELECT id, motion, level FROM motion_bank WHERE deleted_at IS NULL ORDER BY level, motion")
        ctx = {"cases": P.cases_for(conn, sid), "speeches": P.speeches_for(conn, sid), "templates": P.templates(conn, "prepared"),
               "results": R.student_results(conn, sid), "levels": [(lv, [m for m in motions if m["level"] == lv]) for lv in ("junior", "middle", "senior")],
               "practice": one(conn, "SELECT COUNT(*) AS n FROM practice_speech WHERE student_id = ? AND deleted_at IS NULL", (sid,))["n"]}
    return render(request, "debating/prep_home.html", {"title": "Prep and practise", **ctx})


@router.post("/me/prep/cases")
def case_create(request: Request, sess=Depends(require_student), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        cid = P.create_case(w, sess.actor.id, form_int(form.get("motion_id")), form.get("motion") or "", form.get("side") or "")
    return redirect(f"/me/prep/cases/{cid}", "Case started. Begin with your team line, then your arguments.")


@router.get("/me/prep/cases/{case_id}")
def case_page(request: Request, case_id: int, sess=Depends(require_student)):
    with request.app.state.db.read() as conn:
        case = P.get_case(conn, request.state.actor, case_id)
        ctx = P.case_view(conn, case)
    return render(request, "debating/prep_case.html", {"title": f"{ctx['side_label']} case: {case['motion']}", **ctx})


@router.post("/me/prep/cases/{case_id}")
def case_header(request: Request, case_id: int, sess=Depends(require_student), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        case = P.get_case(w.conn, request.state.actor, case_id)
        P.save_header(w, case, form)
    return redirect(f"/me/prep/cases/{case_id}#setup", "Saved.")


@router.post("/me/prep/cases/{case_id}/points")
def case_point(request: Request, case_id: int, sess=Depends(require_student), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        case = P.get_case(w.conn, request.state.actor, case_id)
        pid = P.save_point(w, case, form)
    return redirect(f"/me/prep/cases/{case_id}#p{pid}", "Saved.")


@router.post("/me/prep/cases/{case_id}/points/{point_id}/delete")
def case_point_delete(request: Request, case_id: int, point_id: int, sess=Depends(require_student)):
    with request.app.state.db.write(request.state.actor) as w:
        case = P.get_case(w.conn, request.state.actor, case_id)
        P.delete_point(w, case, point_id)
    return redirect(f"/me/prep/cases/{case_id}", "Removed.")


@router.post("/me/prep/cases/{case_id}/delete")
def case_delete(request: Request, case_id: int, sess=Depends(require_student)):
    with request.app.state.db.write(request.state.actor) as w:
        case = P.get_case(w.conn, request.state.actor, case_id)
        w.soft_delete("prep_case", case["id"])
    return redirect("/me/prep", "Case deleted.")


@router.post("/me/prep/speeches")
def speech_create(request: Request, sess=Depends(require_student), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        sp = P.create_speech(w, sess.actor.id, form.get("template_code") or "", form.get("title") or "")
    return redirect(f"/me/prep/speeches/{sp}", "Speech started. Each box has a prompt: write in your own words.")


@router.get("/me/prep/speeches/{speech_id}")
def speech_page(request: Request, speech_id: int, sess=Depends(require_student)):
    with request.app.state.db.read() as conn:
        sp = P.get_speech(conn, request.state.actor, speech_id)
        ctx = P.speech_view(conn, sp)
    return render(request, "debating/prep_speech.html", {"title": f"Speech: {sp['title']}", **ctx})


@router.post("/me/prep/speeches/{speech_id}")
def speech_save(request: Request, speech_id: int, sess=Depends(require_student), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        sp = P.get_speech(w.conn, request.state.actor, speech_id)
        P.save_speech(w, sp, form)
    return redirect(f"/me/prep/speeches/{speech_id}", "Saved.")


@router.get("/me/prep/speeches/{speech_id}/rehearse")
def speech_rehearse(request: Request, speech_id: int, sess=Depends(require_student)):
    with request.app.state.db.read() as conn:
        sp = P.get_speech(conn, request.state.actor, speech_id)
        ctx = P.speech_view(conn, sp)
    return render(request, "debating/prep_rehearse.html", {"title": f"Rehearse: {sp['title']}", **ctx})


@router.get("/me/prep/speeches/{speech_id}/cards")
def speech_cards(request: Request, speech_id: int, sess=Depends(require_student)):
    with request.app.state.db.read() as conn:
        sp = P.get_speech(conn, request.state.actor, speech_id)
        ctx = P.speech_view(conn, sp)
    return render(request, "debating/prep_cards.html", {"title": f"Cue cards: {sp['title']}", **ctx})


@router.post("/me/prep/speeches/{speech_id}/delete")
def speech_delete(request: Request, speech_id: int, sess=Depends(require_student)):
    with request.app.state.db.write(request.state.actor) as w:
        sp = P.get_speech(w.conn, request.state.actor, speech_id)
        w.soft_delete("prep_speech", sp["id"])
    return redirect("/me/prep", "Speech deleted.")


# ---------- staff ----------

def _check_class(conn, actor, class_id: int) -> dict:
    ids = staff_class_ids(conn, actor)
    if ids is not None and class_id not in ids:
        raise UserError("You aren't assigned to that class.", 403)
    c = one(conn, "SELECT * FROM class WHERE id = ? AND deleted_at IS NULL", (class_id,))
    if not c:
        raise UserError("That class doesn't exist.", 404)
    return c


@router.get("/debating/prep")
def class_prep(request: Request, class_id: int, sess=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        cls = _check_class(conn, request.state.actor, class_id)
        students = P.class_overview(conn, class_id)
    return render(request, "debating/prep_class.html", {"title": f"Student preparation: {cls['name']}", "cls": cls, "students": students})


def _owner(conn, student_id: int) -> dict:
    st = one(conn, "SELECT s.*, c.name AS class_name FROM student s JOIN class c ON c.id = s.class_id WHERE s.id = ?", (student_id,))
    st["name"] = display_name(st["first_name"], st["last_initial"])
    return st


@router.get("/debating/prep/cases/{case_id}")
def staff_case(request: Request, case_id: int, sess=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        case = P.get_case(conn, request.state.actor, case_id)
        ctx = P.case_view(conn, case)
        st = _owner(conn, case["student_id"])
    return render(request, "debating/prep_case_staff.html", {"title": f"{st['name']}: {ctx['side_label']} case", "student": st, **ctx})


@router.post("/debating/prep/cases/{case_id}")
def staff_case_save(request: Request, case_id: int, sess=Depends(require_staff), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        case = P.get_case(w.conn, request.state.actor, case_id)
        P.staff_score(w, case, form)
    return redirect(f"/debating/prep/cases/{case_id}", "Scores and comment saved. The student sees them on their case.")


@router.get("/debating/prep/speeches/{speech_id}")
def staff_speech(request: Request, speech_id: int, sess=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        sp = P.get_speech(conn, request.state.actor, speech_id)
        ctx = P.speech_view(conn, sp)
        st = _owner(conn, sp["student_id"])
    return render(request, "debating/prep_speech_staff.html", {"title": f"{st['name']}: {sp['title']}", "student": st, **ctx})


@router.post("/debating/prep/speeches/{speech_id}")
def staff_speech_save(request: Request, speech_id: int, sess=Depends(require_staff), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        sp = P.get_speech(w.conn, request.state.actor, speech_id)
        w.update("prep_speech", sp["id"], {"staff_comment": (form.get("staff_comment") or "").strip()[:2000]})
    return redirect(f"/debating/prep/speeches/{speech_id}", "Comment saved. The student sees it on their speech.")
