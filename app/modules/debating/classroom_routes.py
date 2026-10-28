"""Routes for the classroom runner (D-075): set up a class debate or speaking round, run it, project it, score it."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from app.db import one, rows
from app.errors import UserError
from app.modules.debating import classroom as R
from app.web.auth import require_staff, staff_class_ids
from app.web.http import form_data, form_int, redirect
from app.web.templating import render

router = APIRouter()

KINDS = {"debate": "Class debate", "speeches": "Speaking round"}


def _classes(conn, actor) -> list[dict]:
    ids = staff_class_ids(conn, actor)
    return [c for c in rows(conn, "SELECT * FROM class WHERE deleted_at IS NULL AND archived_at IS NULL ORDER BY name")
            if ids is None or c["id"] in ids]


def _setup_ctx(conn, request, kind: str, class_id: int | None, run: dict | None = None) -> dict:
    classes = _classes(conn, request.state.actor)
    if class_id and not any(c["id"] == class_id for c in classes):
        raise UserError("You aren't assigned to that class.", 403)
    motions = rows(conn, "SELECT id, motion, level, topic FROM motion_bank WHERE deleted_at IS NULL ORDER BY level, motion")
    names = {}
    if run:
        for s in R.speakers(conn, run["id"]):
            names[f"{s['side']}_{s['position']}" if s["side"] else s["position"]] = s
    return {"kind": kind, "kind_label": KINDS[kind], "classes": classes, "class_id": class_id,
            "roster": R.roster(conn, class_id), "motions": motions, "run": run, "names": names,
            "speech_lines": "\n".join(f"{s['name']}{' - ' + s['topic'] if s['topic'] and run and run['topic_mode'] == 'prepared' else ''}"
                                      for s in sorted(names.values(), key=lambda x: x["position"])) if run and kind == "speeches" else ""}


@router.get("/debating/runs/new")
def run_new(request: Request, kind: str = "debate", class_id: int | None = None, sess=Depends(require_staff)):
    if kind not in KINDS:
        raise UserError("Choose a class debate or a speaking round.", 404)
    with request.app.state.db.read() as conn:
        ctx = _setup_ctx(conn, request, kind, class_id)
    title = "New class debate" if kind == "debate" else "New speaking round"
    return render(request, "debating/run_setup.html", {"title": title, **ctx})


@router.post("/debating/runs")
def run_create(request: Request, sess=Depends(require_staff), form=Depends(form_data)):
    kind = form.get("kind") or "debate"
    with request.app.state.db.write(request.state.actor) as w:
        rid = R.create_run(w, kind, form_int(form.get("class_id")), form)
    return redirect(f"/debating/runs/{rid}", "Ready. Press Start (or Space) when the first speaker stands up.")


@router.get("/debating/runs/{run_id}/edit")
def run_edit(request: Request, run_id: int, sess=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        run = R.get_run(conn, request.state.actor, run_id)
        ctx = _setup_ctx(conn, request, run["kind"], run["class_id"], run)
    return render(request, "debating/run_setup.html", {"title": f"Edit: {run['title']}", **ctx})


@router.post("/debating/runs/{run_id}/edit")
def run_edit_save(request: Request, run_id: int, sess=Depends(require_staff), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        run = R.get_run(w.conn, request.state.actor, run_id)
        R.update_run(w, run, form)
    return redirect(f"/debating/runs/{run_id}", "Saved.")


def _run_ctx(conn, request, run_id: int) -> dict:
    run = R.get_run(conn, request.state.actor, run_id)
    cls = one(conn, "SELECT name FROM class WHERE id = ?", (run["class_id"],)) if run["class_id"] else None
    return {**R.view(conn, run), "class_name": cls["name"] if cls else ""}


@router.get("/debating/runs/{run_id}")
def run_page(request: Request, run_id: int, sess=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        ctx = _run_ctx(conn, request, run_id)
    return render(request, "debating/run.html", {"title": ctx["run"]["title"], **ctx})


@router.get("/debating/runs/{run_id}/f")
def run_fragment(request: Request, run_id: int, sess=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        ctx = _run_ctx(conn, request, run_id)
    return render(request, "debating/_run_main.html", ctx)


@router.post("/debating/runs/{run_id}/act")
def run_act(request: Request, run_id: int, sess=Depends(require_staff), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        run = R.get_run(w.conn, request.state.actor, run_id)
        R.act(w, run, form.get("action") or "", form_int(form.get("arg")))
    if request.headers.get("x-run-control"):
        return Response(status_code=204)
    return redirect(f"/debating/runs/{run_id}")


@router.get("/debating/runs/{run_id}/results")
def run_results(request: Request, run_id: int, sess=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        ctx = _run_ctx(conn, request, run_id)
    return render(request, "debating/run_results.html", {"title": f"Results: {ctx['run']['title']}", **ctx})


@router.post("/debating/runs/{run_id}/results")
def run_results_save(request: Request, run_id: int, sess=Depends(require_staff), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        run = R.get_run(w.conn, request.state.actor, run_id)
        R.save_scores(w, run, form)
    return redirect(f"/debating/runs/{run_id}/results", "Scores saved. Students whose names match the class list see theirs on their page.")


@router.post("/debating/runs/{run_id}/delete")
def run_delete(request: Request, run_id: int, sess=Depends(require_staff)):
    with request.app.state.db.write(request.state.actor) as w:
        run = R.get_run(w.conn, request.state.actor, run_id)
        w.soft_delete("class_run", run["id"], R.ch(run_id))
    return redirect("/debating", "Deleted. It can be restored from Admin for 30 days.")


# ---------- the projector ----------

def _present_ctx(conn, token: str) -> dict:
    run = one(conn, "SELECT * FROM class_run WHERE projector_token = ? AND deleted_at IS NULL", (token,))
    if not run:
        raise UserError("That projector link isn't valid. Open it again from the teacher's page.", 404)
    return {**R.view(conn, run), "token": token}


@router.get("/debating/present/{token}")
def present(request: Request, token: str):
    with request.app.state.db.read() as conn:
        ctx = _present_ctx(conn, token)
    return render(request, "debating/run_present.html", {"title": ctx["run"]["title"], **ctx})


@router.get("/debating/present/{token}/f")
def present_fragment(request: Request, token: str):
    with request.app.state.db.read() as conn:
        ctx = _present_ctx(conn, token)
    return render(request, "debating/_run_present.html", ctx)
