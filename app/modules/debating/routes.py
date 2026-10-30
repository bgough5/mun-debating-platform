"""Debating: events, setup, draws, ballots, results, house points, documents, projector, practice."""
from __future__ import annotations

import json
import random

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from app.db import one, rows, scalar
from app.engine.draw import ROLES, plan_practice
from app.errors import UserError
from app.exports import csv_bytes, text_docx
from app.modules.debating import service as S
from app.modules.debating.access import adjudicates, debate_access
from app.util import display_name, now_iso
from app.web.auth import require_any, require_coordinator, require_staff, require_student, staff_class_ids
from app.web.http import form_data, form_float, form_int, redirect
from app.web.templating import render

router = APIRouter()


def _event(conn, request, event_id: int, need: str = "manage") -> dict:
    a = debate_access(conn, request.state.actor, event_id)
    if a == "none" or (need == "manage" and a != "manage"):
        raise UserError("You don't have access to that event." if a == "none" else "Only staff can do that.", 403)
    e = S.get_event(conn, event_id)
    e["access"] = a
    return e


def _round(conn, request, round_id: int, need: str = "manage") -> tuple[dict, dict]:
    r = one(conn, "SELECT * FROM debate_round WHERE id = ? AND deleted_at IS NULL", (round_id,))
    if not r:
        raise UserError("That round doesn't exist.", 404)
    return r, _event(conn, request, r["event_id"], need)


def _class_students(conn, class_id):
    return rows(conn, "SELECT st.*, h.name AS house FROM student st LEFT JOIN house h ON h.id = st.house_id WHERE st.class_id = ? "
                      "AND st.active = 1 AND st.deleted_at IS NULL ORDER BY st.first_name, st.last_initial", (class_id,))


# ---------- events ----------

@router.get("/debating")
def debating_home(request: Request, sess=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        ids = staff_class_ids(conn, sess.actor)
        events = rows(conn, "SELECT e.*, f.name AS format_name, c.name AS class_name, (SELECT COUNT(*) FROM team t WHERE t.event_id = e.id "
                            "AND t.deleted_at IS NULL) AS teams FROM debate_event e JOIN debate_format f ON f.id = e.format_id "
                            "LEFT JOIN class c ON c.id = e.class_id WHERE e.deleted_at IS NULL ORDER BY e.id DESC")
        if ids is not None:
            events = [e for e in events if e["class_id"] is None or e["class_id"] in ids]
        formats = rows(conn, "SELECT * FROM debate_format WHERE deleted_at IS NULL ORDER BY id")
        rubrics = rows(conn, "SELECT * FROM rubric WHERE kind = 'debate_speaker' AND deleted_at IS NULL ORDER BY name")
        classes = rows(conn, "SELECT * FROM class WHERE deleted_at IS NULL AND archived_at IS NULL ORDER BY name")
        if ids is not None:
            classes = [c for c in classes if c["id"] in ids]
        totals = S.house_totals(conn)
        from app.modules.debating.classroom import runs_for
        runs = runs_for(conn, sess.actor)
    return render(request, "debating/home.html", {"title": "Debating and public speaking", "events": events, "formats": formats,
                                                  "rubrics": rubrics, "classes": classes, "totals": totals, "runs": runs,
                                                  **_prep_choices(request),
                                                  "show_tournaments": bool(request.app.state.settings.get("show_tournaments"))})


def _prep_choices(request: Request) -> dict:
    """Saved groups and year levels for "Student preparation" (D-088)."""
    try:
        from app.modules.people.groups import saved_groups
        from app.modules.people.routes import visible_students
    except ImportError:
        return {"saved_groups": [], "year_counts": []}
    with request.app.state.db.read() as conn:
        groups = saved_groups(conn, request.state.actor)
        counts: dict = {}
        for st in visible_students(conn, request.state.actor):
            if st["year_level"]:
                counts[st["year_level"]] = counts.get(st["year_level"], 0) + 1
    return {"saved_groups": groups, "year_counts": sorted(counts.items())}


@router.post("/debating/tournaments")
def tournaments_toggle(request: Request, sess=Depends(require_coordinator), form=Depends(form_data)):
    """Show or hide the tournament and carnival tools (D-084). Nothing is deleted either way."""
    show = form.get("show") == "1"
    request.app.state.settings.set("show_tournaments", show)
    return redirect("/debating", "Tournament tools shown." if show else "Tournament tools hidden. Nothing was deleted.")


@router.post("/debating/events")
def event_create(request: Request, sess=Depends(require_staff), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        class_id = form_int(form.get("class_id"))
        if class_id is None and not request.state.actor.is_coordinator and form.get("kind") in ("class", "practice"):
            raise UserError("Choose your class for a class event.")
        if class_id is not None:
            ids = staff_class_ids(w.conn, request.state.actor)
            if ids is not None and class_id not in ids:
                raise UserError("You aren't assigned to that class.", 403)
        eid = S.create_event(w, form.get("name"), form.get("kind") or "carnival", form_int(form.get("format_id")),
                             form_int(form.get("rubric_id")), class_id, form.get("starts_on") or "", form.get("start_time") or "09:00")
    return redirect(f"/debating/events/{eid}/setup", "Event created. Add teams, rooms and adjudicators next.")


@router.get("/debating/events/{event_id}")
def event_view(request: Request, event_id: int, sess=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        e = _event(conn, request, event_id)
        rounds = rows(conn, "SELECT r.*, (SELECT COUNT(*) FROM pairing p WHERE p.round_id = r.id AND p.deleted_at IS NULL AND p.neg_team_id IS NOT NULL) AS debates, "
                            "(SELECT COUNT(DISTINCT b.pairing_id) FROM ballot b JOIN pairing p ON p.id = b.pairing_id WHERE p.round_id = r.id "
                            "AND b.deleted_at IS NULL AND p.deleted_at IS NULL) AS results FROM debate_round r WHERE r.event_id = ? "
                            "AND r.deleted_at IS NULL ORDER BY r.number", (event_id,))
        counts = {t: scalar(conn, f"SELECT COUNT(*) FROM {t} WHERE event_id = ? AND deleted_at IS NULL", (event_id,))
                  for t in ("team", "room", "adjudicator")}
        lad = S.ladder(conn, event_id)[:8] if rounds else []
        totals = S.house_totals(conn, event_id)
        motions = rows(conn, "SELECT motion FROM motion_bank WHERE deleted_at IS NULL ORDER BY id")
    return render(request, "debating/event.html", {"title": e["name"], "e": e, "rounds": rounds, "counts": counts, "ladder": lad,
                                                   "totals": totals, "motions": motions})


# ---------- setup ----------

@router.get("/debating/events/{event_id}/setup")
def event_setup(request: Request, event_id: int, sess=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        e = _event(conn, request, event_id)
        teams = rows(conn, "SELECT t.*, h.name AS house FROM team t LEFT JOIN house h ON h.id = t.house_id WHERE t.event_id = ? "
                           "AND t.deleted_at IS NULL ORDER BY t.id", (event_id,))
        members = {}
        for m in rows(conn, "SELECT tm.*, st.first_name, st.last_initial FROM team_member tm JOIN student st ON st.id = tm.student_id "
                            "JOIN team t ON t.id = tm.team_id WHERE t.event_id = ? AND tm.deleted_at IS NULL ORDER BY tm.position", (event_id,)):
            members.setdefault(m["team_id"], []).append(m)
        rooms = rows(conn, "SELECT * FROM room WHERE event_id = ? AND deleted_at IS NULL ORDER BY priority DESC, id", (event_id,))
        adjs = rows(conn, "SELECT a.*, h.name AS house FROM adjudicator a LEFT JOIN house h ON h.id = a.house_id WHERE a.event_id = ? "
                          "AND a.deleted_at IS NULL ORDER BY a.rating DESC, a.name", (event_id,))
        houses = rows(conn, "SELECT * FROM house WHERE deleted_at IS NULL ORDER BY name")
        ids = staff_class_ids(conn, request.state.actor)
        classes = [c for c in rows(conn, "SELECT * FROM class WHERE deleted_at IS NULL AND archived_at IS NULL ORDER BY name")
                   if ids is None or c["id"] in ids]
        class_students = _class_students(conn, e["class_id"]) if e["class_id"] else []
        staff = rows(conn, "SELECT id, name FROM staff WHERE active = 1 AND deleted_at IS NULL ORDER BY name")
    in_team = {m["student_id"] for ms in members.values() for m in ms}
    return render(request, "debating/setup.html", {"title": f"Set up: {e['name']}", "e": e, "teams": teams, "members": members,
                                                   "rooms": rooms, "adjs": adjs, "houses": houses, "classes": classes,
                                                   "class_students": class_students, "in_team": in_team, "staff": staff})


@router.post("/debating/events/{event_id}/setup")
def event_setup_save(request: Request, event_id: int, sess=Depends(require_staff), form=Depends(form_data)):
    action = form.get("action")
    with request.app.state.db.write(request.state.actor) as w:
        e = _event(w.conn, request, event_id)
        if action == "team":
            sids = [int(x) for x in form.getlist("student_id") if x]
            S.add_team(w, event_id, form.get("name"), form_int(form.get("house_id")), sids, bool(form.get("needs_accessible")))
            msg = "Team added."
        elif action == "auto_teams":
            cid = form_int(form.get("class_id"))
            ids = staff_class_ids(w.conn, request.state.actor)
            if not cid or (ids is not None and cid not in ids):
                raise UserError("Choose one of your classes.")
            sids = [r["id"] for r in _class_students(w.conn, cid)]
            n = S.auto_teams(w, event_id, sids, by_house=bool(form.get("by_house")))
            msg = f"Made {n} team(s) from the class." + (" Students without a house were grouped together." if form.get("by_house") else "")
        elif action == "remove_team":
            if form.get("confirm") != "yes":
                raise UserError("Tick the box to confirm removing the team.")
            w.soft_delete("team", form_int(form.get("team_id")), S.ch(event_id))
            msg = "Team removed (undo is available)."
        elif action == "rooms":
            names = [x for x in (form.get("names") or "").splitlines() if x.strip()]
            count = form_int(form.get("count"))
            if count and not names:
                start = (scalar(w.conn, "SELECT COUNT(*) FROM room WHERE event_id = ?", (event_id,)) or 0) + 1
                names = [f"Room {i}" for i in range(start, start + min(count, 200))]
            if not names:
                raise UserError("Type room names (one per line) or how many rooms to add.")
            msg = f"Added {S.add_rooms(w, event_id, names, not form.get('not_accessible'))} room(s)."
        elif action == "adjudicator":
            S.add_adjudicator(w, event_id, form.get("name") or "", form_float(form.get("rating"), 5), form_int(form.get("house_id")),
                              form_int(form.get("staff_id")), form_int(form.get("student_id")))
            msg = "Adjudicator added."
        elif action == "remove":
            table = form.get("table")
            if table not in ("room", "adjudicator"):
                raise UserError("Unknown item.")
            w.soft_delete(table, form_int(form.get("id")), S.ch(event_id))
            msg = "Removed (undo is available)."
        elif action == "settings":
            w.update("debate_event", event_id, {"avoid_same_house": int(bool(form.get("avoid_same_house"))),
                                                "bye_counts_as_win": int(bool(form.get("bye_counts_as_win"))),
                                                "start_time": form.get("start_time") or e["start_time"],
                                                "round_minutes": form_int(form.get("round_minutes"), e["round_minutes"]),
                                                "break_minutes": form_int(form.get("break_minutes"), e["break_minutes"])}, S.ch(event_id))
            msg = "Settings saved."
        else:
            raise UserError("Unknown action.")
    return redirect(f"/debating/events/{event_id}/setup", msg)


# ---------- rounds ----------

@router.post("/debating/events/{event_id}/rounds")
def round_create(request: Request, event_id: int, sess=Depends(require_staff), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        _event(w.conn, request, event_id)
        rid = S.create_round(w, event_id, form.get("kind") or None, form.get("motion") or "", form.get("info") or "")
        problems = S.generate_draw(w, rid)
    msg = "Draw generated. Check it, then release it."
    if problems:
        msg += " Notes: " + " ".join(problems[:4])
    return redirect(f"/debating/rounds/{rid}", msg)


@router.get("/debating/rounds/{round_id}")
def round_view(request: Request, round_id: int, sess=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        r, e = _round(conn, request, round_id)
        draw = S.round_draw(conn, round_id)
        teams = rows(conn, "SELECT id, name FROM team WHERE event_id = ? AND deleted_at IS NULL ORDER BY name", (e["id"],))
    return render(request, "debating/round.html", {"title": f"{e['name']}: round {r['number']}", "r": r, "e": e, "draw": draw,
                                                   "teams": teams, "roles": ROLES.get(e["speakers_per_team"], [])})


@router.get("/debating/rounds/{round_id}/f")
def round_fragment(request: Request, round_id: int, sess=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        r, e = _round(conn, request, round_id)
        draw = S.round_draw(conn, round_id)
    return render(request, "debating/_draw.html", {"r": r, "e": e, "draw": draw, "manage": True})


@router.post("/debating/rounds/{round_id}")
def round_action(request: Request, round_id: int, sess=Depends(require_staff), form=Depends(form_data)):
    action = form.get("action")
    with request.app.state.db.write(request.state.actor) as w:
        r, e = _round(w.conn, request, round_id)
        if action == "redraw":
            problems = S.generate_draw(w, round_id)
            msg = "Draw regenerated." + (" Notes: " + " ".join(problems[:4]) if problems else "")
        elif action == "release":
            S.set_round_status(w, round_id, "released", motion_released=bool(form.get("with_motion")))
            msg = "Draw released: students, adjudicators and the projector can see it."
        elif action == "motion":
            S.set_round_status(w, round_id, r["status"] if r["status"] != "draft" else "released", motion_released=True)
            msg = "Motion released."
        elif action == "unrelease":
            S.set_round_status(w, round_id, "draft", motion_released=False)
            msg = "Round back to draft."
        elif action == "close":
            S.set_round_status(w, round_id, "closed")
            msg = "Round closed."
        elif action == "motion_text":
            w.update("debate_round", round_id, {"motion": (form.get("motion") or "")[:400], "info": (form.get("info") or "")[:2000]},
                     S.ch(e["id"]))
            msg = "Motion saved."
        elif action == "swap":
            S.swap_teams(w, form_int(form.get("pairing_a")), form_int(form.get("team_a")), form_int(form.get("pairing_b")),
                         form_int(form.get("team_b")))
            msg = "Teams swapped."
        elif action == "house_points":
            msg = f"{S.award_house_points(w, e['id'], round_id=round_id)} house point entries added for this round."
        else:
            raise UserError("Unknown action.")
    return redirect(f"/debating/rounds/{round_id}", msg)


# ---------- ballots ----------

def _ballot_context(conn, request, pairing_id: int):
    p = one(conn, "SELECT p.*, r.event_id, r.number, r.motion, r.status AS round_status FROM pairing p JOIN debate_round r ON r.id = p.round_id "
                  "WHERE p.id = ? AND p.deleted_at IS NULL", (pairing_id,))
    if not p or p["neg_team_id"] is None:
        raise UserError("That debate doesn't exist (or is a bye).", 404)
    access = debate_access(conn, request.state.actor, p["event_id"])
    my_adj = adjudicates(conn, request.state.actor, pairing_id)
    if access != "manage" and not my_adj:
        raise UserError("Only the adjudicators of this debate (or staff) can enter its ballot.", 403)
    e = S.get_event(conn, p["event_id"])
    teams = {}
    for side, tid in (("Affirmative", p["aff_team_id"]), ("Negative", p["neg_team_id"])):
        t = one(conn, "SELECT * FROM team WHERE id = ?", (tid,))
        t["side"] = side
        t["members"] = rows(conn, "SELECT st.id, st.first_name, st.last_initial FROM team_member tm JOIN student st ON st.id = tm.student_id "
                                  "WHERE tm.team_id = ? AND tm.deleted_at IS NULL ORDER BY tm.position", (tid,))
        teams[tid] = t
    panel = rows(conn, "SELECT a.id, a.name, pa.role FROM pairing_adjudicator pa JOIN adjudicator a ON a.id = pa.adjudicator_id "
                       "WHERE pa.pairing_id = ? AND pa.deleted_at IS NULL ORDER BY pa.role = 'chair' DESC", (pairing_id,))
    existing = rows(conn, "SELECT b.*, a.name AS adjudicator FROM ballot b LEFT JOIN adjudicator a ON a.id = b.adjudicator_id "
                          "WHERE b.pairing_id = ? AND b.deleted_at IS NULL", (pairing_id,))
    crit = S.criteria(conn, e["rubric_id"])
    descriptors = {}
    for d in rows(conn, "SELECT * FROM rubric_descriptor WHERE criterion_id IN (SELECT id FROM rubric_criterion WHERE rubric_id = ?) "
                        "AND deleted_at IS NULL ORDER BY level", (e["rubric_id"],)):
        descriptors.setdefault(d["criterion_id"], []).append(d)
    return {"p": p, "e": e, "teams": teams, "panel": panel, "existing": existing, "crit": crit, "descriptors": descriptors,
            "my_adj": my_adj, "access": access, "result": S.pairing_result(conn, pairing_id),
            "roles": ROLES.get(e["speakers_per_team"], []),
            "prompts": rows(conn, "SELECT * FROM feedback_prompt WHERE deleted_at IS NULL ORDER BY criterion = 'overall', criterion, position")}


@router.get("/debating/pairings/{pairing_id}/ballot")
def ballot_form(request: Request, pairing_id: int, sess=Depends(require_any)):
    with request.app.state.db.read() as conn:
        ctx = _ballot_context(conn, request, pairing_id)
    return render(request, "debating/ballot.html", {"title": f"Ballot: round {ctx['p']['number']}", **ctx})


@router.post("/debating/pairings/{pairing_id}/ballot")
def ballot_submit(request: Request, pairing_id: int, sess=Depends(require_any), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        ctx = _ballot_context(w.conn, request, pairing_id)
        adj = ctx["my_adj"] if ctx["access"] != "manage" else form_int(form.get("adjudicator_id"))
        if ctx["access"] == "manage" and adj and adj not in [a["id"] for a in ctx["panel"]]:
            raise UserError("That adjudicator isn't on this debate's panel.")
        scores, speakers, comments = {}, {}, {}
        for tid in ctx["teams"]:
            for pos in range(1, ctx["e"]["speakers_per_team"] + 1):
                sc = {}
                for c in ctx["crit"]:
                    v = form.get(f"s_{tid}_{pos}_{c['id']}")
                    if v not in (None, ""):
                        try:
                            sc[c["id"]] = float(v)
                        except ValueError:
                            raise UserError(f"Scores must be numbers (speaker {pos}, {c['name']}).")
                scores[(tid, pos)] = sc
                speakers[(tid, pos)] = form_int(form.get(f"spk_{tid}_{pos}"))
                comments[(tid, pos)] = form.get(f"c_{tid}_{pos}") or ""
        S.submit_ballot(w, pairing_id, adj, scores, speakers, form_int(form.get("winner")), form.get("comments") or "", comments)
    back = f"/debating/rounds/{ctx['p']['round_id']}" if ctx["access"] == "manage" else "/me"
    return redirect(back, "Ballot saved. Thank you.")


# ---------- results, house points ----------

@router.get("/debating/events/{event_id}/results")
def results(request: Request, event_id: int, sess=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        e = _event(conn, request, event_id)
        lad = S.ladder(conn, event_id)
        tab = S.speaker_tab(conn, event_id)
        totals = S.house_totals(conn, event_id)
        entries = rows(conn, "SELECT he.*, h.name AS house FROM house_points_entry he JOIN house h ON h.id = he.house_id WHERE he.event_id = ? "
                             "ORDER BY he.id DESC LIMIT 300", (event_id,))
        houses = rows(conn, "SELECT * FROM house WHERE deleted_at IS NULL ORDER BY name")
    return render(request, "debating/results.html", {"title": f"Results: {e['name']}", "e": e, "ladder": lad, "tab": tab,
                                                     "totals": totals, "entries": entries, "houses": houses})


@router.get("/debating/events/{event_id}/results.csv")
def results_csv(request: Request, event_id: int, what: str = "ladder", sess=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        _event(conn, request, event_id)
        data = S.ladder(conn, event_id) if what == "ladder" else S.speaker_tab(conn, event_id)
    return Response(csv_bytes(data), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{what}-{event_id}.csv"'})


@router.post("/debating/events/{event_id}/housepoints")
def house_points(request: Request, event_id: int, sess=Depends(require_staff), form=Depends(form_data)):
    action = form.get("action")
    with request.app.state.db.write(request.state.actor) as w:
        _event(w.conn, request, event_id)
        if action == "final":
            msg = f"{S.award_house_points(w, event_id, final=True)} final placing entries added."
        elif action == "all_rounds":
            n = sum(S.award_house_points(w, event_id, round_id=r["id"]) for r in
                    rows(w.conn, "SELECT id FROM debate_round WHERE event_id = ? AND deleted_at IS NULL", (event_id,)))
            msg = f"{n} entries added for debates not already counted."
        elif action == "manual":
            pts = form_float(form.get("points"))
            hid = form_int(form.get("house_id"))
            reason = (form.get("reason") or "").strip()
            if pts is None or not hid or not reason:
                raise UserError("Give the house, the points and a reason.")
            w.insert("house_points_entry", {"event_id": event_id, "house_id": hid, "points": pts, "reason": reason[:200],
                                            "source_kind": "manual", "entered_by": w.actor.label, "created_at": now_iso()},
                     S.ch(event_id))
            msg = "Points added."
        elif action == "reverse":
            S.reverse_entry(w, form_int(form.get("entry_id")), form.get("reason") or "")
            msg = "Entry reversed (both entries stay in the record)."
        else:
            raise UserError("Unknown action.")
    return redirect(f"/debating/events/{event_id}/results", msg)


# ---------- run sheet and MC script ----------

@router.get("/debating/events/{event_id}/documents/{kind}")
def documents(request: Request, event_id: int, kind: str, sess=Depends(require_staff)):
    if kind not in ("run_sheet", "mc_script"):
        raise UserError("Not found.", 404)
    with request.app.state.db.read() as conn:
        e = _event(conn, request, event_id)
        versions = rows(conn, "SELECT * FROM event_document WHERE event_id = ? AND kind = ? ORDER BY version DESC", (event_id, kind))
        draft = versions[0]["body"] if versions else S.generate_document(conn, event_id, kind)
        templates = S.templates_for(conn, kind)
    label = {"run_sheet": "Run sheet", "mc_script": "MC script"}[kind]
    return render(request, "debating/document.html", {"title": f"{label}: {e['name']}", "e": e, "kind": kind, "label": label,
                                                      "versions": versions, "draft": draft, "templates": templates,
                                                      "default_template": S.DEFAULT_TEMPLATE.get((e["kind"], kind))})


@router.post("/debating/events/{event_id}/documents/{kind}")
def documents_save(request: Request, event_id: int, kind: str, sess=Depends(require_staff), form=Depends(form_data)):
    if kind not in ("run_sheet", "mc_script"):
        raise UserError("Not found.", 404)
    with request.app.state.db.write(request.state.actor) as w:
        _event(w.conn, request, event_id)
        if form.get("action") == "generate":
            S.save_document(w, event_id, kind, S.generate_document(w.conn, event_id, kind, form.get("template") or None), True)
            msg = "Regenerated from the template as a new version."
        else:
            body = (form.get("body") or "").strip()
            if not body:
                raise UserError("The document is empty.")
            S.save_document(w, event_id, kind, body[:200_000], False)
            msg = "Saved as a new version."
    return redirect(f"/debating/events/{event_id}/documents/{kind}", msg)


@router.get("/debating/events/{event_id}/documents/{kind}/export.docx")
def documents_docx(request: Request, event_id: int, kind: str, sess=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        e = _event(conn, request, event_id)
        body = scalar(conn, "SELECT body FROM event_document WHERE event_id = ? AND kind = ? ORDER BY version DESC LIMIT 1", (event_id, kind)) \
            or S.generate_document(conn, event_id, kind)
    label = {"run_sheet": "Run sheet", "mc_script": "MC script"}.get(kind, kind)
    return Response(text_docx(f"{label} — {e['name']}", body), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="{kind}-{event_id}.docx"'})


@router.get("/debating/events/{event_id}/documents/{kind}/print")
def documents_print(request: Request, event_id: int, kind: str, sess=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        e = _event(conn, request, event_id)
        body = scalar(conn, "SELECT body FROM event_document WHERE event_id = ? AND kind = ? ORDER BY version DESC LIMIT 1", (event_id, kind)) \
            or S.generate_document(conn, event_id, kind)
    return render(request, "debating/document_print.html", {"title": e["name"], "body": body, "e": e, "kind": kind})


# ---------- projector ----------

def _projector_ctx(conn, token: str) -> dict:
    e = one(conn, "SELECT * FROM debate_event WHERE projector_token = ? AND deleted_at IS NULL", (token,))
    if not e:
        raise UserError("That projector link isn't valid. Copy it again from the event page.", 404)
    r = one(conn, "SELECT * FROM debate_round WHERE event_id = ? AND status = 'released' AND deleted_at IS NULL ORDER BY number DESC LIMIT 1",
            (e["id"],))
    return {"e": e, "r": r, "draw": S.round_draw(conn, r["id"]) if r else [], "totals": S.house_totals(conn, e["id"]),
            "ladder": S.ladder(conn, e["id"])[:10], "token": token}


@router.get("/debating/projector/{token}")
def projector(request: Request, token: str):
    with request.app.state.db.read() as conn:
        ctx = _projector_ctx(conn, token)
    return render(request, "debating/projector.html", {"title": ctx["e"]["name"], **ctx})


@router.get("/debating/projector/{token}/f")
def projector_fragment(request: Request, token: str):
    with request.app.state.db.read() as conn:
        ctx = _projector_ctx(conn, token)
    return render(request, "debating/_projector_main.html", ctx)


# ---------- practice ----------

@router.get("/debating/practice")
def practice_page(request: Request, class_id: int | None = None, sess=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        ids = staff_class_ids(conn, request.state.actor)
        classes = [c for c in rows(conn, "SELECT * FROM class WHERE deleted_at IS NULL AND archived_at IS NULL ORDER BY name")
                   if ids is None or c["id"] in ids]
        if class_id and not any(c["id"] == class_id for c in classes):
            raise UserError("You aren't assigned to that class.", 403)
        students = _class_students(conn, class_id) if class_id else []
        motions = rows(conn, "SELECT motion FROM motion_bank WHERE deleted_at IS NULL ORDER BY level, id")
    plans = {n: plan_practice(n) for n in range(1, 26)}
    return render(request, "debating/practice.html", {"title": "Practice debates", "classes": classes, "class_id": class_id,
                                                      "students": students, "motions": motions, "plans": plans})


@router.post("/debating/practice")
def practice_create(request: Request, sess=Depends(require_staff), form=Depends(form_data)):
    class_id = form_int(form.get("class_id"))
    sids = [int(x) for x in form.getlist("student_id") if x]
    with request.app.state.db.write(request.state.actor) as w:
        ids = staff_class_ids(w.conn, request.state.actor)
        if not class_id or (ids is not None and class_id not in ids):
            raise UserError("Choose one of your classes.")
        valid = {s["id"] for s in _class_students(w.conn, class_id)}
        sids = [s for s in sids if s in valid]
        motion = form.get("motion") or ""
        if not motion:
            ms = [m["motion"] for m in rows(w.conn, "SELECT motion FROM motion_bank WHERE deleted_at IS NULL")]
            motion = random.choice(ms) if ms else ""
        out = S.create_practice(w, class_id, sids, motion)
    if out["solo"]:
        return redirect(f"/debating/practice?class_id={class_id}", "One student: use solo speech practice (the student opens Practise on their page).")
    return redirect(f"/debating/rounds/{out['round_id']}", f"Practice set up: {len(out['rooms'])} room(s). Motion: {motion}")


@router.get("/me/practice")
def my_practice(request: Request, mode: str = "impromptu", speech: int | None = None, sess=Depends(require_student)):
    from app.modules.debating import prep as P
    mode = mode if mode in ("impromptu", "prepared", "rebuttal") else "impromptu"
    with request.app.state.db.read() as conn:
        rub = one(conn, "SELECT * FROM rubric WHERE code = 'speech_practice' AND deleted_at IS NULL") or \
            one(conn, "SELECT * FROM rubric WHERE kind = 'speech' AND deleted_at IS NULL ORDER BY id LIMIT 1")
        crit = S.criteria(conn, rub["id"]) if rub else []
        descriptors = {}
        for d in rows(conn, "SELECT * FROM rubric_descriptor WHERE criterion_id IN (SELECT id FROM rubric_criterion WHERE rubric_id = ?) "
                            "AND deleted_at IS NULL ORDER BY level", (rub["id"] if rub else 0,)):
            descriptors.setdefault(d["criterion_id"], []).append(d)
        past = rows(conn, "SELECT * FROM practice_speech WHERE student_id = ? AND deleted_at IS NULL ORDER BY id DESC LIMIT 20",
                    (sess.actor.id,))
        material = P.practice_material(conn, sess.actor.id)
        structures = P.templates(conn, "impromptu")
        level = one(conn, "SELECT year FROM class WHERE id = ?", (sess.actor.class_id,)) if sess.actor.class_id else None
    for p in past:
        p["scores"] = json.loads(p["self_scores"] or "{}")
        p["staff"] = json.loads(p["staff_scores"] or "{}")
    chosen = next((m for m in material["prepared"] if m["id"] == speech), None)
    year = (level or {}).get("year") or 9
    return render(request, "debating/my_practice.html", {"title": "Practise a speech", "rub": rub, "crit": crit, "descriptors": descriptors,
                                                         "past": past, "mode": mode, "material": material, "structures": structures,
                                                         "chosen": chosen, "level": "junior" if year <= 8 else ("middle" if year <= 10 else "senior")})


@router.post("/me/practice")
def my_practice_save(request: Request, sess=Depends(require_student), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        rub = one(w.conn, "SELECT * FROM rubric WHERE code = 'speech_practice' AND deleted_at IS NULL") or \
            one(w.conn, "SELECT * FROM rubric WHERE kind = 'speech' AND deleted_at IS NULL ORDER BY id LIMIT 1")
        if not rub:
            raise UserError("No speech rubric is set up. Ask your teacher.")
        scores = {k[2:]: form.get(k) for k in form.keys() if k.startswith("c_")}
        topic = (form.get("topic") or "").strip()
        prefix = {"impromptu": "Impromptu: ", "rebuttal": "Rebuttal drill: "}.get(form.get("mode") or "", "")
        if prefix and topic and not topic.startswith(prefix):
            topic = prefix + topic
        S.save_practice_speech(w, sess.actor.id, rub["id"], topic[:300], form_int(form.get("target_seconds"), 180) or 180,
                               form_int(form.get("actual_seconds")), scores, form.get("reflection") or "")
    mode = form.get("mode") if form.get("mode") in ("impromptu", "prepared", "rebuttal") else "impromptu"
    return redirect(f"/me/practice?mode={mode}", "Practice saved. Look back at your scores over time to see your progress.")


@router.get("/debating/practice-speeches")
def practice_speeches(request: Request, class_id: int, sess=Depends(require_staff)):
    """Staff view of a class's practice speeches, to add feedback."""
    with request.app.state.db.read() as conn:
        ids = staff_class_ids(conn, request.state.actor)
        if ids is not None and class_id not in ids:
            raise UserError("You aren't assigned to that class.", 403)
        data = rows(conn, "SELECT ps.*, st.first_name, st.last_initial FROM practice_speech ps JOIN student st ON st.id = ps.student_id "
                          "WHERE st.class_id = ? AND ps.deleted_at IS NULL ORDER BY ps.id DESC LIMIT 200", (class_id,))
        crit = {c["id"]: c for c in rows(conn, "SELECT * FROM rubric_criterion")}
    for d in data:
        d["scores"] = {crit[int(k)]["name"]: v for k, v in json.loads(d["self_scores"] or "{}").items() if int(k) in crit}
    return render(request, "debating/practice_speeches.html", {"title": "Practice speeches", "data": data, "class_id": class_id})


@router.post("/debating/practice-speeches/{ps_id}")
def practice_feedback(request: Request, ps_id: int, sess=Depends(require_staff), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        ps = one(w.conn, "SELECT ps.*, st.class_id FROM practice_speech ps JOIN student st ON st.id = ps.student_id WHERE ps.id = ?", (ps_id,))
        if not ps:
            raise UserError("Not found.", 404)
        ids = staff_class_ids(w.conn, request.state.actor)
        if ids is not None and ps["class_id"] not in ids:
            raise UserError("You aren't assigned to that class.", 403)
        w.update("practice_speech", ps_id, {"staff_comment": (form.get("staff_comment") or "")[:2000]})
    return redirect(f"/debating/practice-speeches?class_id={ps['class_id']}", "Feedback saved.")


@router.post("/debating/demo-carnival")
def demo_carnival(request: Request, sess=Depends(require_staff), form=Depends(form_data)):
    """Demo mode only: generate a full fake house carnival (325 students, 4 rounds) to explore."""
    if not request.app.state.settings.is_demo:
        raise UserError("The practice carnival can only be generated in demo mode (fake data).", 403)
    if not request.state.actor.is_coordinator:
        raise UserError("Only the coordinator can do that.", 403)
    from app.modules.debating.demo import make_carnival
    n = max(8, min(form_int(form.get("students"), 325) or 325, 400))
    with request.app.state.db.write(request.state.actor) as w:
        info = make_carnival(w, n_students=n, n_rounds=max(1, min(form_int(form.get("rounds"), 4) or 4, 8)), seed=n)
    return redirect(f"/debating/events/{info['event_id']}",
                    f"Generated a demo carnival: {info['students']} fake students in {info['teams']} teams, {info['rooms']} rooms.")
