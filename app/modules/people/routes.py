"""People: classes, rosters, staff, pathways (Layer 3), and student join (D-003)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.db import one, rows, scalar
from app.errors import UserError
from app.util import display_name, hash_passphrase, new_code, now_iso, today_iso
from app.web.auth import can_run_class, require_coordinator, require_staff, staff_class_ids, revoke_devices
from app.web.http import form_int, redirect, form_data
from app.web.templating import render

router = APIRouter(prefix="/people")
NAME_LIMIT = 40


def _class_or_404(conn, class_id: int) -> dict:
    c = one(conn, "SELECT * FROM class WHERE id = ? AND deleted_at IS NULL", (class_id,))
    if not c:
        raise UserError("That class doesn't exist.", 404)
    return c


def _check_class(conn, request, class_id: int) -> dict:
    c = _class_or_404(conn, class_id)
    if not can_run_class(conn, request.state.actor, class_id):
        raise UserError("You aren't assigned to that class. Ask the coordinator to add you.", 403)
    return c


def clean_name(first: str, initial: str = "") -> tuple[str, str]:
    first = " ".join((first or "").split())
    initial = (initial or "").strip().rstrip(".")[:1].upper()
    if not first:
        raise UserError("Enter a first name.")
    if len(first) > NAME_LIMIT:
        raise UserError(f"First names are limited to {NAME_LIMIT} characters.")
    if " " in first.strip():
        # Privacy (spec §8.1): first name only. "Sam Lee" -> first name Sam, initial L.
        parts = first.split()
        first, initial = parts[0], initial or parts[-1][:1].upper()
    return first, initial


def needs_initial(conn, class_id: int, first: str, exclude_id: int | None = None) -> bool:
    return bool(scalar(conn, "SELECT COUNT(*) FROM student WHERE class_id = ? AND first_name = ? AND deleted_at IS NULL "
                             "AND id IS NOT ?", (class_id, first, exclude_id)))


@router.get("")
def people_home(request: Request, s=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        ids = staff_class_ids(conn, s.actor)
        classes = rows(conn, "SELECT c.*, (SELECT COUNT(*) FROM student st WHERE st.class_id = c.id AND st.deleted_at IS NULL "
                             "AND st.active = 1) AS n FROM class c WHERE c.deleted_at IS NULL ORDER BY c.archived_at IS NOT NULL, c.year DESC, c.name")
        if ids is not None:
            classes = [c for c in classes if c["id"] in ids]
    return render(request, "people/home.html", {"title": "People", "classes": classes})


@router.get("/classes")
def classes_redirect(request: Request, s=Depends(require_staff)):
    return redirect("/people")


def create_class(w, name: str, year: int | None) -> tuple[int, str]:
    name = (name or "").strip()
    if not name:
        raise UserError("Give the class a name, e.g. “Year 9 Model UN”.")
    code = new_code()
    while one(w.conn, "SELECT 1 FROM class WHERE code = ?", (code,)):
        code = new_code()
    cid = w.insert("class", {"name": name[:80], "year": year or int(today_iso()[:4]), "code": code, "code_set_at": now_iso()})
    return cid, code


def add_students(w, class_id: int, lines: list[str]) -> str:
    """One name per line: "Sam" or "Sam L". Only first names and an initial are kept (privacy rule 1)."""
    lines = [ln for ln in lines if ln.strip()]
    if not lines:
        raise UserError("Type at least one first name (one per line).")
    added = []
    for ln in lines:
        parts = ln.split()
        first, initial = clean_name(parts[0], parts[1] if len(parts) > 1 else "")
        sid = w.insert("student", {"class_id": class_id, "first_name": first, "last_initial": initial}, channel=f"class:{class_id}")
        added.append((sid, first, initial))
    from app.modules.people.codes import assign_missing
    assign_missing(w.conn)
    # If two students now share a first name and either lacks an initial, say so.
    clashes = [f for _, f, i in added if needs_initial(w.conn, class_id, f) and not i]
    msg = f"Added {len(added)} student(s)."
    if clashes:
        msg += f" Two or more students are called {', '.join(sorted(set(clashes)))}: add a last initial so they can tell their names apart."
    return msg


def roster_lines_from_csv(data: bytes) -> list[str]:
    """A roster CSV with a first_name column (and optionally last_initial), or a single name column.
    Any other column (surname, email, date of birth) is ignored and never stored."""
    from app.exports import read_csv
    try:
        recs = read_csv(data)
    except UnicodeDecodeError:
        raise UserError("That file isn't UTF-8 CSV. In Excel, use Save As → CSV UTF-8.")
    if not recs:
        raise UserError("The file has no rows.")
    cols = {k.strip().lower().replace(" ", "_"): k for k in recs[0]}
    if "first_name" in cols:
        return [f"{r[cols['first_name']]} {(r.get(cols['last_initial'], '') if 'last_initial' in cols else '')}".strip() for r in recs]
    if "name" in cols:
        return [r[cols["name"]] for r in recs]
    raise UserError("The file needs a first_name column (and optionally last_initial), or a name column.")


@router.post("/classes")
def class_create(request: Request, s=Depends(require_coordinator), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        cid, code = create_class(w, form.get("name"), form_int(form.get("year")))
    return redirect(f"/people/classes/{cid}", "Class created. Add the students: each gets their own sign-in code.")


@router.get("/classes/{class_id}")
def class_view(request: Request, class_id: int, s=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        c = _check_class(conn, request, class_id)
        students = rows(conn, "SELECT st.*, (SELECT COUNT(*) FROM device_session d WHERE d.student_id = st.id AND d.revoked_at IS NULL) AS devices, "
                              "(SELECT MAX(last_seen_at) FROM device_session d WHERE d.student_id = st.id AND d.revoked_at IS NULL) AS last_seen "
                              "FROM student st WHERE st.class_id = ? AND st.deleted_at IS NULL ORDER BY st.active DESC, st.first_name, st.last_initial",
                        (class_id,))
        staff = rows(conn, "SELECT sf.name FROM staff_class sc JOIN staff sf ON sf.id = sc.staff_id WHERE sc.class_id = ? "
                           "AND sc.deleted_at IS NULL AND sf.deleted_at IS NULL", (class_id,))
        milestones = rows(conn, "SELECT * FROM pathway_milestone WHERE deleted_at IS NULL ORDER BY position")
        achieved = {}
        for r in rows(conn, "SELECT sm.student_id, COUNT(*) AS n FROM student_milestone sm JOIN student st ON st.id = sm.student_id "
                            "WHERE st.class_id = ? AND sm.deleted_at IS NULL GROUP BY sm.student_id", (class_id,)):
            achieved[r["student_id"]] = r["n"]
    connected = sum(1 for st in students if st["devices"])
    from app.modules.people.codes import shown
    for st in students:
        st["code"] = shown(st["login_code"])
    return render(request, "people/class.html", {"title": c["name"], "c": c, "students": students,
                                                 "staff": staff, "connected": connected, "achieved": achieved,
                                                 "milestone_count": len(milestones),
                                                 "cap": request.app.state.settings.get("max_live_students", 25)})


@router.post("/classes/{class_id}/students")
def students_add(request: Request, class_id: int, s=Depends(require_staff), form=Depends(form_data)):
    """Add one name per line: "Sam" or "Sam L". Only first names and an initial are kept."""
    with request.app.state.db.write(request.state.actor) as w:
        _check_class(w.conn, request, class_id)
        msg = add_students(w, class_id, (form.get("names") or "").splitlines())
    return redirect(f"/people/classes/{class_id}", msg)


@router.post("/students/{student_id}")
def student_edit(request: Request, student_id: int, s=Depends(require_staff), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        st = one(w.conn, "SELECT * FROM student WHERE id = ?", (student_id,))
        if not st:
            raise UserError("That student doesn't exist.", 404)
        _check_class(w.conn, request, st["class_id"])
        action = form.get("action")
        ch = f"class:{st['class_id']}"
        if action == "rename":
            first, initial = clean_name(form.get("first_name"), form.get("last_initial"))
            w.update("student", student_id, {"first_name": first, "last_initial": initial}, ch)
            msg = "Name updated."
        elif action == "deactivate":
            w.update("student", student_id, {"active": 0}, ch)
            revoke_devices(w.conn, "student_id = ?", (student_id,))
            msg = "Student marked as left. Their device was signed out."
        elif action == "activate":
            w.update("student", student_id, {"active": 1}, ch)
            msg = "Student is active again."
        elif action == "delete":
            if form.get("confirm") != "yes":
                raise UserError("Tick the confirmation box to delete.")
            w.soft_delete("student", student_id, ch)
            revoke_devices(w.conn, "student_id = ?", (student_id,))
            msg = "Student deleted (restorable for 30 days)."
        elif action == "erase":
            if not request.state.actor.is_coordinator:
                raise UserError("Only the coordinator can erase a student's records.", 403)
            if form.get("confirm") != "yes":
                raise UserError("Tick the confirmation box to erase.")
            from app.retention import erase_student
            erase_student(w, student_id)
            msg = "Student erased: their name, own writing and devices are gone; their scores stay as \"Erased\"."
        elif action == "release":
            n = revoke_devices(w.conn, "student_id = ?", (student_id,))
            w.log("student", student_id, "sign_out", None, {"devices_signed_out": n}, ch)
            msg = f"Signed out of {n} laptop(s)."
        elif action == "new_code":
            from app.modules.people.codes import shown, unique
            code = unique(w.conn)
            w.conn.execute("UPDATE student SET login_code = ? WHERE id = ?", (code, student_id))
            n = revoke_devices(w.conn, "student_id = ?", (student_id,))
            w.log("student", student_id, "new_code", None, {"devices_signed_out": n}, ch)
            msg = f"New code for {st['first_name']}: {shown(code)}. The old code no longer works. Print a new card from the class page."
        else:
            raise UserError("Unknown action.")
    return redirect(f"/people/classes/{st['class_id']}", msg)


@router.post("/classes/{class_id}")
def class_edit(request: Request, class_id: int, s=Depends(require_staff), form=Depends(form_data)):
    action = form.get("action")
    with request.app.state.db.write(request.state.actor) as w:
        c = _check_class(w.conn, request, class_id)
        if action == "rotate_code":
            code = new_code()
            while one(w.conn, "SELECT 1 FROM class WHERE code = ?", (code,)):
                code = new_code()
            w.update("class", class_id, {"code": code, "code_set_at": now_iso()}, f"class:{class_id}")
            msg = f"New class code: {code}. Students already joined stay signed in; new joins need the new code."
        elif action == "rename":
            name = (form.get("name") or "").strip()
            if not name:
                raise UserError("Enter a class name.")
            w.update("class", class_id, {"name": name})
            msg = "Class renamed."
        elif action == "archive":
            if not request.state.actor.is_coordinator:
                raise UserError("Only the coordinator can archive a class.", 403)
            w.update("class", class_id, {"archived_at": now_iso(), "active": 0})
            revoke_devices(w.conn, "class_id = ?", (class_id,))
            msg = "Class archived (end of year). Students are signed out; records are kept read-only."
        elif action == "unarchive":
            if not request.state.actor.is_coordinator:
                raise UserError("Only the coordinator can do that.", 403)
            w.update("class", class_id, {"archived_at": None, "active": 1})
            msg = "Class is active again."
        else:
            raise UserError("Unknown action.")
    return redirect(f"/people/classes/{class_id}", msg)


# ---------- sign-in cards and poster (printable; each card carries one student's own code, D-079) ----------

def _bare(base: str) -> str:
    """The address as students type it: without http://."""
    return base.split("://", 1)[-1]


@router.get("/classes/{class_id}/join-cards")
def join_cards(request: Request, class_id: int, s=Depends(require_staff)):
    from app.modules.people.codes import shown
    from app.web.net import student_base_url
    with request.app.state.db.read() as conn:
        c = _check_class(conn, request, class_id)
        students = rows(conn, "SELECT id, first_name, last_initial, login_code FROM student WHERE class_id = ? AND active = 1 "
                              "AND deleted_at IS NULL ORDER BY first_name, last_initial", (class_id,))
    for st in students:
        st["code"] = shown(st["login_code"])
        st["name"] = display_name(st["first_name"], st["last_initial"])
    base = student_base_url(request)
    return render(request, "people/join_cards.html", {"title": f"Sign-in cards: {c['name']}", "c": c, "base": base,
                                                      "addr": _bare(base), "students": students})


@router.get("/classes/{class_id}/poster")
def join_poster(request: Request, class_id: int, s=Depends(require_staff)):
    from app.web.net import student_base_url
    with request.app.state.db.read() as conn:
        c = _check_class(conn, request, class_id)
    base = student_base_url(request)
    return render(request, "people/join_poster.html", {"title": f"Sign in: {c['name']}", "c": c, "addr": _bare(base)})


# ---------- pathway ----------

@router.get("/students/{student_id}")
def student_view(request: Request, student_id: int, s=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        st = one(conn, "SELECT st.*, c.name AS class_name FROM student st JOIN class c ON c.id = st.class_id WHERE st.id = ?", (student_id,))
        if not st:
            raise UserError("That student doesn't exist.", 404)
        _check_class(conn, request, st["class_id"])
        from app.modules.people.pathway import pathway
        path = pathway(conn, student_id)
        delegations = rows(conn, "SELECT d.iso3, c.name AS country, cm.name AS committee, dm.role FROM delegation_member dm "
                                 "JOIN delegation d ON d.id = dm.delegation_id JOIN country c ON c.iso3 = d.iso3 "
                                 "JOIN committee cm ON cm.id = d.committee_id WHERE dm.student_id = ? AND dm.deleted_at IS NULL", (student_id,))
    return render(request, "people/student.html", {"title": display_name(st["first_name"], st["last_initial"]), "st": st,
                                                   "path": path, "delegations": delegations})


@router.post("/students/{student_id}/milestones")
def milestone_record(request: Request, student_id: int, s=Depends(require_staff), form=Depends(form_data)):
    mid = form_int(form.get("milestone_id"))
    with request.app.state.db.write(request.state.actor) as w:
        st = one(w.conn, "SELECT * FROM student WHERE id = ?", (student_id,))
        if not st:
            raise UserError("That student doesn't exist.", 404)
        _check_class(w.conn, request, st["class_id"])
        if not one(w.conn, "SELECT 1 FROM pathway_milestone WHERE id = ?", (mid,)):
            raise UserError("Choose a milestone.")
        existing = one(w.conn, "SELECT * FROM student_milestone WHERE student_id = ? AND milestone_id = ?", (student_id, mid))
        vals = {"achieved_on": form.get("achieved_on") or today_iso(), "evidence_note": (form.get("note") or "")[:500],
                "recorded_by": w.actor.label, "deleted_at": None}
        if existing:
            w.update("student_milestone", existing["id"], vals)
        else:
            w.insert("student_milestone", {"student_id": student_id, "milestone_id": mid, **vals})
    return redirect(f"/people/students/{student_id}", "Milestone recorded.")


# ---------- staff ----------

@router.get("/staff")
def staff_list(request: Request, s=Depends(require_coordinator)):
    with request.app.state.db.read() as conn:
        staff = rows(conn, "SELECT * FROM staff WHERE deleted_at IS NULL ORDER BY name")
        classes = rows(conn, "SELECT * FROM class WHERE deleted_at IS NULL AND archived_at IS NULL ORDER BY name")
        links = rows(conn, "SELECT * FROM staff_class WHERE deleted_at IS NULL")
    by_staff: dict[int, set] = {}
    for l in links:
        by_staff.setdefault(l["staff_id"], set()).add(l["class_id"])
    return render(request, "people/staff.html", {"title": "Staff", "staff": staff, "classes": classes, "by_staff": by_staff})


@router.post("/staff")
def staff_save(request: Request, s=Depends(require_coordinator), form=Depends(form_data)):
    action = form.get("action", "create")
    with request.app.state.db.write(request.state.actor) as w:
        if action == "create":
            name = (form.get("name") or "").strip()
            pp = form.get("passphrase") or ""
            if not name:
                raise UserError("Enter the staff member's name as students will see it, e.g. “Ms Nguyen”.")
            if len(pp) < 10:
                raise UserError("Give them a passphrase of at least 10 characters. They can't change it themselves yet: tell them in person.")
            sid = w.insert("staff", {"name": name, "pass_hash": hash_passphrase(pp)})
            msg = f"Added {name}."
        else:
            sid = form_int(form.get("staff_id"))
            st = one(w.conn, "SELECT * FROM staff WHERE id = ?", (sid,))
            if not st:
                raise UserError("That staff member doesn't exist.", 404)
            if action == "passphrase":
                pp = form.get("passphrase") or ""
                if len(pp) < 10:
                    raise UserError("Passphrases need at least 10 characters.")
                w.update("staff", sid, {"pass_hash": hash_passphrase(pp)})
                revoke_devices(w.conn, "staff_id = ?", (sid,))
                msg = "Passphrase changed; their other sessions were signed out."
            elif action == "classes":
                wanted = {int(x) for x in form.getlist("class_id")}
                have = {r["class_id"]: r for r in rows(w.conn, "SELECT * FROM staff_class WHERE staff_id = ?", (sid,))}
                for cid in wanted:
                    if cid in have:
                        if have[cid]["deleted_at"]:
                            w.restore("staff_class", have[cid]["id"])
                    else:
                        w.insert("staff_class", {"staff_id": sid, "class_id": cid})
                for cid, r in have.items():
                    if cid not in wanted and not r["deleted_at"]:
                        w.soft_delete("staff_class", r["id"])
                msg = "Classes updated."
            elif action == "deactivate":
                w.update("staff", sid, {"active": 0})
                revoke_devices(w.conn, "staff_id = ?", (sid,))
                msg = "Staff member deactivated and signed out."
            elif action == "activate":
                w.update("staff", sid, {"active": 1})
                msg = "Staff member reactivated."
            else:
                raise UserError("Unknown action.")
    return redirect("/people/staff", msg)
