"""Phase 6 item 5: content — motion bank, carnival and inter-school documents, feedback prompts, the Evatt-style demo."""
from app.db import SYSTEM, connect
from app.db.seed import seed_content_updates
from tests.conftest import db_one, db_rows


def test_motion_bank_by_level_and_theme(app):
    rows = db_rows(app, "SELECT motion, topic, level FROM motion_bank WHERE deleted_at IS NULL")
    assert len(rows) >= 120 and len({r["motion"] for r in rows}) == len(rows)
    by_level = {lv: [r for r in rows if r["level"] == lv] for lv in ("junior", "middle", "senior")}
    assert all(len(v) >= 30 for v in by_level.values())
    assert len({r["topic"] for r in rows}) >= 10
    assert all(r["motion"].startswith("That ") for r in rows)


def test_content_updates_add_missing_without_overwriting(app):
    path = app.state.db.path
    conn = connect(path)
    try:
        conn.execute("UPDATE template SET body = 'MY EDIT' WHERE code = 'mc_script_house_carnival'")
        conn.execute("DELETE FROM template WHERE code = 'run_sheet_interschool'")
        # Its likely arguments (D-076) go first: they point at the motion.
        conn.execute("DELETE FROM motion_argument WHERE motion_id = (SELECT id FROM motion_bank WHERE motion = 'That every school should have a vegetable garden')")
        conn.execute("DELETE FROM motion_bank WHERE motion = 'That every school should have a vegetable garden'")
        conn.commit()
        seed_content_updates(conn)
        conn.commit()
        assert conn.execute("SELECT body FROM template WHERE code = 'mc_script_house_carnival'").fetchone()[0] == "MY EDIT"
        assert conn.execute("SELECT 1 FROM template WHERE code = 'run_sheet_interschool'").fetchone()
        assert conn.execute("SELECT 1 FROM motion_bank WHERE motion = 'That every school should have a vegetable garden'").fetchone()
        assert conn.execute("SELECT COUNT(*) FROM motion_argument a JOIN motion_bank m ON m.id = a.motion_id "
                            "WHERE m.motion = 'That every school should have a vegetable garden'").fetchone()[0] == 6
        assert conn.execute("SELECT 1 FROM source_type WHERE code = 'demo_unverified'").fetchone()
    finally:
        conn.close()


def test_house_carnival_documents_for_325_students(app, coord):
    from app.modules.debating.demo import make_carnival
    with app.state.db.write(SYSTEM) as w:
        eid = make_carnival(w, n_students=325, n_rounds=4, seed=11)["event_id"]
    r = coord.get(f"/debating/events/{eid}/documents/run_sheet")
    assert r.status_code == 200 and "TIMING SIGNALS" in r.text and "ROUND 4" in r.text
    assert "House carnival run sheet" in r.text              # chosen by default for a carnival
    debates = db_one(app, "SELECT COUNT(*) AS n FROM pairing p JOIN debate_round r ON r.id = p.round_id WHERE r.event_id = ? "
                          "AND p.neg_team_id IS NOT NULL", (eid,))["n"]
    assert r.text.count(" v ") >= debates                    # every debate is listed with its room
    r = coord.get(f"/debating/events/{eid}/documents/mc_script")
    assert "HOUSE ROLL CALL" in r.text and "Traditional Owners" in r.text and "points" in r.text


def test_interschool_documents_and_template_choice(app, coord):
    from app.modules.debating import service as S
    with app.state.db.write(SYSTEM) as w:
        fmt = w.conn.execute("SELECT id FROM debate_format WHERE reply = 1 ORDER BY id LIMIT 1").fetchone()[0]
        eid = S.create_event(w, "Inter-school round (test)", "competition", fmt)
    r = coord.get(f"/debating/events/{eid}/documents/mc_script")
    assert "CHAIRPERSON'S SCRIPT" in r.text or "CHAIRPERSON’S SCRIPT" in r.text
    r = coord.post(f"/debating/events/{eid}/documents/mc_script", {"action": "generate", "template": "mc_script_carnival"})
    assert r.status_code == 200 and "HOUSE ROLL CALL" in r.text     # staff can choose another template


def test_feedback_prompts_on_ballot(app, coord):
    pid = db_one(app, "SELECT id FROM pairing WHERE neg_team_id IS NOT NULL LIMIT 1")["id"]
    r = coord.get(f"/debating/pairings/{pid}/ballot")
    assert "Feedback prompts for adjudicators" in r.text and "reason for the decision in one sentence" in r.text
    assert db_one(app, "SELECT COUNT(*) AS n FROM feedback_prompt")["n"] >= 15


def test_evatt_demo_is_fictional_and_labelled(app, coord):
    com = db_one(app, "SELECT cm.*, vr.code AS rule FROM committee cm JOIN voting_rule vr ON vr.id = cm.voting_rule_id "
                      "WHERE cm.name LIKE 'Security Council: the situation in Veloria%'")
    assert com and com["rule"] == "sc_substantive"
    assert db_one(app, "SELECT COUNT(*) AS n FROM delegation WHERE committee_id = ?", (com["id"],))["n"] == 15
    ev = db_rows(app, "SELECT e.*, st.shown_as FROM evidence e JOIN source_type st ON st.code = e.source_type WHERE e.topic_id = ?",
                 (com["topic_id"],))
    assert len(ev) == 15 * 7
    assert all(e["source_type"] == "demo_unverified" and "not" in e["summary"] and "real position" in e["summary"] for e in ev)
    assert all(e["shown_as"].startswith("Unverified demo") for e in ev)
    paras = {p["tags"]: p["id"] for p in db_rows(app, "SELECT p.id, v.tags FROM paragraph p JOIN paragraph_version v ON v.id = p.current_version_id "
                                                       "JOIN resolution r ON r.id = p.resolution_id WHERE r.committee_id = ? AND p.kind = 'operative'",
                                                 (com["id"],))}
    from app.modules.mun.predict import run_prediction
    with app.state.db.read() as conn:
        p_sanctions = run_prediction(conn, "paragraph", paras["sanctions"], with_swing=False)["result"].p_pass
        p_aid = run_prediction(conn, "paragraph", paras["humanitarian_access"], with_swing=False)["result"].p_pass
    assert p_sanctions < 0.2 < 0.6 < p_aid      # invented vetoes sink sanctions; aid access is broadly supported
    page = coord.get(f"/mun/committees/{com['id']}/evidence").text
    assert "Unverified demo" in page
