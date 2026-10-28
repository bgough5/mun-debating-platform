"""Intelligence: data sources and licences, imports, backtests, AI settings, AI estimates, AI practice and coaching."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, File, Request, UploadFile

from app.ai import AIDisabled, get_provider, negotiation_label
from app.db import one, rows, scalar
from app.errors import UserError
from app.modules.intelligence import service as I
from app.util import now_iso
from app.web.auth import committee_access, require_coordinator, require_staff, require_student
from app.web.http import form_data, form_int, redirect
from app.web.templating import render
router = APIRouter()

def _provider(request):
    try:
        return get_provider(request.app.state.settings)
    except AIDisabled as e:
        raise UserError(str(e), 403)
    except RuntimeError as e:
        raise UserError(str(e), 503)

@router.get("/intel")
def intel_home(request: Request, sess=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        sources = rows(conn, "SELECT s.*, (SELECT COUNT(*) FROM un_resolution r WHERE r.source_id = s.id) AS resolutions, "
                             "(SELECT COUNT(*) FROM un_vote v JOIN un_resolution r ON r.id = v.resolution_id WHERE r.source_id = s.id) AS votes "
                             "FROM data_source s WHERE s.deleted_at IS NULL ORDER BY s.synthetic, s.id")
        backtests = rows(conn, "SELECT b.id, b.created_at, b.synthetic, s.name FROM backtest_report b LEFT JOIN data_source s ON s.id = b.source_id "
                               "ORDER BY b.id DESC LIMIT 10")
        topics = rows(conn, "SELECT * FROM topic WHERE deleted_at IS NULL ORDER BY name")
        calls = rows(conn, "SELECT * FROM ai_call ORDER BY id DESC LIMIT 15")
    for s in sources:
        s["can_import"], s["why"] = I.can_import(s)
    ai = request.app.state.settings.get("ai", {})
    try:
        prov = get_provider(request.app.state.settings)
        prov_name, off_device = prov.name, prov.sends_data_off_device
    except (AIDisabled, RuntimeError) as e:
        prov_name, off_device = f"unavailable: {e}", False
    return render(request, "intelligence/home.html", {"title": "Intelligence", "sources": sources, "backtests": backtests,
                                                      "topics": topics, "ai": ai, "prov_name": prov_name, "off_device": off_device,
                                                      "calls": calls})

@router.post("/intel/sources/{source_id}/confirm")
def confirm(request: Request, source_id: int, sess=Depends(require_coordinator), form=Depends(form_data)):
    if form.get("confirm") != "yes":
        raise UserError("Tick the box to confirm you have read the licence and it allows this school's use.")
    with request.app.state.db.write(request.state.actor) as w:
        I.confirm_licence(w, source_id, form.get("licence_text"), form.get("note"))
    return redirect("/intel", "Licence recorded. Import is now allowed for this source.")

@router.post("/intel/sources/{source_id}/import")
async def import_file(request: Request, source_id: int, file: UploadFile = File(...), sess=Depends(require_coordinator)):
    form = await request.form()
    data = await file.read()

    def run():      # database work off the event loop (D-042)
        with request.app.state.db.write(request.state.actor) as w:
            s = I.source(w.conn, source_id)
            if s["synthetic"] and not request.app.state.settings.is_demo:
                raise UserError("Synthetic data can only be loaded into the demo dataset, so it never mixes with real records.")
            return I.import_votes(w, source_id, data, form.get("preset") or "generic", form_int(form.get("topic_id")))
    out = await asyncio.to_thread(run)
    return redirect("/intel", f"Imported {out['votes']} votes on {out['resolutions']} resolutions ({out['skipped']} rows skipped).")

@router.post("/intel/sources/{source_id}/load-synthetic")
def load_synthetic(request: Request, source_id: int, sess=Depends(require_coordinator)):
    from app.config import REPO_ROOT
    if not request.app.state.settings.is_demo:
        raise UserError("Synthetic data can only be loaded into the demo dataset.")
    data = (REPO_ROOT / "tests" / "fixtures" / "synthetic_un_votes.csv").read_bytes()
    with request.app.state.db.write(request.state.actor) as w:
        s = I.source(w.conn, source_id)
        if not s["synthetic"]:
            raise UserError("Only the synthetic source can be filled with test data.")
        topic = scalar(w.conn, "SELECT id FROM topic WHERE code = 'climate2026'")
        out = I.import_votes(w, source_id, data, "generic", topic)
    return redirect("/intel", f"Loaded synthetic test data: {out['resolutions']} resolutions, {out['votes']} votes.")

@router.post("/intel/backtest/{source_id}")
def run_backtest(request: Request, source_id: int, sess=Depends(require_coordinator)):
    with request.app.state.db.read() as conn:
        result = I.backtest(conn, source_id)
    with request.app.state.db.write(request.state.actor) as w:
        bid = I.store_backtest(w, source_id, result)
    return redirect(f"/intel/backtests/{bid}", "Backtest finished.")

@router.get("/intel/backtests/{bid}")
def backtest_view(request: Request, bid: int, sess=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        b = one(conn, "SELECT * FROM backtest_report WHERE id = ?", (bid,))
        if not b:
            raise UserError("Not found.", 404)
    res = json.loads(b["results_json"])
    return render(request, "intelligence/backtest.html", {"title": "Backtest report", "b": b, "r": res})

@router.post("/intel/ai")
def ai_settings(request: Request, sess=Depends(require_coordinator), form=Depends(form_data)):
    s = request.app.state.settings
    ai = dict(s.get("ai", {}))
    provider = form.get("provider") or "fake"
    if provider not in ("fake", "off", "anthropic"):
        raise UserError("Unknown provider.")
    approved = bool(form.get("school_approved"))
    if provider == "anthropic" and not approved:
        raise UserError("A real AI service needs the school's written approval first (spec §8.7). Record the approval reference.")
    if approved and len((form.get("approval_ref") or "").strip()) < 5:
        raise UserError("Record the school's approval reference (who approved it, and when).")
    ai.update(provider=provider, school_approved=approved, approval_ref=(form.get("approval_ref") or "")[:300],
              api_key_env=(form.get("api_key_env") or "ANTHROPIC_API_KEY")[:60])
    s.set("ai", ai)
    return redirect("/intel", "AI settings saved.")

@router.post("/intel/ai/estimate")
def ai_estimate(request: Request, sess=Depends(require_staff), form=Depends(form_data)):
    committee_id = form_int(form.get("committee_id"))
    provider = _provider(request)
    with request.app.state.db.write(request.state.actor) as w:
        if committee_access(w.conn, request.state.actor, committee_id) != "manage":
            raise UserError("You don't have access to that committee.", 403)
        out = I.ai_suggest_position(w, provider, committee_id, (form.get("iso3") or "").upper(), form_int(form.get("paragraph_id")))
    msg = ("AI estimate stored, labelled “AI estimate — verify”, with its sources." if out["stored_as"] == "estimate" else
           "The AI couldn't cite a source, so this was stored as unknown: it does not change the prediction.")
    return redirect(f"/mun/committees/{committee_id}/evidence?iso3={form.get('iso3', '')}", msg)

# ---------- students: practice against an AI delegation (S-7) ----------
def _archetype_lines(conn, iso3: str) -> dict:
    top = one(conn, "SELECT a.id FROM country_archetype ca JOIN archetype a ON a.id = ca.archetype_id WHERE ca.iso3 = ? "
                    "AND ca.deleted_at IS NULL ORDER BY ca.weight DESC, ca.id LIMIT 1", (iso3,))
    if not top:
        return {}
    return {r["stance"]: r["line"] for r in rows(conn, "SELECT stance, line FROM archetype_line WHERE archetype_id = ?", (top["id"],))}

@router.get("/me/ai-practice")
def ai_practice_home(request: Request, sess=Depends(require_student)):
    with request.app.state.db.read() as conn:
        paras = rows(conn, "SELECT p.id, p.position, r.title, cm.id AS committee_id, cm.name AS committee FROM paragraph p "
                           "JOIN resolution r ON r.id = p.resolution_id JOIN committee cm ON cm.id = r.committee_id "
                           "WHERE cm.class_id = ? AND p.kind = 'operative' AND p.deleted_at IS NULL ORDER BY cm.id, p.position", (sess.actor.class_id,))
        countries = rows(conn, "SELECT DISTINCT c.iso3, c.name FROM delegation d JOIN country c ON c.iso3 = d.iso3 JOIN committee cm ON cm.id = d.committee_id "
                               "WHERE cm.class_id = ? AND d.deleted_at IS NULL ORDER BY c.name", (sess.actor.class_id,))
        past = rows(conn, "SELECT ap.*, c.name AS country FROM ai_practice ap JOIN country c ON c.iso3 = ap.iso3 WHERE ap.student_id = ? "
                          "AND ap.deleted_at IS NULL ORDER BY ap.id DESC LIMIT 10", (sess.actor.id,))
    try:
        prov = get_provider(request.app.state.settings)
    except AIDisabled:
        prov = None
    return render(request, "intelligence/ai_practice_home.html", {"title": negotiation_label(request.app.state.settings), "paras": paras,
                                                                   "countries": countries, "past": past, "prov": prov})

@router.post("/me/ai-practice")
def ai_practice_start(request: Request, sess=Depends(require_student), form=Depends(form_data)):
    _provider(request)
    with request.app.state.db.write(request.state.actor) as w:
        iso3 = (form.get("iso3") or "").upper()
        if not one(w.conn, "SELECT 1 FROM country WHERE iso3 = ?", (iso3,)):
            raise UserError("Choose a country to negotiate with.")
        pid = form_int(form.get("paragraph_id"))
        if pid and not one(w.conn, "SELECT 1 FROM paragraph p JOIN resolution r ON r.id = p.resolution_id JOIN committee cm "
                                   "ON cm.id = r.committee_id WHERE p.id = ? AND cm.class_id = ?", (pid, sess.actor.class_id)):
            raise UserError("That paragraph isn't in your class's resolutions.", 403)
        aid = w.insert("ai_practice", {"student_id": sess.actor.id, "iso3": iso3, "paragraph_id": pid, "created_at": now_iso()})
    return redirect(f"/me/ai-practice/{aid}")

def _practice(conn, request, aid):
    ap = one(conn, "SELECT ap.*, c.name AS country FROM ai_practice ap JOIN country c ON c.iso3 = ap.iso3 WHERE ap.id = ? AND ap.deleted_at IS NULL", (aid,))
    if not ap or ap["student_id"] != request.state.actor.id:
        raise UserError("That practice isn't yours.", 403)
    return ap

def _stance_hint(conn, ap) -> int | None:
    if not ap["paragraph_id"]:
        return None
    from app.modules.mun.predict import run_prediction
    try:
        pred = run_prediction(conn, "paragraph", ap["paragraph_id"], runs=500, with_swing=False)
    except UserError:
        return None
    d = next((d for d in pred["dists"] if d.iso3 == ap["iso3"]), None)
    if not d or d.unknown:
        return None
    return int(max(-2, min(2, round(d.mu))))

@router.get("/me/ai-practice/{aid}")
def ai_practice_view(request: Request, aid: int, sess=Depends(require_student)):
    with request.app.state.db.read() as conn:
        ap = _practice(conn, request, aid)
        msgs = rows(conn, "SELECT * FROM ai_practice_message WHERE practice_id = ? ORDER BY id", (aid,))
        para = one(conn, "SELECT v.text, p.position FROM paragraph p JOIN paragraph_version v ON v.id = p.current_version_id WHERE p.id = ?",
                   (ap["paragraph_id"],)) if ap["paragraph_id"] else None
    return render(request, "intelligence/ai_practice.html", {"title": f"Negotiating with {ap['country']}", "ap": ap, "msgs": msgs, "para": para,
                                                             "prov": _provider(request)})

@router.post("/me/ai-practice/{aid}")
def ai_practice_send(request: Request, aid: int, sess=Depends(require_student), form=Depends(form_data)):
    text = (form.get("message") or "").strip()[:1500]
    if not text:
        raise UserError("Type what you want to say to the delegation.")
    provider = _provider(request)
    with request.app.state.db.write(request.state.actor) as w:
        ap = _practice(w.conn, request, aid)
        history = [(m["role"], m["text"]) for m in rows(w.conn, "SELECT role, text FROM ai_practice_message WHERE practice_id = ? ORDER BY id", (aid,))]
        reply = provider.roleplay(ap["country"], _stance_hint(w.conn, ap), _archetype_lines(w.conn, ap["iso3"]), history, text)
        for role, t in (("student", text), ("ai", reply or "(No reply. Try rephrasing.)")):
            w.conn.execute("INSERT INTO ai_practice_message (practice_id, role, text, created_at) VALUES (?,?,?,?)", (aid, role, t, now_iso()))
        I.log_ai(w.conn, provider, "roleplay", "student", f"practice {aid} with {ap['iso3']}", 0, "transcript")
    return redirect(f"/me/ai-practice/{aid}")

@router.get("/me/practice/{ps_id}/coach")
def coach(request: Request, ps_id: int, sess=Depends(require_student)):
    provider = _provider(request)
    with request.app.state.db.read() as conn:
        ps = one(conn, "SELECT * FROM practice_speech WHERE id = ? AND student_id = ? AND deleted_at IS NULL", (ps_id, sess.actor.id))
        if not ps:
            raise UserError("That practice isn't yours.", 403)
        scores = json.loads(ps["self_scores"] or "{}")
        notes = []
        for c in rows(conn, "SELECT * FROM rubric_criterion WHERE rubric_id = ? AND deleted_at IS NULL ORDER BY position", (ps["rubric_id"],)):
            desc = [d["descriptor"] for d in rows(conn, "SELECT descriptor FROM rubric_descriptor WHERE criterion_id = ? AND deleted_at IS NULL "
                                                        "ORDER BY level", (c["id"],))]
            lvl = scores.get(str(c["id"]))
            notes.append({"criterion": c["name"], "text": provider.coach(c["name"], desc, int(float(lvl)) if lvl else None, ps["reflection"])})
        conn.execute("INSERT INTO ai_call (provider, purpose, actor_kind, summary, sources, stored_as, created_at) VALUES (?,?,?,?,?,?,?)",
                     (provider.name, "coach", "student", f"practice speech {ps_id}", 0, "shown", now_iso()))
        conn.commit()
    return render(request, "intelligence/coach.html", {"title": "Coaching", "ps": ps, "notes": notes, "prov": provider})
