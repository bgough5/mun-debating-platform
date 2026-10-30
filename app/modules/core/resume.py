"""Activities in progress, and "who's here today?" when you come back to one (D-084 stage 3).

Everything is saved as it happens, so resuming is just opening the activity again. What changes between sessions is
who turned up. The Dashboard lists unfinished debates, speaking rounds and Model UN sessions. Resume asks who's here,
starting from last time's students, and then:
- **Speaking round:** speakers who have already spoken (or are speaking) keep their place. Students who are away
  leave the rest of the order, and new students go on the end.
- **Debate:** an absent student's unspoken slot is cleared, and new students fill the free slots.
- **Model UN:** new students get a delegation. Nothing is needed for absent ones: a country whose students haven't
  signed in is voted by the engine (D-079).
"""
from __future__ import annotations

import json
import random

from fastapi import APIRouter, Depends, Request

from app.db import one, rows, scalar
from app.errors import UserError
from app.util import display_name
from app.web.auth import committee_access, require_staff
from app.web.http import form_data, redirect
from app.web.templating import render

router = APIRouter()

KIND_LABEL = {"debate": "Class debate", "speeches": "Speaking round", "mun": "Model UN"}


def _last_used(conn, channel: str, fallback: str) -> str:
    return scalar(conn, "SELECT at FROM event_log WHERE channel = ? ORDER BY seq DESC LIMIT 1", (channel,)) or fallback


def in_progress(conn, actor, limit: int = 12) -> list[dict]:
    """Unfinished activities this person can run, most recently used first."""
    from app.modules.chair import service as C
    from app.modules.debating import classroom as R
    out = []
    for r in R.runs_for(conn, actor, limit=60):
        if r["status"] == "finished":
            continue
        n_steps = len(R.steps(r, R.speakers(conn, r["id"])))
        where = "not started" if r["status"] == "ready" else f"step {min(r['step'] + 1, n_steps)} of {n_steps}"
        out.append({"kind": r["kind"], "label": KIND_LABEL[r["kind"]], "title": r["title"], "where": where,
                    "people": r["n_speakers"], "used": _last_used(conn, R.ch(r["id"]), r["created_at"]),
                    "open": f"/debating/runs/{r['id']}", "resume": f"/start/resume/run/{r['id']}"})
    for s in rows(conn, "SELECT s.*, (SELECT COUNT(*) FROM delegation_member dm JOIN delegation d ON d.id = dm.delegation_id "
                        "WHERE d.committee_id = s.committee_id AND dm.deleted_at IS NULL AND d.deleted_at IS NULL) AS people "
                        "FROM live_session s JOIN committee cm ON cm.id = s.committee_id AND cm.deleted_at IS NULL "
                        "WHERE s.state != 'closed' ORDER BY s.id DESC LIMIT 60"):
        if committee_access(conn, actor, s["committee_id"]) != "manage":
            continue
        out.append({"kind": "mun", "label": KIND_LABEL["mun"], "title": s["title"],
                    "where": "suspended" if s["state"] == "suspended" else "open", "people": s["people"],
                    "used": _last_used(conn, C.ch(s["id"]), s["created_at"]),
                    "open": f"/chair/{s['id']}", "resume": f"/start/resume/session/{s['id']}"})
    out.sort(key=lambda x: x["used"], reverse=True)
    return out[:limit]


# ---------- who's here today ----------

def _target(conn, actor, what: str, key: int) -> dict:
    """The activity being resumed, with the students it has now, after checking this person may run it."""
    if what == "run":
        from app.modules.debating import classroom as R
        run = R.get_run(conn, actor, key)                       # 404 / 403 as on the run page
        if run["status"] == "finished":
            raise UserError("That one has finished. Open it and choose Reopen to carry on, or start a new activity.")
        spk = R.speakers(conn, key)
        return {"what": what, "id": key, "title": run["title"], "label": KIND_LABEL[run["kind"]], "run": run, "speakers": spk,
                "students": {s["student_id"] for s in spk if s["student_id"]},
                "typed": [s["name"] for s in spk if not s["student_id"] and s["name"] and not s["name"].startswith("Speaker ")],
                "open": f"/debating/runs/{key}"}
    if what == "session":
        from app.modules.chair import service as C
        s = C.get_session(conn, key)
        if committee_access(conn, actor, s["committee_id"]) != "manage":
            raise UserError("Only staff running this class can chair its session.", 403)
        if s["state"] == "closed":
            raise UserError("That session has closed. Open the committee to start a new session.")
        members = {r["student_id"] for r in rows(conn, "SELECT dm.student_id FROM delegation_member dm JOIN delegation d ON d.id = dm.delegation_id "
                                                       "WHERE d.committee_id = ? AND dm.deleted_at IS NULL AND d.deleted_at IS NULL",
                                                 (s["committee_id"],))}
        return {"what": what, "id": key, "title": s["title"], "label": KIND_LABEL["mun"], "session": s, "students": members,
                "typed": [], "open": f"/chair/{key}"}
    raise UserError("Unknown activity.", 404)


def _page(conn, request, t: dict, ticked: set[int], flash: str | None = None):
    from app.modules.core.start import picker
    from app.modules.people.groups import saved_groups
    ctx = {"title": "Who's here today?", "t": t, "ticked": ticked, **picker(conn, request.state.actor),
           "saved": saved_groups(conn, request.state.actor), "offer_save": True}
    if flash:
        ctx["flash"] = flash
    return render(request, "core/resume.html", ctx)


@router.get("/start/resume/{what}/{key}")
def resume_page(request: Request, what: str, key: int, s=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        t = _target(conn, request.state.actor, what, key)
        return _page(conn, request, t, set(t["students"]))


@router.post("/start/resume/{what}/{key}")
def resume_submit(request: Request, what: str, key: int, s=Depends(require_staff), form=Depends(form_data)):
    actor = request.state.actor
    ticked = {int(x) for x in form.getlist("student_id") if str(x).isdigit()}
    from app.modules.people.groups import picker_op
    done = picker_op(request.app.state.db, actor, form, ticked)
    if done is not None:
        with request.app.state.db.read() as conn:
            return _page(conn, request, _target(conn, actor, what, key), done[0], done[1])
    with request.app.state.db.write(actor) as w:
        from app.modules.people.routes import visible_students
        t = _target(w.conn, actor, what, key)
        allowed = {st["id"]: st for st in visible_students(w.conn, actor)}
        here = [allowed[i] for i in sorted(ticked) if i in allowed]
        if what == "session":
            msg = _resume_session(w, t, here)
        elif t["run"]["kind"] == "speeches":
            msg = _resume_speeches(w, t, here)
        else:
            msg = _resume_debate(w, t, here)
    return redirect(t["open"], msg)


def _resume_session(w, t, here) -> str:
    from app.modules.mun import service as M
    new = [st["id"] for st in here if st["id"] not in t["students"]]
    added = M.allocate_round_robin(w, t["session"]["committee_id"], new) if new else 0
    msg = f"Welcome back. {added} new student(s) given a country." if added else "Welcome back."
    return msg + " Students who are away need nothing: until they sign in, their country is voted by the engine and labelled computed."


def _started(run: dict, spk: list[dict]) -> set[int]:
    """Speaker ids whose turn has come: spoken, being spoken, timed or scored. These keep their place."""
    from app.modules.debating import classroom as R
    times = json.loads(run["step_seconds"] or "{}")
    live = run["timer_state"] != "idle" or run["timer_elapsed"] > 0
    out = set()
    for st in R.steps(run, spk):
        sp = st["speaker"]
        if sp and (st["index"] < run["step"] or st["key"] in times or (st["index"] == run["step"] and live and run["status"] != "ready")):
            out.add(sp["id"])
    out |= {sp["id"] for sp in spk if sp["scores"] not in ("", "{}") or sp["comment"]}
    return out


def _resume_speeches(w, t, here) -> str:
    from app.modules.debating import classroom as R
    run, spk = t["run"], sorted(t["speakers"], key=lambda s: s["position"])
    done = _started(run, spk)
    here_ids = {st["id"] for st in here}
    keep_done = [s for s in spk if s["id"] in done]
    rest = [s for s in spk if s["id"] not in done]
    staying = [s for s in rest if not s["student_id"] or s["student_id"] in here_ids]   # typed names can't be ticked: kept
    away = [s for s in rest if s["student_id"] and s["student_id"] not in here_ids]
    new = [st for st in here if st["id"] not in t["students"]]
    random.shuffle(new)
    if len(keep_done) + len(staying) + len(new) > R.MAX_SPEAKERS:
        raise UserError(f"A speaking round holds up to {R.MAX_SPEAKERS} speakers. Start another activity for the extra students.")
    c = R.ch(run["id"])
    for s in away:
        w.soft_delete("class_run_speaker", s["id"], c)
    pos = max([s["position"] for s in keep_done], default=0)
    for s in staying:
        pos += 1
        if s["position"] != pos:
            w.update("class_run_speaker", s["id"], {"position": pos}, c, action="reorder")
    for st in new:
        pos += 1
        w.insert("class_run_speaker", {"run_id": run["id"], "side": "", "position": pos, "name": display_name(st["first_name"], st["last_initial"]),
                                       "student_id": st["id"], "topic": ""}, c)
    _clamp_step(w, run)
    parts = [f"Welcome back: {len(keep_done)} already spoken"]
    if away:
        parts.append(f"{len(away)} away taken out of the order")
    if new:
        parts.append(f"{len(new)} new added at the end")
    return ", ".join(parts) + "."


def _resume_debate(w, t, here) -> str:
    from app.modules.debating import classroom as R
    run, spk = t["run"], t["speakers"]
    done = _started(run, spk)
    here_ids = {st["id"] for st in here}
    c = R.ch(run["id"])
    cleared = 0
    by_slot = {(s["side"], s["position"]): s for s in spk}
    for s in spk:
        if s["id"] not in done and s["student_id"] and s["student_id"] not in here_ids:
            w.update("class_run_speaker", s["id"], {"name": "", "student_id": None, "topic": ""}, c, action="away")
            s["name"], s["student_id"] = "", None
            cleared += 1
    new = [st for st in here if st["id"] not in t["students"]]
    random.shuffle(new)
    placed = 0
    for st in R.steps(run, spk):                      # fill free slots in speaking order
        if not new or st["kind"] != "speech":
            continue
        slot = by_slot.get((st["side"], int(st["key"][3:])))
        if slot and slot["id"] not in done and not slot["name"]:
            who = new.pop(0)
            w.update("class_run_speaker", slot["id"], {"name": display_name(who["first_name"], who["last_initial"]),
                                                       "student_id": who["id"]}, c, action="here")
            slot["name"] = "x"
            placed += 1
    msg = "Welcome back."
    if cleared:
        msg += f" {cleared} speaker slot(s) of students who are away are now free."
    if placed:
        msg += f" {placed} new student(s) given a slot."
    if new:
        msg += (f" {len(new)} student(s) didn't fit: every slot is taken. Edit the debate to add speakers, "
                "or start another activity for them.")
    empty = sum(1 for s in R.speakers(w.conn, run["id"]) if not s["name"])
    if empty:
        msg += f" {empty} slot(s) still have no speaker: a student can speak twice, or edit the debate."
    return msg


def _clamp_step(w, run) -> None:
    """If students left the end of the order, keep the current step inside it."""
    from app.modules.debating import classroom as R
    fresh = one(w.conn, "SELECT * FROM class_run WHERE id = ?", (run["id"],))
    n = len(R.steps(fresh, R.speakers(w.conn, run["id"])))
    if n and fresh["step"] >= n:
        w.update("class_run", run["id"], {"step": n - 1, "timer_state": "idle", "timer_elapsed": 0, "timer_extra": 0,
                                          "timer_started_at": None}, R.ch(run["id"]), action="restart")
