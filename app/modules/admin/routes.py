"""Coordinator admin: reference tables, CSV, history/undo, datasets, backups, model versions."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import Response

from app.db import columns, history, one, pk_of, restore_from_event, rows, scalar, undo_last
from app.errors import UserError
from app.exports import csv_bytes, read_csv
from app.modules.admin.tables import BY_NAME, EXPORT_ONLY, REFERENCE, SECRET_COLUMNS, Col, Table
from app.web.auth import require_coordinator, revoke_devices
from app.web.http import redirect, form_data
from app.web.safety import safe_back, svg_is_safe
from app.web.templating import render

router = APIRouter(prefix="/admin", dependencies=[Depends(require_coordinator)])


def _table(name: str) -> Table:
    t = BY_NAME.get(name)
    if not t:
        raise UserError("There is no admin table with that name.", 404)
    return t


def _ref_options(conn, col: Col) -> list[tuple]:
    table, key, label = col.ref.split(":")
    extra = ", name" if label != "name" and "name" in columns(conn, table) else ""
    out = []
    for r in rows(conn, f"SELECT {key} AS k, {label} AS l{extra} FROM {table} WHERE deleted_at IS NULL ORDER BY {label}"):
        text = r["l"] if not extra else f"{r['l']} ({r['name']})"
        out.append((r["k"], text))
    return out


def parse_value(col: Col, raw, conn=None):
    """Form/CSV text -> stored value, with plain-English errors."""
    if raw is None:
        raw = ""
    raw = str(raw).strip() if col.type not in ("textarea", "json") else str(raw)
    if col.type == "bool":
        return 1 if str(raw).lower() in ("1", "true", "yes", "on", "y") else 0
    if raw == "":
        if col.required:
            raise UserError(f"{col.label} is required.")
        if col.type in ("int", "real"):
            return 0
        return None if col.type == "ref" else ""
    if col.type == "int":
        try:
            return int(float(raw))
        except ValueError:
            raise UserError(f"{col.label} must be a whole number (got “{raw}”).")
    if col.type == "real":
        try:
            return float(raw)
        except ValueError:
            raise UserError(f"{col.label} must be a number (got “{raw}”).")
    if col.type == "choice" and raw not in col.choices:
        raise UserError(f"{col.label} must be one of: {', '.join(col.choices)}.")
    if col.type == "ref":
        table, key, _ = col.ref.split(":")
        if conn is not None and not one(conn, f"SELECT 1 FROM {table} WHERE {key} = ?", (raw,)):
            raise UserError(f"{col.label}: “{raw}” doesn't exist.")
        return int(raw) if key == "id" else raw
    if col.name == "iso3":
        if len(raw) != 3 or not raw.isalpha():
            raise UserError("ISO-3 code must be three letters.")
        return raw.upper()
    if col.name == "flag_svg" and not svg_is_safe(raw):
        # Shown on every page without escaping, so only plain SVG shapes are accepted (S-5, D-083).
        raise UserError("Flag markup can only use plain SVG shapes (svg, g, path, rect, circle, polygon…) with colours and "
                        "sizes: no scripts, links, styles or event attributes.")
    return raw


def _values(t: Table, form, conn) -> dict:
    return {c.name: parse_value(c, form.get(c.name), conn) for c in t.cols}


@router.get("")
def admin_home(request: Request):
    db = request.app.state.db
    with db.read() as conn:
        counts = {t.name: scalar(conn, f"SELECT COUNT(*) FROM {t.name} WHERE deleted_at IS NULL") for t in REFERENCE}
        last_events = rows(conn, "SELECT * FROM event_log ORDER BY seq DESC LIMIT 8")
        live = 0
        if "live_session" in [r["name"] for r in rows(conn, "SELECT name FROM sqlite_master WHERE type='table'")]:
            live = scalar(conn, "SELECT COUNT(*) FROM live_session WHERE state != 'closed'")
    from app.backup import last_backup_age_s
    s = request.app.state.settings
    return render(request, "admin/home.html", {"title": "Admin", "tables": REFERENCE, "counts": counts,
                                               "export_only": EXPORT_ONLY, "events": last_events, "live": live,
                                               "backup_age": last_backup_age_s(s, s.dataset)})


@router.get("/t/{name}")
def table_list(request: Request, name: str, q: str = "", show: str = ""):
    t = _table(name)
    db = request.app.state.db
    with db.read() as conn:
        where = "1=1" if show == "deleted" else "deleted_at IS NULL"
        if show == "deleted":
            where = "deleted_at IS NOT NULL"
        params: list = []
        if q:
            text_cols = [c.name for c in t.cols if c.type in ("text", "textarea", "choice")]
            if text_cols:
                where += " AND (" + " OR ".join(f"{c} LIKE ?" for c in text_cols) + ")"
                params += [f"%{q}%"] * len(text_cols)
        data = rows(conn, f"SELECT * FROM {name} WHERE {where} ORDER BY {t.order_by} LIMIT 1000", params)
        refs = {c.name: dict(_ref_options(conn, c)) for c in t.cols if c.type == "ref"}
    return render(request, "admin/table.html", {"title": t.label, "t": t, "data": data, "q": q, "show": show,
                                                "refs": refs, "pk": pk_of(name)})


@router.get("/t/{name}/new")
def table_new(request: Request, name: str):
    t = _table(name)
    with request.app.state.db.read() as conn:
        opts = {c.name: _ref_options(conn, c) for c in t.cols if c.type == "ref"}
    return render(request, "admin/edit.html", {"title": f"Add to {t.label}", "t": t, "row": {}, "opts": opts,
                                               "is_new": True, "events": []})


@router.post("/t/{name}/new")
def table_create(request: Request, name: str, form=Depends(form_data)):
    t = _table(name)
    with request.app.state.db.write(request.state.actor) as w:
        vals = _values(t, form, w.conn)
        if t.natural_key and all(vals.get(k) not in (None, "") for k in t.natural_key):
            clash = one(w.conn, f"SELECT {pk_of(name)} FROM {name} WHERE " + " AND ".join(f"{k} = ?" for k in t.natural_key),
                        [vals[k] for k in t.natural_key])
            if clash:
                raise UserError(f"That {', '.join(t.natural_key)} already exists in {t.label}. Edit the existing row instead.")
        key = w.insert(name, vals)
    return redirect(f"/admin/t/{name}/{key}", f"Added to {t.label}.")


@router.get("/t/{name}/{key}")
def table_edit(request: Request, name: str, key: str):
    t = _table(name)
    with request.app.state.db.read() as conn:
        row = one(conn, f"SELECT * FROM {name} WHERE {pk_of(name)} = ?", (key,))
        if not row:
            raise UserError("That row doesn't exist.", 404)
        opts = {c.name: _ref_options(conn, c) for c in t.cols if c.type == "ref"}
        events = history(conn, name, key)
    return render(request, "admin/edit.html", {"title": f"Edit {t.label}", "t": t, "row": row, "opts": opts,
                                               "is_new": False, "events": events, "key": key})


@router.post("/t/{name}/{key}")
def table_save(request: Request, name: str, key: str, form=Depends(form_data)):
    t = _table(name)
    with request.app.state.db.write(request.state.actor) as w:
        k = int(key) if pk_of(name) == "id" else key
        if not w.get(name, k):
            raise UserError("That row doesn't exist.", 404)
        vals = _values(t, form, w.conn)
        if pk_of(name) in vals:
            vals.pop(pk_of(name))       # the key itself is not editable
        if name == "model_version":
            pass
        w.update(name, k, vals)
    return redirect(f"/admin/t/{name}/{key}", "Saved.")


@router.post("/t/{name}/{key}/delete")
def table_delete(request: Request, name: str, key: str, form=Depends(form_data)):
    t = _table(name)
    if form.get("confirm") != "yes":
        raise UserError("Tick the confirmation box to delete.")
    with request.app.state.db.write(request.state.actor) as w:
        w.soft_delete(name, int(key) if pk_of(name) == "id" else key)
    return redirect(f"/admin/t/{name}", f"Deleted from {t.label}. It can be restored for 30 days (show deleted rows).")


@router.post("/t/{name}/{key}/restore")
def table_restore(request: Request, name: str, key: str):
    _table(name)
    with request.app.state.db.write(request.state.actor) as w:
        w.restore(name, int(key) if pk_of(name) == "id" else key)
    return redirect(f"/admin/t/{name}/{key}", "Restored.")


@router.post("/history/{seq}/restore")
def history_restore(request: Request, seq: int):
    with request.app.state.db.write(request.state.actor) as w:
        ev = one(w.conn, "SELECT entity, entity_id FROM event_log WHERE seq = ?", (seq,))
        if not ev:
            raise UserError("That version doesn't exist.", 404)
        restore_from_event(w, seq)
    back = f"/admin/t/{ev['entity']}/{ev['entity_id']}" if ev["entity"] in BY_NAME else "/admin/log"
    return redirect(back, f"Restored the version from change #{seq}.")


@router.post("/undo")
def undo(request: Request):
    with request.app.state.db.write(request.state.actor) as w:
        res = undo_last(w)
    if not res:
        return redirect("/admin", "Nothing of yours to undo.")
    return redirect(safe_back(request, "/admin"),
                    f"Undid your last change ({len(res['events'])} step(s) on {res['entity']}).")


@router.get("/log")
def event_log(request: Request, entity: str = "", actor: str = "", before: int | None = None):
    sql, params = "SELECT * FROM event_log WHERE 1=1", []
    if entity:
        sql += " AND entity = ?"
        params.append(entity)
    if actor:
        sql += " AND actor_label LIKE ?"
        params.append(f"%{actor}%")
    if before:
        sql += " AND seq < ?"
        params.append(before)
    with request.app.state.db.read() as conn:
        data = rows(conn, sql + " ORDER BY seq DESC LIMIT 200", params)
        entities = [r["entity"] for r in rows(conn, "SELECT DISTINCT entity FROM event_log ORDER BY entity")]
    return render(request, "admin/log.html", {"title": "Change log", "data": data, "entity": entity, "actor": actor,
                                              "entities": entities})


# ---------- CSV ----------

def _csv_response(data: bytes, filename: str) -> Response:
    return Response(data, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/csv/{name}.csv")
def export_csv(request: Request, name: str):
    if name not in BY_NAME and name not in EXPORT_ONLY:
        raise UserError("That table can't be exported.", 404)
    with request.app.state.db.read() as conn:
        cols = [c for c in columns(conn, name) if c not in SECRET_COLUMNS]
        data = rows(conn, f"SELECT {', '.join(cols)} FROM {name} ORDER BY {pk_of(name)}")
    return _csv_response(csv_bytes(data, cols), f"{name}.csv")


@router.post("/import/{name}")
async def import_csv(request: Request, name: str, file: UploadFile = File(...)):
    t = _table(name)
    data = await file.read()
    if not data:
        raise UserError("Choose a CSV file to import.")
    try:
        records = read_csv(data)
    except UnicodeDecodeError:
        raise UserError("That file isn't UTF-8 CSV. In Excel, use Save As → CSV UTF-8.")

    def run():      # database work off the event loop (D-042)
        added = updated = 0
        with request.app.state.db.write(request.state.actor) as w:
            for i, rec in enumerate(records, start=2):
                try:
                    vals = {c.name: parse_value(c, rec.get(c.name), w.conn) for c in t.cols if c.name in rec}
                except UserError as e:
                    raise UserError(f"Row {i}: {e.message} Nothing was imported; fix the file and try again.")
                missing = [c.label for c in t.cols if c.required and c.name not in vals]
                if missing:
                    raise UserError(f"The file is missing column(s): {', '.join(missing)}. Nothing was imported.")
                key_cols = t.natural_key or (pk_of(name),)
                existing = None
                if all(vals.get(k) not in (None, "") for k in key_cols):
                    existing = one(w.conn, f"SELECT {pk_of(name)} AS k FROM {name} WHERE " +
                                   " AND ".join(f"{k} = ?" for k in key_cols), [vals[k] for k in key_cols])
                elif rec.get("id"):
                    existing = one(w.conn, f"SELECT id AS k FROM {name} WHERE id = ?", (rec["id"],))
                if existing:
                    vals.pop(pk_of(name), None)
                    if w.update(name, existing["k"], vals):
                        updated += 1
                else:
                    w.insert(name, vals)
                    added += 1
        return added, updated
    added, updated = await asyncio.to_thread(run)
    return redirect(f"/admin/t/{name}", f"Imported {len(records)} row(s): {added} added, {updated} changed.")


# ---------- datasets, backups ----------

@router.get("/data")
def data_page(request: Request):
    from app.backup import last_backup_age_s
    s = request.app.state.settings
    with request.app.state.db.read() as conn:
        live = 0
        if one(conn, "SELECT 1 FROM sqlite_master WHERE name = 'live_session'"):
            live = scalar(conn, "SELECT COUNT(*) FROM live_session WHERE state != 'closed'")
    files = sorted(s.backup_dir.glob("*.db"), reverse=True)[:20] if s.backup_dir.exists() else []
    return render(request, "admin/data.html", {"title": "Data, demo mode and backups", "live": live, "files": files,
                                               "backup_age": last_backup_age_s(s, s.dataset)})


@router.post("/data/switch")
def switch_dataset(request: Request, form=Depends(form_data)):
    from app.datasets import open_dataset
    from app.web.auth import SESSION_COOKIE, create_session
    target = form.get("dataset")
    s = request.app.state.settings
    if target not in ("real", "demo") or target == s.dataset:
        raise UserError("Choose the other dataset to switch to.")
    with request.app.state.db.read() as conn:
        if one(conn, "SELECT 1 FROM sqlite_master WHERE name = 'live_session'") and \
                scalar(conn, "SELECT COUNT(*) FROM live_session WHERE state != 'closed'"):
            raise UserError("Close every live session before switching datasets. Real and demo data are never open together.")
        revoke_devices(conn, "1=1")
        conn.commit()
    s.set("dataset", target)
    request.app.state.db.dispose()
    request.app.state.db = open_dataset(s, target, request.app.state.hub)
    with request.app.state.db.read() as conn:
        token = create_session(conn, "coordinator")
        conn.commit()
    resp = redirect("/admin/data", f"Switched to the {target} dataset. Everyone else has been signed out.")
    resp.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax")
    return resp


@router.post("/data/reset-demo")
def reset_demo(request: Request, form=Depends(form_data)):
    s = request.app.state.settings
    if form.get("confirm") != "yes":
        raise UserError("Tick the confirmation box to reset the demo data.")
    if s.dataset != "demo":
        raise UserError("Reset only works while the demo dataset is open.")
    from app.datasets import open_dataset
    from app.web.auth import SESSION_COOKIE, create_session
    request.app.state.db.dispose()
    path = s.db_path("demo")
    for suffix in ("", "-wal", "-shm"):
        p = path.with_name(path.name + suffix)
        p.unlink(missing_ok=True)
    request.app.state.db = open_dataset(s, "demo", request.app.state.hub)
    with request.app.state.db.read() as conn:
        token = create_session(conn, "coordinator")
        conn.commit()
    resp = redirect("/admin/data", "Demo data reset to a fresh fake dataset.")
    resp.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax")
    return resp


@router.post("/data/backup-now")
def backup_now(request: Request):
    from app.backup import nightly_backup
    p = nightly_backup(request.app.state.settings)
    return redirect("/admin/data", f"Backup saved: {p.name}")


@router.get("/data/download")
def download_backup(request: Request):
    from app.backup import make_download, stamp
    s = request.app.state.settings
    data = make_download(s, s.dataset)
    return Response(data, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="soc-{s.dataset}-backup-{stamp()}.zip"'})


@router.post("/data/restore")
async def restore_backup(request: Request, file: UploadFile = File(...)):
    from app.backup import check_backup, restore
    from app.datasets import open_dataset
    from app.web.auth import SESSION_COOKIE, create_session
    form = await request.form()
    if form.get("confirm") != "yes":
        raise UserError("Tick the confirmation box: restoring replaces the current data (a copy is kept first).")
    s = request.app.state.settings
    data = await file.read()
    await asyncio.to_thread(check_backup, data)      # refuse a bad file before touching the open data
    request.app.state.db.dispose()       # close pooled connections before the file is replaced
    try:
        manifest = await asyncio.to_thread(restore, s, s.dataset, data)
    finally:
        request.app.state.db = open_dataset(s, s.dataset, request.app.state.hub)
    with request.app.state.db.read() as conn:
        token = create_session(conn, "coordinator")
        conn.commit()
    resp = redirect("/admin/data", f"Restored the backup from {manifest.get('created')} "
                                   f"({manifest.get('counts', {}).get('student', '?')} students). The previous data was kept as a backup file.")
    resp.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax")
    return resp


# ---------- model versions ----------

@router.get("/model")
def model_versions(request: Request):
    with request.app.state.db.read() as conn:
        data = rows(conn, "SELECT * FROM model_version ORDER BY id DESC")
    return render(request, "admin/model.html", {"title": "Prediction model versions", "data": data})


@router.post("/model")
def model_create(request: Request, form=Depends(form_data)):
    from app.engine.model import ModelParams
    from app.util import now_iso
    name = (form.get("name") or "").strip()
    if not name:
        raise UserError("Give the model version a name.")
    try:
        params = json.loads(form.get("params") or "{}")
        ModelParams.from_dict(params)
    except (ValueError, TypeError) as e:
        raise UserError(f"The parameters aren't valid JSON for the model: {e}")
    with request.app.state.db.write(request.state.actor) as w:
        if one(w.conn, "SELECT 1 FROM model_version WHERE name = ?", (name,)):
            raise UserError("A model version with that name exists. Versions are never edited; choose a new name.")
        w.insert("model_version", {"name": name, "params_json": json.dumps(params), "active": 0,
                                   "notes": form.get("notes") or "", "created_at": now_iso()})
    return redirect("/admin/model", "Model version saved. Activate it to use it for new predictions.")


@router.post("/model/{mid}/activate")
def model_activate(request: Request, mid: int):
    with request.app.state.db.write(request.state.actor) as w:
        for r in rows(w.conn, "SELECT id FROM model_version WHERE active = 1"):
            w.update("model_version", r["id"], {"active": 0})
        w.update("model_version", mid, {"active": 1})
    return redirect("/admin/model", "Activated. Earlier predictions keep the version they were made with.")
