"""Model UN: conferences, committees, delegations, resolution workspace, evidence,
predictions, swing, amendment comparison, lobbying tasks, actual votes, calibration, exports.

Access (enforced here, on the server):
- coordinator: everything; staff: committees linked to their classes;
- students: committees of their class. They edit only paragraphs their
  delegation owns, table amendments and add evidence ("student intel") for
  their own delegation, and see their own delegation's tasks.
"""
from __future__ import annotations

import difflib

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from markupsafe import Markup, escape

from app.db import one, rows, scalar, undo_last
from app.errors import UserError
from app.exports import csv_bytes, resolution_docx
from app.modules.mun import predict as P
from app.modules.mun import service as S
from app.util import display_name
from app.web.auth import committee_access, require_any, require_coordinator, require_staff, staff_class_ids
from app.web.http import form_int, redirect, form_data
from app.web.templating import render

router = APIRouter(prefix="/mun")


# ---------- access helpers ----------

def _access(conn, request, committee_id: int, need: str = "participate") -> str:
    a = committee_access(conn, request.state.actor, committee_id)
    if a == "none" or (need == "manage" and a != "manage"):
        raise UserError("You don't have access to that committee." if a == "none" else "Only staff can do that.", 403)
    return a


def _my_delegation(conn, actor, committee_id: int) -> dict | None:
    if actor.kind != "student":
        return None
    return one(conn, "SELECT d.* FROM delegation d JOIN delegation_member dm ON dm.delegation_id = d.id "
                     "WHERE dm.student_id = ? AND d.committee_id = ? AND dm.deleted_at IS NULL AND d.deleted_at IS NULL",
               (actor.id, committee_id))


def _committee_of_resolution(conn, resolution_id: int) -> int:
    cid = scalar(conn, "SELECT committee_id FROM resolution WHERE id = ? AND deleted_at IS NULL", (resolution_id,))
    if not cid:
        raise UserError("That resolution doesn't exist.", 404)
    return cid


def _committee_of_paragraph(conn, paragraph_id: int) -> int:
    cid = scalar(conn, "SELECT r.committee_id FROM paragraph p JOIN resolution r ON r.id = p.resolution_id WHERE p.id = ?",
                 (paragraph_id,))
    if not cid:
        raise UserError("That paragraph doesn't exist.", 404)
    return cid


def _committee_of_amendment(conn, amendment_id: int) -> int:
    cid = scalar(conn, "SELECT r.committee_id FROM amendment a JOIN paragraph p ON p.id = a.paragraph_id "
                       "JOIN resolution r ON r.id = p.resolution_id WHERE a.id = ?", (amendment_id,))
    if not cid:
        raise UserError("That amendment doesn't exist.", 404)
    return cid


def _committee_of_target(conn, kind: str, tid: int) -> int:
    finder = {"paragraph": _committee_of_paragraph, "amendment": _committee_of_amendment,
              "resolution": _committee_of_resolution}.get(kind)
    if finder is None:
        raise UserError("Predictions are for a paragraph, an amendment or a resolution.", 404)
    return finder(conn, tid)


def _ref(conn):
    return {
        "rules": rows(conn, "SELECT id, name FROM voting_rule WHERE deleted_at IS NULL ORDER BY name"),
        "types": rows(conn, "SELECT id, name FROM committee_type WHERE deleted_at IS NULL ORDER BY name"),
        "topics": rows(conn, "SELECT id, name FROM topic WHERE deleted_at IS NULL ORDER BY name"),
        "classes": rows(conn, "SELECT id, name FROM class WHERE deleted_at IS NULL AND archived_at IS NULL ORDER BY name"),
    }


# ---------- conferences and committees ----------

@router.get("")
def mun_home(request: Request, s=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        confs = rows(conn, "SELECT * FROM conference WHERE deleted_at IS NULL ORDER BY id DESC")
        coms = rows(conn, "SELECT cm.*, vr.name AS rule FROM committee cm JOIN voting_rule vr ON vr.id = cm.voting_rule_id "
                          "WHERE cm.deleted_at IS NULL ORDER BY cm.id")
        ids = staff_class_ids(conn, s.actor)
    if ids is not None:
        coms = [c for c in coms if c["class_id"] in ids]
    by_conf: dict = {}
    for c in coms:
        by_conf.setdefault(c["conference_id"], []).append(c)
    return render(request, "mun/home.html", {"title": "Model UN", "confs": confs, "by_conf": by_conf})


@router.post("/conferences")
def conference_create(request: Request, s=Depends(require_coordinator), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        cid = S.create_conference(w, form.get("name"), form.get("starts_on"), form.get("ends_on"), form.get("organiser"))
    return redirect(f"/mun/conferences/{cid}", "Conference created. Now add a committee.")


@router.post("/load-pack")
def load_pack(request: Request, s=Depends(require_coordinator), form=Depends(form_data)):
    from app.modules.mun.packs import load_climate_conference
    with request.app.state.db.write(request.state.actor) as w:
        info = load_climate_conference(w, form_int(form.get("class_id")))
    return redirect(f"/mun/committees/{info['committee_id']}", "Loaded the UNAA 2026 climate pack as a conference. "
                    "Every value is an unsourced estimate until you attach sources.")


@router.get("/conferences/{conf_id}")
def conference_view(request: Request, conf_id: int, s=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        conf = one(conn, "SELECT * FROM conference WHERE id = ? AND deleted_at IS NULL", (conf_id,))
        if not conf:
            raise UserError("That conference doesn't exist.", 404)
        coms = rows(conn, "SELECT cm.*, vr.name AS rule, (SELECT COUNT(*) FROM delegation d WHERE d.committee_id = cm.id AND d.deleted_at IS NULL) AS n "
                          "FROM committee cm JOIN voting_rule vr ON vr.id = cm.voting_rule_id WHERE cm.conference_id = ? AND cm.deleted_at IS NULL",
                    (conf_id,))
        ref = _ref(conn)
    return render(request, "mun/conference.html", {"title": conf["name"], "conf": conf, "coms": coms, **ref})


@router.post("/conferences/{conf_id}/committees")
def committee_create(request: Request, conf_id: int, s=Depends(require_coordinator), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        cid = S.create_committee(w, conf_id, form.get("name"), form_int(form.get("committee_type_id")),
                                 form_int(form.get("voting_rule_id")), form_int(form.get("topic_id")),
                                 form_int(form.get("class_id")))
    return redirect(f"/mun/committees/{cid}", "Committee created. Add delegations next.")


@router.get("/committees/{committee_id}")
def committee_view(request: Request, committee_id: int, s=Depends(require_any)):
    with request.app.state.db.read() as conn:
        access = _access(conn, request, committee_id)
        com = one(conn, "SELECT cm.*, cf.name AS conference, vr.name AS rule, vr.notes AS rule_notes, t.name AS topic, cl.name AS class_name "
                        "FROM committee cm JOIN conference cf ON cf.id = cm.conference_id JOIN voting_rule vr ON vr.id = cm.voting_rule_id "
                        "LEFT JOIN topic t ON t.id = cm.topic_id LEFT JOIN class cl ON cl.id = cm.class_id WHERE cm.id = ?", (committee_id,))
        dels = rows(conn, "SELECT d.*, c.name, c.flag_svg, c.p5 FROM delegation d JOIN country c ON c.iso3 = d.iso3 "
                          "WHERE d.committee_id = ? AND d.deleted_at IS NULL ORDER BY c.name", (committee_id,))
        members = rows(conn, "SELECT dm.*, st.first_name, st.last_initial FROM delegation_member dm JOIN student st ON st.id = dm.student_id "
                             "JOIN delegation d ON d.id = dm.delegation_id WHERE d.committee_id = ? AND dm.deleted_at IS NULL "
                             "ORDER BY dm.role = 'head' DESC, st.first_name", (committee_id,))
        by_del: dict = {}
        for m in members:
            by_del.setdefault(m["delegation_id"], []).append(m)
        resolutions = rows(conn, "SELECT * FROM resolution WHERE committee_id = ? AND deleted_at IS NULL ORDER BY id", (committee_id,))
        students = rows(conn, "SELECT * FROM student WHERE class_id = ? AND deleted_at IS NULL AND active = 1 ORDER BY first_name",
                        (com["class_id"],)) if com["class_id"] else []
        countries = rows(conn, "SELECT iso3, name FROM country WHERE deleted_at IS NULL ORDER BY name")
        blocs = rows(conn, "SELECT id, code, name FROM bloc WHERE deleted_at IS NULL ORDER BY name")
        mine = _my_delegation(conn, request.state.actor, committee_id)
        tq = "SELECT t.*, d.iso3, st.first_name, st.last_initial FROM task t JOIN delegation d ON d.id = t.delegation_id " \
             "LEFT JOIN student st ON st.id = t.assignee_student_id WHERE d.committee_id = ? AND t.deleted_at IS NULL"
        if access == "manage":
            tasks = rows(conn, tq + " ORDER BY t.status, t.id", (committee_id,))
        else:   # students see only their own delegation's tasks
            tasks = rows(conn, tq + " AND t.delegation_id = ? ORDER BY t.status, t.id", (committee_id, mine["id"] if mine else -1))
    allocated = {m["student_id"] for m in members}
    return render(request, "mun/committee.html", {
        "title": com["name"], "com": com, "dels": dels, "by_del": by_del, "resolutions": resolutions, "students": students,
        "unallocated": [st for st in students if st["id"] not in allocated], "countries": countries, "blocs": blocs,
        "access": access, "mine": mine, "tasks": tasks})


@router.post("/committees/{committee_id}/delegations")
def delegations_add(request: Request, committee_id: int, s=Depends(require_staff), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        _access(w.conn, request, committee_id, "manage")
        isos = [x for x in form.getlist("iso3") if x]
        isos += [x for x in (form.get("iso3_list") or "").replace(",", " ").split() if x]
        bloc = form_int(form.get("bloc_id"))
        if bloc:
            isos += [r["iso3"] for r in rows(w.conn, "SELECT iso3 FROM bloc_member WHERE bloc_id = ? AND deleted_at IS NULL", (bloc,))]
        if form.get("all_un"):
            isos += [r["iso3"] for r in rows(w.conn, "SELECT iso3 FROM country WHERE un_member = 1 AND deleted_at IS NULL")]
        if not isos:
            raise UserError("Choose at least one country (or a bloc, or all UN members).")
        n = len(S.add_delegations(w, committee_id, sorted(set(isos))))
    return redirect(f"/mun/committees/{committee_id}", f"{n} delegation(s) in the committee.")


@router.post("/delegations/{delegation_id}/remove")
def delegation_remove(request: Request, delegation_id: int, s=Depends(require_staff), form=Depends(form_data)):
    if form.get("confirm") != "yes":
        raise UserError("Tick the confirmation box to remove the delegation.")
    with request.app.state.db.write(request.state.actor) as w:
        d = one(w.conn, "SELECT * FROM delegation WHERE id = ?", (delegation_id,))
        if not d:
            raise UserError("That delegation doesn't exist.", 404)
        _access(w.conn, request, d["committee_id"], "manage")
        w.soft_delete("delegation", delegation_id, S.committee_channel(d["committee_id"]))
    return redirect(f"/mun/committees/{d['committee_id']}", f"Removed {d['iso3']}. Undo is available.")


@router.post("/committees/{committee_id}/allocate")
def allocate(request: Request, committee_id: int, s=Depends(require_staff), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        _access(w.conn, request, committee_id, "manage")
        sid, did = form_int(form.get("student_id")), form_int(form.get("delegation_id"))
        if sid and did:
            S.assign_member(w, did, sid, form.get("role") or "delegate")
            msg = "Student allocated."
        else:
            com = one(w.conn, "SELECT class_id FROM committee WHERE id = ?", (committee_id,))
            if not com["class_id"]:
                raise UserError("Link this committee to a class first (Admin can set it), then allocate.")
            ids = [r["id"] for r in rows(w.conn, "SELECT id FROM student WHERE class_id = ? AND active = 1 AND deleted_at IS NULL "
                                                 "ORDER BY first_name, last_initial", (com["class_id"],))]
            msg = f"Allocated {S.allocate_round_robin(w, committee_id, ids)} student(s), filling empty delegations first."
    return redirect(f"/mun/committees/{committee_id}", msg)


@router.post("/members/{member_id}/remove")
def member_remove(request: Request, member_id: int, s=Depends(require_staff)):
    with request.app.state.db.write(request.state.actor) as w:
        m = one(w.conn, "SELECT dm.*, d.committee_id FROM delegation_member dm JOIN delegation d ON d.id = dm.delegation_id WHERE dm.id = ?",
                (member_id,))
        if not m:
            raise UserError("Not found.", 404)
        _access(w.conn, request, m["committee_id"], "manage")
        S.remove_member(w, member_id)
    return redirect(f"/mun/committees/{m['committee_id']}", "Student removed from the delegation.")


@router.post("/committees/{committee_id}/settings")
def committee_settings(request: Request, committee_id: int, s=Depends(require_coordinator), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        changes = {"name": (form.get("name") or "").strip() or None, "voting_rule_id": form_int(form.get("voting_rule_id")),
                   "topic_id": form_int(form.get("topic_id")), "class_id": form_int(form.get("class_id"))}
        w.update("committee", committee_id, {k: v for k, v in changes.items() if v is not None or k == "class_id"},
                 S.committee_channel(committee_id))
    return redirect(f"/mun/committees/{committee_id}", "Committee settings saved.")


# ---------- resolution workspace ----------

@router.post("/committees/{committee_id}/resolutions")
def resolution_create(request: Request, committee_id: int, s=Depends(require_any), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        access = _access(w.conn, request, committee_id)
        if access != "manage" and not _my_delegation(w.conn, request.state.actor, committee_id):
            raise UserError("Only staff or a delegation member can start a resolution.", 403)
        rid = S.create_resolution(w, committee_id, form.get("title"))
    return redirect(f"/mun/resolutions/{rid}", "Draft resolution created.")


def workspace_context(conn, request, resolution_id: int) -> dict:
    committee_id = _committee_of_resolution(conn, resolution_id)
    access = _access(conn, request, committee_id)
    res = one(conn, "SELECT * FROM resolution WHERE id = ?", (resolution_id,))
    com = one(conn, "SELECT cm.*, vr.name AS rule FROM committee cm JOIN voting_rule vr ON vr.id = cm.voting_rule_id WHERE cm.id = ?",
              (committee_id,))
    paras = rows(conn, "SELECT p.*, v.text, v.tags, v.created_at AS version_at, v.author_label, c.name AS owner_name, d.iso3 AS owner_iso3, "
                       "(SELECT COUNT(*) FROM paragraph_version pv WHERE pv.paragraph_id = p.id) AS versions "
                       "FROM paragraph p JOIN paragraph_version v ON v.id = p.current_version_id "
                       "LEFT JOIN delegation d ON d.id = p.owner_delegation_id LEFT JOIN country c ON c.iso3 = d.iso3 "
                       "WHERE p.resolution_id = ? AND p.deleted_at IS NULL ORDER BY p.kind = 'operative', p.position", (resolution_id,))
    mine = _my_delegation(conn, request.state.actor, committee_id)
    # Drafts (D-068) are shown only to their sponsors and to staff running the class.
    amends = rows(conn, "SELECT a.*, c.name AS sponsor_name, d.iso3 AS sponsor_iso3 FROM amendment a "
                        "LEFT JOIN delegation d ON d.id = a.sponsor_delegation_id LEFT JOIN country c ON c.iso3 = d.iso3 "
                        "JOIN paragraph p ON p.id = a.paragraph_id WHERE p.resolution_id = ? AND a.deleted_at IS NULL "
                        "AND (a.submitted_at IS NOT NULL OR ? OR a.sponsor_delegation_id = ?) ORDER BY a.id",
                  (resolution_id, int(access == "manage"), mine["id"] if mine else -1))
    support = rows(conn, "SELECT s.*, d.iso3 FROM amendment_support s JOIN delegation d ON d.id = s.delegation_id "
                         "JOIN amendment a ON a.id = s.amendment_id JOIN paragraph p ON p.id = a.paragraph_id "
                         "WHERE p.resolution_id = ? AND s.deleted_at IS NULL ORDER BY s.seq", (resolution_id,))
    sup: dict = {}
    for s_ in support:
        sup.setdefault(s_["amendment_id"], []).append(s_)
    by_para: dict = {}
    for a in amends:
        by_para.setdefault(a["paragraph_id"], []).append(a)
    floor = {p["id"]: S.amendment_on_floor(conn, p["id"]) for p in paras if by_para.get(p["id"])}
    dels = rows(conn, "SELECT d.id, d.iso3, c.name FROM delegation d JOIN country c ON c.iso3 = d.iso3 "
                      "WHERE d.committee_id = ? AND d.deleted_at IS NULL ORDER BY c.name", (committee_id,))
    tags = rows(conn, "SELECT code, label FROM tag WHERE topic_id = ? AND deleted_at IS NULL ORDER BY code", (com["topic_id"],)) \
        if com["topic_id"] else []
    locks = {}
    if one(conn, "SELECT 1 FROM sqlite_master WHERE name = 'paragraph_lock'"):
        from app.modules.mun.locks import active_locks
        locks = active_locks(conn, resolution_id, request.state.actor)
    return {"res": res, "com": com, "paras": paras, "by_para": by_para, "sup": sup, "floor": floor, "dels": dels,
            "tags": tags, "access": access, "mine": mine, "locks": locks}


@router.get("/resolutions/{resolution_id}")
def workspace(request: Request, resolution_id: int, s=Depends(require_any)):
    with request.app.state.db.read() as conn:
        ctx = workspace_context(conn, request, resolution_id)
    return render(request, "mun/workspace.html", {"title": ctx["res"]["title"], **ctx})


@router.get("/resolutions/{resolution_id}/fragment")
def workspace_fragment(request: Request, resolution_id: int, s=Depends(require_any)):
    with request.app.state.db.read() as conn:
        ctx = workspace_context(conn, request, resolution_id)
    return render(request, "mun/_paragraphs.html", ctx)


def _can_edit_paragraph(conn, request, p: dict, access: str) -> bool:
    if access == "manage":
        return True
    mine = _my_delegation(conn, request.state.actor, p["committee_id"])
    return bool(mine and p["owner_delegation_id"] == mine["id"])


@router.post("/resolutions/{resolution_id}/paragraphs")
def paragraph_add(request: Request, resolution_id: int, s=Depends(require_any), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        committee_id = _committee_of_resolution(w.conn, resolution_id)
        access = _access(w.conn, request, committee_id)
        owner = form_int(form.get("owner_delegation_id"))
        if access != "manage":
            mine = _my_delegation(w.conn, request.state.actor, committee_id)
            if not mine:
                raise UserError("Only delegation members can add paragraphs.", 403)
            owner = mine["id"]       # students add paragraphs owned by their own delegation
        S.add_paragraph(w, resolution_id, form.get("kind") or "operative", form.get("text"), form.getlist("tags"), owner)
    return redirect(f"/mun/resolutions/{resolution_id}", "Paragraph added.")


@router.post("/paragraphs/{paragraph_id}")
def paragraph_edit(request: Request, paragraph_id: int, s=Depends(require_any), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        p = S.paragraph(w.conn, paragraph_id)
        access = _access(w.conn, request, p["committee_id"])
        if not _can_edit_paragraph(w.conn, request, p, access):
            raise UserError("Only the delegation that owns this paragraph can edit it. You can table an amendment instead.", 403)
        if one(w.conn, "SELECT 1 FROM sqlite_master WHERE name = 'paragraph_lock'"):
            from app.modules.mun.locks import check_can_save
            check_can_save(w, paragraph_id)
        if form.get("owner_delegation_id") is not None and access == "manage":
            S.set_owner(w, paragraph_id, form_int(form.get("owner_delegation_id")))
        S.edit_paragraph(w, paragraph_id, form.get("text"), form.getlist("tags"), form_int(form.get("version_id")),
                         form.get("note") or "")
        if one(w.conn, "SELECT 1 FROM sqlite_master WHERE name = 'paragraph_lock'"):
            from app.modules.mun.locks import release
            release(w, paragraph_id)
    return redirect(f"/mun/resolutions/{p['resolution_id']}#p{paragraph_id}", "Saved as a new version.")


@router.post("/paragraphs/{paragraph_id}/lock")
def paragraph_lock(request: Request, paragraph_id: int, s=Depends(require_any)):
    """Called by the page when an editor opens (and every 20 s while it stays open)."""
    from fastapi.responses import JSONResponse

    from app.modules.mun.locks import acquire
    with request.app.state.db.write(request.state.actor) as w:
        p = S.paragraph(w.conn, paragraph_id)
        access = _access(w.conn, request, p["committee_id"])
        if not _can_edit_paragraph(w.conn, request, p, access):
            raise UserError("Only the delegation that owns this paragraph can edit it.", 403)
        try:
            res = acquire(w, paragraph_id)
        except UserError as e:
            return JSONResponse({"state": "taken", "message": e.message}, status_code=409)
    return JSONResponse(res)


@router.post("/paragraphs/{paragraph_id}/unlock")
def paragraph_unlock(request: Request, paragraph_id: int, s=Depends(require_any)):
    from fastapi.responses import JSONResponse

    from app.modules.mun.locks import release
    with request.app.state.db.write(request.state.actor) as w:
        p = S.paragraph(w.conn, paragraph_id)
        _access(w.conn, request, p["committee_id"])
        release(w, paragraph_id)
    return JSONResponse({"state": "released"})


@router.get("/paragraphs/{paragraph_id}/history")
def paragraph_history(request: Request, paragraph_id: int, s=Depends(require_any)):
    with request.app.state.db.read() as conn:
        p = S.paragraph(conn, paragraph_id)
        access = _access(conn, request, p["committee_id"])
        versions = rows(conn, "SELECT * FROM paragraph_version WHERE paragraph_id = ? ORDER BY id DESC", (paragraph_id,))
    for i, v in enumerate(versions):
        prev = versions[i + 1]["text"] if i + 1 < len(versions) else ""
        v["diff"] = word_diff(prev, v["text"])
    return render(request, "mun/history.html", {"title": f"History of paragraph {p['position']}", "p": p, "versions": versions,
                                                "can_restore": access == "manage"})


def word_diff(a: str, b: str) -> Markup:
    aw, bw = a.split(), b.split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=aw, b=bw).get_opcodes():
        if op == "equal":
            out.append(escape(" ".join(aw[i1:i2])))
        if op in ("delete", "replace"):
            out.append(Markup("<del>") + escape(" ".join(aw[i1:i2])) + Markup("</del>"))
        if op in ("insert", "replace"):
            out.append(Markup("<ins>") + escape(" ".join(bw[j1:j2])) + Markup("</ins>"))
    return Markup(" ").join(out)


@router.post("/paragraphs/{paragraph_id}/restore/{version_id}")
def paragraph_restore(request: Request, paragraph_id: int, version_id: int, s=Depends(require_staff)):
    with request.app.state.db.write(request.state.actor) as w:
        p = S.paragraph(w.conn, paragraph_id)
        _access(w.conn, request, p["committee_id"], "manage")
        S.restore_paragraph_version(w, paragraph_id, version_id)
    return redirect(f"/mun/paragraphs/{paragraph_id}/history", f"Version {version_id} restored as the newest version.")


@router.post("/paragraphs/{paragraph_id}/delete")
def paragraph_delete(request: Request, paragraph_id: int, s=Depends(require_staff), form=Depends(form_data)):
    if form.get("confirm") != "yes":
        raise UserError("Tick the confirmation box to delete the paragraph.")
    with request.app.state.db.write(request.state.actor) as w:
        p = S.paragraph(w.conn, paragraph_id)
        _access(w.conn, request, p["committee_id"], "manage")
        w.soft_delete("paragraph", paragraph_id, S.resolution_channel(p["resolution_id"]))
    return redirect(f"/mun/resolutions/{p['resolution_id']}", "Paragraph deleted. Undo is available.")


@router.post("/paragraphs/{paragraph_id}/amendments")
def amendment_table(request: Request, paragraph_id: int, s=Depends(require_any), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        p = S.paragraph(w.conn, paragraph_id)
        access = _access(w.conn, request, p["committee_id"])
        sponsor = form_int(form.get("sponsor_delegation_id"))
        if access != "manage":
            mine = _my_delegation(w.conn, request.state.actor, p["committee_id"])
            if not mine:
                raise UserError("Only delegation members can table amendments.", 403)
            sponsor = mine["id"]
        aid = S.table_amendment(w, paragraph_id, form.get("kind") or "replace", form.get("proposed_text"),
                                form.getlist("tags"), sponsor, form.get("rationale") or "")
    return redirect(f"/mun/resolutions/{p['resolution_id']}#a{aid}", f"Amendment {aid} tabled.")


@router.post("/amendments/{amendment_id}/support")
def amendment_support(request: Request, amendment_id: int, s=Depends(require_any), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        cid = _committee_of_amendment(w.conn, amendment_id)
        access = _access(w.conn, request, cid)
        did = form_int(form.get("delegation_id"))
        if access != "manage":
            mine = _my_delegation(w.conn, request.state.actor, cid)
            if not mine:
                raise UserError("Only delegation members can support amendments.", 403)
            did = mine["id"]
        if form.get("withdraw"):
            sid = scalar(w.conn, "SELECT id FROM amendment_support WHERE amendment_id = ? AND delegation_id = ? AND kind = ? AND deleted_at IS NULL",
                         (amendment_id, did, form.get("kind")))
            if sid:
                S.withdraw_support(w, sid)
        else:
            S.support_amendment(w, amendment_id, did, form.get("kind") or "second")
        rid = scalar(w.conn, "SELECT p.resolution_id FROM amendment a JOIN paragraph p ON p.id = a.paragraph_id WHERE a.id = ?", (amendment_id,))
    return redirect(f"/mun/resolutions/{rid}#a{amendment_id}", "Support recorded.")


@router.post("/amendments/{amendment_id}/status")
def amendment_status(request: Request, amendment_id: int, s=Depends(require_any), form=Depends(form_data)):
    status = form.get("status")
    with request.app.state.db.write(request.state.actor) as w:
        cid = _committee_of_amendment(w.conn, amendment_id)
        access = _access(w.conn, request, cid)
        if access != "manage":
            a = one(w.conn, "SELECT * FROM amendment WHERE id = ?", (amendment_id,))
            mine = _my_delegation(w.conn, request.state.actor, cid)
            if not (status == "withdrawn" and mine and a["sponsor_delegation_id"] == mine["id"]):
                raise UserError("Only the chair can change an amendment's status (sponsors can withdraw their own).", 403)
        S.set_amendment_status(w, amendment_id, status)
        rid = scalar(w.conn, "SELECT p.resolution_id FROM amendment a JOIN paragraph p ON p.id = a.paragraph_id WHERE a.id = ?", (amendment_id,))
    msg = {"passed": "Amendment passed and applied to the text.", "friendly": "Accepted as friendly and applied to the text.",
           "withdrawn": "Amendment withdrawn.", "failed": "Amendment marked as failed."}.get(status, "Status updated.")
    return redirect(f"/mun/resolutions/{rid}", msg)


@router.post("/resolutions/{resolution_id}/status")
def resolution_status(request: Request, resolution_id: int, s=Depends(require_staff), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        cid = _committee_of_resolution(w.conn, resolution_id)
        _access(w.conn, request, cid, "manage")
        st = form.get("status")
        if st not in ("draft", "tabled", "passed", "failed", "withdrawn"):
            raise UserError("Unknown status.")
        w.update("resolution", resolution_id, {"status": st}, S.committee_channel(cid))
    return redirect(f"/mun/resolutions/{resolution_id}", "Resolution status updated.")


@router.post("/undo")
def mun_undo(request: Request, s=Depends(require_any)):
    entities = {"paragraph", "paragraph_version", "amendment", "amendment_support", "evidence", "task", "resolution",
                "delegation", "delegation_member", "committee", "conference", "actual_vote"}
    with request.app.state.db.write(request.state.actor) as w:
        res = undo_last(w, entities)
        if res:
            # Re-publish the channels touched so open pages refresh.
            for ev in res["events"]:
                w.touch(ev["channel"])
    back = request.headers.get("referer") or "/"
    return redirect(back, "Undid your last change." if res else "Nothing of yours to undo here.")


# ---------- exports ----------

def _resolution_export_data(conn, resolution_id):
    res = one(conn, "SELECT * FROM resolution WHERE id = ?", (resolution_id,))
    com = one(conn, "SELECT * FROM committee WHERE id = ?", (res["committee_id"],))
    paras = rows(conn, "SELECT p.*, v.text FROM paragraph p JOIN paragraph_version v ON v.id = p.current_version_id "
                       "WHERE p.resolution_id = ? AND p.deleted_at IS NULL ORDER BY p.kind = 'operative', p.position", (resolution_id,))
    sponsors = [r["name"] for r in rows(conn, "SELECT DISTINCT c.name FROM paragraph p JOIN delegation d ON d.id = p.owner_delegation_id "
                                             "JOIN country c ON c.iso3 = d.iso3 WHERE p.resolution_id = ? AND p.deleted_at IS NULL ORDER BY c.name",
                                       (resolution_id,))]
    return res, com, [p for p in paras if p["kind"] == "preambular"], [p for p in paras if p["kind"] == "operative"], sponsors


@router.get("/resolutions/{resolution_id}/export.docx")
def resolution_export_docx(request: Request, resolution_id: int, s=Depends(require_any)):
    with request.app.state.db.read() as conn:
        _access(conn, request, _committee_of_resolution(conn, resolution_id))
        res, com, pre, op, sponsors = _resolution_export_data(conn, resolution_id)
    data = resolution_docx(res, com, pre, op, sponsors)
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="resolution-{resolution_id}.docx"'})


@router.get("/resolutions/{resolution_id}/print")
def resolution_print(request: Request, resolution_id: int, s=Depends(require_any)):
    with request.app.state.db.read() as conn:
        _access(conn, request, _committee_of_resolution(conn, resolution_id))
        res, com, pre, op, sponsors = _resolution_export_data(conn, resolution_id)
    return render(request, "mun/print_resolution.html", {"title": res["title"], "res": res, "com": com, "pre": pre, "op": op,
                                                         "sponsors": sponsors})


# ---------- evidence ----------

@router.get("/committees/{committee_id}/evidence")
def evidence_page(request: Request, committee_id: int, iso3: str = "", target_kind: str = "", target_id: int | None = None,
                  s=Depends(require_any)):
    with request.app.state.db.read() as conn:
        access = _access(conn, request, committee_id)
        com = one(conn, "SELECT * FROM committee WHERE id = ?", (committee_id,))
        dels = rows(conn, "SELECT d.iso3, c.name FROM delegation d JOIN country c ON c.iso3 = d.iso3 WHERE d.committee_id = ? "
                          "AND d.deleted_at IS NULL ORDER BY c.name", (committee_id,))
        blocs = rows(conn, "SELECT id, name FROM bloc WHERE deleted_at IS NULL ORDER BY name")
        stypes = rows(conn, "SELECT * FROM source_type WHERE deleted_at IS NULL ORDER BY weight DESC")
        if access != "manage":
            stypes = [t for t in stypes if t["code"] == "student_intel"]
        paras = rows(conn, "SELECT p.id, p.position, p.kind, r.title, v.text FROM paragraph p JOIN resolution r ON r.id = p.resolution_id "
                           "JOIN paragraph_version v ON v.id = p.current_version_id WHERE r.committee_id = ? AND p.deleted_at IS NULL "
                           "AND p.kind = 'operative' ORDER BY r.id, p.position", (committee_id,))
        amends = rows(conn, "SELECT a.id, a.kind, p.position FROM amendment a JOIN paragraph p ON p.id = a.paragraph_id JOIN resolution r "
                            "ON r.id = p.resolution_id WHERE r.committee_id = ? AND a.deleted_at IS NULL AND a.submitted_at IS NOT NULL "
                            "ORDER BY a.id", (committee_id,))
        resolutions = rows(conn, "SELECT id, title FROM resolution WHERE committee_id = ? AND deleted_at IS NULL", (committee_id,))
        tags = rows(conn, "SELECT code, label FROM tag WHERE topic_id = ? AND deleted_at IS NULL ORDER BY code", (com["topic_id"],))
        isos = [d["iso3"] for d in dels]
        ev = rows(conn, "SELECT e.*, b.name AS bloc_name, st.shown_as, c.name AS country FROM evidence e "
                        "LEFT JOIN bloc b ON b.id = e.bloc_id LEFT JOIN country c ON c.iso3 = e.iso3 "
                        "JOIN source_type st ON st.code = e.source_type WHERE e.deleted_at IS NULL AND "
                        f"(e.iso3 IN ({','.join('?' * len(isos)) or 'NULL'}) OR e.subject_kind = 'bloc') "
                        + ("AND e.iso3 = ? " if iso3 else "") + "ORDER BY e.id DESC LIMIT 300",
                  isos + ([iso3.upper()] if iso3 else []))
    return render(request, "mun/evidence.html", {"title": "Evidence", "com": com, "dels": dels, "blocs": blocs, "stypes": stypes,
                                                 "paras": paras, "amends": amends, "resolutions": resolutions, "tags": tags,
                                                 "ev": ev, "access": access, "iso3": iso3.upper(), "target_kind": target_kind,
                                                 "target_id": target_id})


@router.post("/committees/{committee_id}/evidence")
def evidence_add(request: Request, committee_id: int, s=Depends(require_any), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        access = _access(w.conn, request, committee_id)
        com = one(w.conn, "SELECT * FROM committee WHERE id = ?", (committee_id,))
        st = form.get("source_type") or "student_intel"
        if access != "manage" and st != "student_intel":
            raise UserError("Students record evidence as student intel, with a source (who said it and when).", 403)
        tk = form.get("target_kind") or "paragraph"
        target_id = form_int(form.get(f"target_id_{tk}")) or form_int(form.get("target_id"))
        S.add_evidence(w, subject_kind=form.get("subject_kind") or "country", iso3=form.get("iso3"), bloc_id=form_int(form.get("bloc_id")),
                       target_kind=tk, target_id=target_id, tag_code=form.get("tag_code") or "", topic_id=com["topic_id"],
                       position=form.get("position"), strength=form.get("strength") or "moderate",
                       conditional=bool(form.get("conditional")), condition_text=form.get("condition_text") or "",
                       source=form.get("source") or "", source_type=st, stated_on=form.get("stated_on") or "",
                       summary=form.get("summary") or "", channel=S.committee_channel(committee_id))
    back = form.get("back") or f"/mun/committees/{committee_id}/evidence"
    if not back.startswith("/"):
        back = "/"
    return redirect(back, "Evidence recorded. Predictions now include it.")


@router.post("/evidence/{evidence_id}/delete")
def evidence_delete(request: Request, evidence_id: int, s=Depends(require_any), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        e = one(w.conn, "SELECT * FROM evidence WHERE id = ?", (evidence_id,))
        if not e:
            raise UserError("Not found.", 404)
        cid = form_int(form.get("committee_id"))
        access = _access(w.conn, request, cid)
        if access != "manage" and e["recorded_by"] != request.state.actor.label:
            raise UserError("You can only remove evidence you recorded.", 403)
        w.soft_delete("evidence", evidence_id, S.committee_channel(cid))
    return redirect(f"/mun/committees/{cid}/evidence", "Evidence removed (undo is available).")


# ---------- predictions ----------

def _computed_isos(conn, committee_id: int) -> set[str]:
    return {r["iso3"] for r in rows(conn, "SELECT d.iso3 FROM delegation d WHERE d.committee_id = ? AND d.deleted_at IS NULL AND NOT EXISTS "
                                          "(SELECT 1 FROM delegation_member dm WHERE dm.delegation_id = d.id AND dm.deleted_at IS NULL)",
                                    (committee_id,))}


@router.get("/predict/{kind}/{tid}")
def prediction_page(request: Request, kind: str, tid: int, runs: int = P.DEFAULT_RUNS, s=Depends(require_any)):
    runs = max(500, min(int(runs), 20000))
    with request.app.state.db.read() as conn:
        cid = _committee_of_target(conn, kind, tid)
        access = _access(conn, request, cid)
        pred = P.run_prediction(conn, kind, tid, runs=runs)
        stypes = {r["code"]: r for r in rows(conn, "SELECT * FROM source_type")}
        computed = _computed_isos(conn, cid)
        snapshots = rows(conn, "SELECT * FROM prediction WHERE target_kind = ? AND target_id = ? ORDER BY id DESC LIMIT 10", (kind, tid))
        mine = _my_delegation(conn, request.state.actor, cid)
        dels = rows(conn, "SELECT d.id, d.iso3, c.name FROM delegation d JOIN country c ON c.iso3 = d.iso3 WHERE d.committee_id = ? "
                          "AND d.deleted_at IS NULL ORDER BY c.name", (cid,))
        flags = {r["iso3"]: r["flag_svg"] for r in rows(conn, "SELECT iso3, flag_svg FROM country WHERE flag_svg != ''")}
        ev_index = {e["id"]: e for e in rows(conn, "SELECT id, source, stated_on, recorded_on, summary FROM evidence WHERE deleted_at IS NULL")}
        actual = rows(conn, "SELECT * FROM actual_vote WHERE target_kind = ? AND target_id = ?", (kind, tid))
    swing = pred["result"].swing[:15]
    return render(request, "mun/prediction.html", {"title": f"Prediction: {pred['target']['label']}", "pred": pred, "access": access,
                                                   "stypes": stypes, "computed": computed, "snapshots": snapshots, "mine": mine,
                                                   "dels": dels, "swing": swing, "flags": flags, "ev_index": ev_index, "kind": kind,
                                                   "tid": tid, "runs": runs, "committee_id": cid, "has_actual": bool(actual)})


@router.post("/predict/{kind}/{tid}/snapshot")
def prediction_snapshot(request: Request, kind: str, tid: int, s=Depends(require_any)):
    with request.app.state.db.write(request.state.actor) as w:
        cid = _committee_of_target(w.conn, kind, tid)
        _access(w.conn, request, cid)
        pred = P.run_prediction(w.conn, kind, tid)
        pid = P.store_prediction(w, pred)
    return redirect(f"/mun/predict/{kind}/{tid}", f"Prediction saved as snapshot #{pid} (seed {pred['seed']}). "
                                                  "It will be compared with the actual vote for calibration.")


@router.get("/predictions/{pid}.csv")
def prediction_csv(request: Request, pid: int, s=Depends(require_any)):
    with request.app.state.db.read() as conn:
        p = one(conn, "SELECT * FROM prediction WHERE id = ?", (pid,))
        if not p:
            raise UserError("Not found.", 404)
        _access(conn, request, p["committee_id"])
        data = rows(conn, "SELECT pc.iso3, c.name, pc.p_yes, pc.p_abstain, pc.p_no, pc.mu, pc.sigma, pc.unknown FROM prediction_country pc "
                          "JOIN country c ON c.iso3 = pc.iso3 WHERE pc.prediction_id = ? ORDER BY pc.iso3", (pid,))
    return Response(csv_bytes(data), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="prediction-{pid}.csv"'})


@router.get("/predictions/{pid}/replay")
def prediction_replay(request: Request, pid: int, s=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        p = one(conn, "SELECT committee_id FROM prediction WHERE id = ?", (pid,))
        if not p:
            raise UserError("Not found.", 404)
        _access(conn, request, p["committee_id"], "manage")
        stored, res, h = P.replay(conn, pid)
    same = res.p_pass == stored["p_pass"] and h == stored["inputs_hash"]
    body = (f"<p>Stored P(pass) {stored['p_pass']:.4f}; replayed {res.p_pass:.4f} with seed {stored['seed']}. "
            f"Input hash {'matches' if h == stored['inputs_hash'] else 'DIFFERS'}.</p>"
            f"<p class='{'ok-box' if same else 'error-box'}'>{'Reproduced exactly.' if same else 'Not reproduced: report this as a bug.'}</p>")
    return render(request, "page.html", {"title": f"Replay of snapshot #{pid}", "body": body})


@router.post("/predict/{kind}/{tid}/tasks")
def prediction_tasks(request: Request, kind: str, tid: int, s=Depends(require_any), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        cid = _committee_of_target(w.conn, kind, tid)
        access = _access(w.conn, request, cid)
        did = form_int(form.get("delegation_id"))
        if access != "manage":
            mine = _my_delegation(w.conn, request.state.actor, cid)
            if not mine:
                raise UserError("Only delegation members can create tasks.", 403)
            did = mine["id"]
        if not did:
            raise UserError("Choose which delegation the tasks are for.")
        pred = P.run_prediction(w.conn, kind, tid)
        t = pred["target"]
        ids = S.create_tasks_from_swing(w, did, pred["result"].swing, t["amendment_id"], t["paragraph_id"],
                                        top_n=max(1, min(10, form_int(form.get("top_n"), 3))))
    return redirect(f"/mun/committees/{cid}#tasks", f"Created {len(ids)} lobbying task(s) from the swing list.")


@router.get("/paragraphs/{paragraph_id}/compare")
def compare_page(request: Request, paragraph_id: int, s=Depends(require_any)):
    with request.app.state.db.read() as conn:
        cid = _committee_of_paragraph(conn, paragraph_id)
        _access(conn, request, cid)
        cmp = P.compare(conn, paragraph_id)
        amends = {a["id"]: a for a in rows(conn, "SELECT a.*, c.name AS sponsor FROM amendment a LEFT JOIN delegation d ON d.id = a.sponsor_delegation_id "
                                                 "LEFT JOIN country c ON c.iso3 = d.iso3 WHERE a.paragraph_id = ? "
                                                 "AND a.submitted_at IS NOT NULL", (paragraph_id,))}
        p = S.paragraph(conn, paragraph_id)
    return render(request, "mun/compare.html", {"title": f"Amendments to paragraph {p['position']}", "cmp": cmp, "amends": amends,
                                                "p": p})


# ---------- tasks ----------

@router.post("/tasks/{task_id}")
def task_update(request: Request, task_id: int, s=Depends(require_any), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        t = one(w.conn, "SELECT t.*, d.committee_id FROM task t JOIN delegation d ON d.id = t.delegation_id WHERE t.id = ?", (task_id,))
        if not t:
            raise UserError("That task doesn't exist.", 404)
        access = _access(w.conn, request, t["committee_id"])
        if access != "manage":
            mine = _my_delegation(w.conn, request.state.actor, t["committee_id"])
            if not mine or mine["id"] != t["delegation_id"]:
                raise UserError("That task belongs to another delegation.", 403)
        changes = {k: form.get(k) for k in ("status", "talking_points", "notes") if form.get(k) is not None}
        if form.get("assignee_student_id") is not None:
            changes["assignee_student_id"] = form_int(form.get("assignee_student_id"))
        S.update_task(w, task_id, **changes)
    back = form.get("back") or f"/mun/committees/{t['committee_id']}#tasks"
    return redirect(back if back.startswith("/") else "/", "Task updated.")


# ---------- actual votes and calibration ----------

@router.get("/votes/{kind}/{tid}")
def votes_form(request: Request, kind: str, tid: int, s=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        cid = _committee_of_target(conn, kind, tid)
        _access(conn, request, cid, "manage")
        target = P.describe_target(conn, kind, tid)
        dels = rows(conn, "SELECT d.iso3, c.name FROM delegation d JOIN country c ON c.iso3 = d.iso3 WHERE d.committee_id = ? "
                          "AND d.deleted_at IS NULL ORDER BY c.name", (cid,))
        existing = {r["iso3"]: r["vote"] for r in rows(conn, "SELECT iso3, vote FROM actual_vote WHERE target_kind = ? AND target_id = ? "
                                                             "AND context = 'conference'", (kind, tid))}
        snaps = rows(conn, "SELECT id, created_at, p_pass FROM prediction WHERE target_kind = ? AND target_id = ? ORDER BY id DESC", (kind, tid))
        outcome = None
        if existing:
            _, rule = P.committee_rule(conn, cid)
            from app.engine.rules import tally
            outcome = tally(rule, existing, len(dels))
    return render(request, "mun/votes.html", {"title": f"Record the actual vote: {target['label']}", "target": target, "dels": dels,
                                              "existing": existing, "snaps": snaps, "kind": kind, "tid": tid, "outcome": outcome,
                                              "committee_id": cid})


@router.post("/votes/{kind}/{tid}")
def votes_save(request: Request, kind: str, tid: int, s=Depends(require_staff), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        cid = _committee_of_target(w.conn, kind, tid)
        _access(w.conn, request, cid, "manage")
        isos = [r["iso3"] for r in rows(w.conn, "SELECT iso3 FROM delegation WHERE committee_id = ? AND deleted_at IS NULL", (cid,))]
        votes = {iso: form.get(f"v_{iso}") or "" for iso in isos}
        n = S.record_actual_votes(w, kind, tid, votes, "conference", form_int(form.get("prediction_id")))
    return redirect(f"/mun/votes/{kind}/{tid}", f"Recorded {n} vote(s). They now count in the calibration report.")


@router.get("/calibration")
def calibration(request: Request, context: str = "conference", s=Depends(require_staff)):
    if context not in ("conference", "real_un"):
        context = "conference"
    with request.app.state.db.read() as conn:
        rep = S.calibration_report(conn, context)
        n_targets = scalar(conn, "SELECT COUNT(DISTINCT target_kind || target_id) FROM actual_vote WHERE context = ?", (context,))
    return render(request, "mun/calibration.html", {"title": "Calibration report", "rep": rep, "context": context,
                                                    "n_targets": n_targets})
