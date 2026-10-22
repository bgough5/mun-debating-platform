"""Spec W-1, end to end through the HTTP API in demo mode (fake data)."""
import re

from tests.conftest import db_one, db_rows


def _ga(app):
    com = db_one(app, "SELECT * FROM committee WHERE name LIKE 'United Nations General Assembly%'")
    para = db_one(app, "SELECT p.* FROM paragraph p JOIN resolution r ON r.id = p.resolution_id WHERE r.committee_id = ? "
                       "AND p.kind = 'operative' AND p.position = 6", (com["id"],))   # clause 2.6 (finance)
    return com, para


def test_w1_end_to_end(coord, app):
    com, para = _ga(app)
    fji = db_one(app, "SELECT id FROM delegation WHERE committee_id = ? AND iso3 = 'FJI'", (com["id"],))
    # 1. Table an amendment (replace) with a sponsor
    r = coord.post(f"/mun/paragraphs/{para['id']}/amendments", {
        "kind": "replace", "proposed_text": "Suggests all wealthy developed States increase support to the Green Climate Fund, "
                                            "with progress reported every two years.",
        "tags": ["cost_wealthy", "adapt_finance", "binding"], "sponsor_delegation_id": fji["id"]})
    assert r.status_code == 200
    am = db_one(app, "SELECT * FROM amendment WHERE paragraph_id = ? ORDER BY id DESC LIMIT 1", (para["id"],))
    assert am["base_version_id"] == para["current_version_id"] and am["sponsor_delegation_id"] == fji["id"]
    assert db_one(app, "SELECT kind FROM amendment_support WHERE amendment_id = ?", (am["id"],))["kind"] == "sponsor"

    # 2. P(pass) for original and amended, each with a 90% interval and the rule
    r = coord.get(f"/mun/paragraphs/{para['id']}/compare")
    assert r.status_code == 200 and f"Amendment {am['id']}" in r.text
    r0 = coord.get(f"/mun/predict/paragraph/{para['id']}")
    r1 = coord.get(f"/mun/predict/amendment/{am['id']}")
    for r in (r0, r1):
        assert r.status_code == 200
        assert "90% interval" in r.text and "GA simple majority" in r.text
        assert re.search(r'class="bigstat">\d+%', r.text)

    # 3. Swing list: ranked rows with evidence and staleness information
    assert "Who decides it" in r1.text and re.search(r"[+-]\d+\.\d pts", r1.text)
    assert "item(s)" in r1.text or "only the model estimate" in r1.text

    # 4. Lobbying tasks from the top swing blocs and countries
    r = coord.post(f"/mun/predict/amendment/{am['id']}/tasks", {"delegation_id": fji["id"], "top_n": 3})
    assert r.status_code == 200 and "lobbying task" in r.text
    tasks = db_rows(app, "SELECT * FROM task WHERE delegation_id = ? AND amendment_id = ?", (fji["id"], am["id"]))
    assert len(tasks) == 3
    assert all((t["target_iso3"] or t["target_bloc_id"]) and t["assignee_student_id"] for t in tasks)
    r = coord.post(f"/mun/tasks/{tasks[0]['id']}", {"status": "doing", "talking_points": "Ask about the review clause."})
    assert db_one(app, "SELECT talking_points FROM task WHERE id = ?", (tasks[0]["id"],))["talking_points"] == "Ask about the review clause."

    # 5. New evidence (bloc-level, conditional) updates the prediction, and the change is logged
    before = _p_pass(coord, am["id"])
    aosis = db_one(app, "SELECT id FROM bloc WHERE code = 'AOSIS'")["id"]
    r = coord.post(f"/mun/committees/{com['id']}/evidence", {
        "subject_kind": "bloc", "bloc_id": aosis, "target_kind": "amendment", "target_id_amendment": am["id"],
        "position": "2", "strength": "strong", "conditional": "1", "condition_text": "a review clause is included",
        "source_type": "student_intel", "source": "AOSIS chair (Fiji delegate), caucus, 22 Oct", "summary": "Will back it with review"})
    assert r.status_code == 200
    after = _p_pass(coord, am["id"])
    assert after != before
    assert db_one(app, "SELECT COUNT(*) AS n FROM event_log WHERE entity = 'evidence' AND action = 'create' AND actor_kind = 'coordinator'")["n"] == 1

    # 6. Save the prediction, record the actual vote, and see calibration
    coord.post(f"/mun/predict/amendment/{am['id']}/snapshot")
    snap = db_one(app, "SELECT * FROM prediction WHERE target_kind = 'amendment' AND target_id = ?", (am["id"],))
    assert snap and snap["seed"] and len(snap["inputs_hash"]) == 64
    isos = [d["iso3"] for d in db_rows(app, "SELECT iso3 FROM delegation WHERE committee_id = ?", (com["id"],))]
    votes = {f"v_{iso}": ("yes" if i % 3 else "no") for i, iso in enumerate(isos)}
    r = coord.post(f"/mun/votes/amendment/{am['id']}", votes)
    assert r.status_code == 200 and "Recorded result" in r.text
    assert db_one(app, "SELECT COUNT(*) AS n FROM actual_vote WHERE target_kind='amendment' AND target_id=?", (am["id"],))["n"] == 31
    r = coord.get("/mun/calibration")
    assert r.status_code == 200 and "Brier score" in r.text and "Everyone votes yes" in r.text and "Only 31" in r.text


def _p_pass(c, aid):
    t = c.get(f"/mun/predict/amendment/{aid}").text
    return re.search(r'class="bigstat">(\d+)%', t).group(1)


def test_snapshot_replays_exactly(coord, app):
    com, para = _ga(app)
    coord.post(f"/mun/predict/paragraph/{para['id']}/snapshot")
    pid = db_one(app, "SELECT id FROM prediction ORDER BY id DESC LIMIT 1")["id"]
    r = coord.get(f"/mun/predictions/{pid}/replay")
    assert "Reproduced exactly" in r.text


def test_edit_versions_restore_and_undo(coord, app):
    com, para = _ga(app)
    r = coord.post(f"/mun/paragraphs/{para['id']}", {"text": "New wording A.", "tags": ["cost_wealthy"], "version_id": para["current_version_id"]})
    assert r.status_code == 200
    p = db_one(app, "SELECT p.*, v.text FROM paragraph p JOIN paragraph_version v ON v.id = p.current_version_id WHERE p.id = ?", (para["id"],))
    assert p["text"] == "New wording A."
    # stale version id -> conflict, nothing lost
    r = coord.post(f"/mun/paragraphs/{para['id']}", {"text": "B", "tags": [], "version_id": para["current_version_id"]})
    assert r.status_code == 409
    # undo returns to the original text
    coord.post("/mun/undo")
    p2 = db_one(app, "SELECT v.text FROM paragraph p JOIN paragraph_version v ON v.id = p.current_version_id WHERE p.id = ?", (para["id"],))
    assert p2["text"].startswith("Suggests all wealthy")
    # history lists both versions, and an old one can be restored
    r = coord.get(f"/mun/paragraphs/{para['id']}/history")
    assert "New wording A." in r.text
    vid = db_one(app, "SELECT id FROM paragraph_version WHERE paragraph_id = ? AND text = 'New wording A.'", (para["id"],))["id"]
    coord.post(f"/mun/paragraphs/{para['id']}/restore/{vid}")
    p3 = db_one(app, "SELECT v.text FROM paragraph p JOIN paragraph_version v ON v.id = p.current_version_id WHERE p.id = ?", (para["id"],))
    assert p3["text"] == "New wording A."


def test_passed_amendment_applies_text(coord, app):
    com, para = _ga(app)
    am = db_one(app, "SELECT * FROM amendment WHERE paragraph_id = ?", (para["id"],))   # the demo 'review' amendment
    coord.post(f"/mun/amendments/{am['id']}/status", {"status": "passed"})
    p = db_one(app, "SELECT v.text, v.tags FROM paragraph p JOIN paragraph_version v ON v.id = p.current_version_id WHERE p.id = ?", (para["id"],))
    assert p["text"] == am["proposed_text"] and "binding" in p["tags"]


def test_override_survives_amendment(coord, app):
    """Audit §5.2: in v2 any amendment discarded overrides. Now paragraph evidence carries over to amendments."""
    from app.modules.mun.predict import run_prediction
    com = db_one(app, "SELECT * FROM committee WHERE name LIKE 'United Nations General Assembly%'")
    p21 = db_one(app, "SELECT p.* FROM paragraph p JOIN resolution r ON r.id = p.resolution_id WHERE r.committee_id = ? AND p.kind='operative' AND p.position = 1", (com["id"],))
    am = db_one(app, "SELECT * FROM amendment WHERE paragraph_id = ?", (p21["id"],))   # 'soften' amendment
    with app.state.db.read() as conn:
        base = {d.iso3: d for d in run_prediction(conn, "paragraph", p21["id"], runs=500)["dists"]}
        amended = {d.iso3: d for d in run_prediction(conn, "amendment", am["id"], runs=500)["dists"]}
    assert base["USA"].mu < -1.4 and amended["USA"].mu < -1.0   # the US override (-2) still counts


def test_exports_open(coord, app):
    import io

    from docx import Document
    com, para = _ga(app)
    r = coord.get(f"/mun/resolutions/{para['resolution_id']}/export.docx")
    assert r.status_code == 200
    doc = Document(io.BytesIO(r.content))
    assert any("Green Climate Fund" in p.text for p in doc.paragraphs)
    r = coord.get(f"/mun/resolutions/{para['resolution_id']}/print")
    assert r.status_code == 200 and "Save as PDF" in r.text
