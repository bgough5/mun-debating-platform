"""Committee flow v4 (D-068): six stages, the open floor, amendments from draft to adoption, points, messages,
speech drafts, friends and foes, and voting procedure."""
import math

from app.db import SYSTEM
from app.modules.floor import service as F
from app.modules.sim import service as SIM
from tests.api.helpers import ga, join_as, member_of, sc
from tests.conftest import db_one, db_rows


def _open(coord, app, com):
    coord.post(f"/chair/committee/{com['id']}/open")
    return db_one(app, "SELECT * FROM live_session WHERE committee_id = ? AND state = 'open'", (com["id"],))


def _stage(app, sid, code):
    with app.state.db.write(SYSTEM) as w:
        SIM.set_stage(w, sid, code)


def _operative(app, com):
    return db_rows(app, "SELECT p.*, v.text FROM paragraph p JOIN resolution r ON r.id = p.resolution_id "
                        "JOIN paragraph_version v ON v.id = p.current_version_id WHERE r.committee_id = ? AND p.kind = 'operative' "
                        "AND p.deleted_at IS NULL ORDER BY p.position", (com["id"],))


def test_six_stages_follow_the_new_flow(coord, app):
    assert SIM.STAGES == ["roll_call", "agenda", "opening_speeches", "floor", "voting_procedure", "debrief"]
    for rs in ("ga_simplified", "sc_simplified"):
        codes = [r["code"] for r in db_rows(app, "SELECT ps.code FROM procedure_stage ps JOIN procedure_rule_set r ON r.id = ps.rule_set_id "
                                                 "WHERE r.code = ? ORDER BY ps.position", (rs,))]
        assert codes == SIM.STAGES
    s = _open(coord, app, ga(app))
    _stage(app, s["id"], "floor")
    guide = coord.get(f"/chair/{s['id']}/guide").text
    assert "Are there any points or motions on the floor?" in guide and "Amendments" in guide


def test_unmoderated_caucus_is_capped_at_ten_minutes(coord, app):
    com = ga(app)
    s = _open(coord, app, com)
    _stage(app, s["id"], "floor")
    m = member_of(app, com["id"])[0]
    st = join_as(app, m["student_id"])
    r = st.post(f"/live/{s['id']}/unmod", {"minutes": "11"})
    assert "between 1 and 10 minutes" in r.text
    unmod = db_one(app, "SELECT id FROM procedure_motion WHERE rule_set_id = ? AND code = 'unmod'", (com["procedure_rule_set_id"],))
    r = coord.post(f"/chair/{s['id']}/motions", {"procedure_motion_id": str(unmod["id"]), "duration_min": "15"})
    assert "at most 10 minutes" in r.text
    st.post(f"/live/{s['id']}/unmod", {"minutes": "10"})
    mot = db_one(app, "SELECT * FROM motion WHERE session_id = ? ORDER BY id DESC LIMIT 1", (s["id"],))
    assert mot["duration_s"] == 600 and mot["proposer_delegation_id"] == m["delegation_id"]


def test_amendment_from_private_draft_to_adoption(coord, app):
    com = ga(app)
    s = _open(coord, app, com)
    _stage(app, s["id"], "floor")
    members = member_of(app, com["id"])
    a_m, b_m = members[0], members[1]
    a, b = join_as(app, a_m["student_id"]), join_as(app, b_m["student_id"])
    para = _operative(app, com)[0]
    new_text = para["text"].replace(".", "") + ", subject to an annual review."
    r = a.post(f"/mun/committees/{com['id']}/amendments", {"paragraph_id": str(para["id"]), "kind": "replace",
                                                           "proposed_text": new_text, "rationale": "Builds trust"})
    assert "Only your delegation sees it" in r.text
    aid = db_one(app, "SELECT id FROM amendment ORDER BY id DESC LIMIT 1")["id"]
    assert db_one(app, "SELECT submitted_at FROM amendment WHERE id = ?", (aid,))["submitted_at"] is None
    # Drafts are private to the sponsors: not on another delegation's board or in the workspace.
    assert f'id="a{aid}"' in a.get(f"/mun/committees/{com['id']}/amendments").text
    assert f'id="a{aid}"' not in b.get(f"/mun/committees/{com['id']}/amendments").text
    assert "still a draft" in b.post(f"/mun/amendments/{aid}/act", {"action": "sign"}).text
    a.post(f"/mun/amendments/{aid}/act", {"action": "submit"})
    board = b.get(f"/mun/committees/{com['id']}/amendments").text
    assert f'id="a{aid}"' in board and "<ins>" in board and "annual" in board
    # A suggested edit from another delegation; the sponsors accept it and the text changes.
    b.post(f"/mun/amendments/{aid}/act", {"action": "suggest", "proposed_text": new_text.replace("annual", "biennial"), "note": "less burden"})
    g = db_one(app, "SELECT * FROM amendment_suggestion WHERE amendment_id = ?", (aid,))
    assert g["status"] == "pending"
    assert b.post(f"/mun/amendments/{aid}/act", {"action": "accept", "suggestion_id": str(g["id"])}).status_code == 403
    a.post(f"/mun/amendments/{aid}/act", {"action": "accept", "suggestion_id": str(g["id"])})
    assert "biennial" in db_one(app, "SELECT proposed_text FROM amendment WHERE id = ?", (aid,))["proposed_text"]
    # It needs signatories (a fifth of the committee, at least two) before the chair can bring it to the floor.
    n = len({m["delegation_id"] for m in members})          # delegations with students; computed seats can't sign
    needed = max(2, math.ceil(n / 5))
    assert F.signatories_needed(app.state.db.read().__enter__(), com["id"]) == needed
    r = coord.post(f"/chair/{s['id']}/floor", {"action": "bring", "amendment_id": str(aid)})
    assert "signatories" in r.text
    signers, seen = [], {a_m["delegation_id"]}
    for m in members:
        if m["delegation_id"] not in seen:
            seen.add(m["delegation_id"])
            signers.append(m)
    signers = signers[:needed]
    clients = {a_m["student_id"]: a, b_m["student_id"]: b}
    for m in signers:
        c = clients.get(m["student_id"]) or clients.setdefault(m["student_id"], join_as(app, m["student_id"]))
        assert "Signed." in c.post(f"/mun/amendments/{aid}/act", {"action": "sign"}).text
    r = coord.post(f"/chair/{s['id']}/floor", {"action": "bring", "amendment_id": str(aid)})
    sess = db_one(app, "SELECT * FROM live_session WHERE id = ?", (s["id"],))
    assert sess["floor_amendment_id"] == aid, (r.status_code, __import__("re").findall(r'(?s)<main.*?</h1>(.{0,600})', r.text),
                                                db_rows(app, "SELECT * FROM amendment_support WHERE amendment_id = ?", (aid,)))
    assert sess["floor_amendment_id"] == aid
    # Suggestions are frozen while it is on the floor.
    assert "on the floor" in b.post(f"/mun/amendments/{aid}/act", {"action": "suggest", "proposed_text": "x y z"}).text
    # Speakers for and against: the live list is only the amendment's list now.
    coord.post(f"/chair/{s['id']}/speakers", {"delegation_id": str(members[5]["delegation_id"]), "list_kind": "general"})
    a.post(f"/live/{s['id']}/side", {"side": "for"})
    b.post(f"/live/{s['id']}/side", {"side": "against"})
    page = b.get(f"/live/{s['id']}").text
    assert "Speakers on the amendment" in page and "Speak for it" not in page
    coord.post(f"/chair/{s['id']}/next")
    cur = db_one(app, "SELECT e.* FROM speakers_list_entry e JOIN live_session ls ON ls.current_entry_id = e.id WHERE ls.id = ?", (s["id"],))
    assert cur["side"] == "for" and cur["amendment_id"] == aid
    # The vote: students vote, it passes, the clause changes and the floor clears.
    coord.post(f"/chair/{s['id']}/floor", {"action": "vote_amendment", "amendment_id": str(aid)})
    did = db_one(app, "SELECT * FROM division WHERE session_id = ? AND status = 'open'", (s["id"],))
    assert did["target_kind"] == "amendment" and did["target_id"] == aid
    voted = set()
    for m in members:
        if m["delegation_id"] in voted:
            continue
        voted.add(m["delegation_id"])
        c = clients.get(m["student_id"]) or clients.setdefault(m["student_id"], join_as(app, m["student_id"]))
        c.post(f"/live/{s['id']}/vote", {"vote": "yes"})
    coord.post(f"/chair/{s['id']}/divisions/{did['id']}", {"action": "close"})
    assert db_one(app, "SELECT status FROM amendment WHERE id = ?", (aid,))["status"] == "passed"
    assert "biennial" in _operative(app, com)[0]["text"]
    assert db_one(app, "SELECT floor_amendment_id FROM live_session WHERE id = ?", (s["id"],))["floor_amendment_id"] is None
    assert not db_rows(app, "SELECT id FROM speakers_list_entry WHERE session_id = ? AND amendment_id = ? AND status = 'waiting'", (s["id"], aid))


def test_friendly_amendment_is_adopted_without_a_vote(coord, app):
    com = ga(app)
    s = _open(coord, app, com)
    _stage(app, s["id"], "floor")
    m = member_of(app, com["id"])[0]
    a = join_as(app, m["student_id"])
    para = _operative(app, com)[1]
    a.post(f"/mun/committees/{com['id']}/amendments", {"paragraph_id": str(para["id"]), "kind": "replace",
                                                       "proposed_text": "Urges all Member States to act together.", "submit_now": "1"})
    aid = db_one(app, "SELECT id FROM amendment ORDER BY id DESC LIMIT 1")["id"]
    coord.post(f"/chair/{s['id']}/floor", {"action": "friendly", "amendment_id": str(aid)})
    assert db_one(app, "SELECT status FROM amendment WHERE id = ?", (aid,))["status"] == "friendly"
    assert _operative(app, com)[1]["text"] == "Urges all Member States to act together."
    assert not db_rows(app, "SELECT id FROM division WHERE target_kind = 'amendment' AND target_id = ?", (aid,))


def test_points_and_right_of_reply(coord, app):
    com = ga(app)
    s = _open(coord, app, com)
    _stage(app, s["id"], "floor")
    m, m2 = member_of(app, com["id"])[:2]
    st = join_as(app, m["student_id"])
    st.post(f"/live/{s['id']}/points", {"kind": "privilege", "note": "Can't hear the speaker"})
    assert "already has a point waiting" in st.post(f"/live/{s['id']}/points", {"kind": "order"}).text
    p = db_one(app, "SELECT * FROM floor_point WHERE session_id = ?", (s["id"],))
    console = coord.get(f"/chair/{s['id']}/f/floor").text
    assert "Point of personal privilege" in console and "hear the speaker" in console
    coord.post(f"/chair/{s['id']}/points/{p['id']}", {"status": "answered"})
    assert db_one(app, "SELECT status FROM floor_point WHERE id = ?", (p["id"],))["status"] == "answered"
    # Right of reply: granted, the delegation goes to the top of the list.
    coord.post(f"/chair/{s['id']}/speakers", {"delegation_id": str(m2["delegation_id"]), "list_kind": "general"})
    st.post(f"/live/{s['id']}/points", {"kind": "reply", "note": "Our country was named"})
    p2 = db_one(app, "SELECT * FROM floor_point WHERE session_id = ? AND kind = 'reply'", (s["id"],))
    coord.post(f"/chair/{s['id']}/points/{p2['id']}", {"status": "granted"})
    first = db_rows(app, "SELECT delegation_id FROM speakers_list_entry WHERE session_id = ? AND status = 'waiting' ORDER BY position", (s["id"],))[0]
    assert first["delegation_id"] == m["delegation_id"]
    # In voting procedure only points of order and personal privilege are in order.
    _stage(app, s["id"], "voting_procedure")
    assert "only points of order" in st.post(f"/live/{s['id']}/points", {"kind": "inquiry"}).text


def test_messages_between_delegations_are_private_but_the_chair_sees_them(coord, app):
    com = ga(app)
    s = _open(coord, app, com)
    _stage(app, s["id"], "floor")
    m1, m2, m3 = member_of(app, com["id"])[:3]
    a, b, c = join_as(app, m1["student_id"]), join_as(app, m2["student_id"]), join_as(app, m3["student_id"])
    a.post(f"/live/{s['id']}/messages", {"to_delegation_id": str(m2["delegation_id"]), "body": "Will you co-sign our amendment?"})
    assert "co-sign our amendment" in b.get(f"/live/{s['id']}/f/messages").text
    assert "co-sign our amendment" in a.get(f"/live/{s['id']}/f/messages").text
    assert "co-sign our amendment" not in c.get(f"/live/{s['id']}/f/messages").text
    assert "co-sign our amendment" in coord.get(f"/chair/{s['id']}/messages").text
    # The chair hides a message: both delegations see that it was hidden.
    mid = db_one(app, "SELECT id FROM delegate_message")["id"]
    coord.post(f"/chair/{s['id']}/messages/{mid}", {"action": "hide"})
    view = b.get(f"/live/{s['id']}/f/messages").text
    assert "Hidden by the chair" in view and "co-sign our amendment" not in view
    assert "under 500 characters" in a.post(f"/live/{s['id']}/messages", {"to_delegation_id": str(m2["delegation_id"]), "body": "x" * 501}).text
    for i in range(F.MESSAGES_PER_MINUTE - 1):
        a.post(f"/live/{s['id']}/messages", {"to_delegation_id": str(m3["delegation_id"]), "body": f"note {i}"})
    assert "a lot of messages" in a.post(f"/live/{s['id']}/messages", {"to_delegation_id": str(m3["delegation_id"]), "body": "again"}).text
    _stage(app, s["id"], "voting_procedure")
    assert "No notes during voting procedure" in b.post(f"/live/{s['id']}/messages", {"to_delegation_id": str(m1["delegation_id"]), "body": "psst"}).text


def test_message_channels_are_authorised(coord, app):
    from app.db import Actor
    from app.web.ws import channel_allowed
    com = ga(app)
    s = _open(coord, app, com)
    m1, m2 = member_of(app, com["id"])[:2]
    st = db_one(app, "SELECT * FROM student WHERE id = ?", (m1["student_id"],))
    actor = Actor("student", st["id"], st["first_name"], st["class_id"])
    with app.state.db.read() as conn:
        assert channel_allowed(conn, actor, f"inbox:{m1['delegation_id']}", None, 25)[0]
        assert not channel_allowed(conn, actor, f"inbox:{m2['delegation_id']}", None, 25)[0]
        assert not channel_allowed(conn, actor, f"chat:{s['id']}", None, 25)[0]
        assert not channel_allowed(conn, None, f"inbox:{m1['delegation_id']}", s["projector_token"], 25)[0]


def test_speech_drafts_are_private(coord, app):
    com = ga(app)
    m1, m2 = member_of(app, com["id"])[:2]
    a, b = join_as(app, m1["student_id"]), join_as(app, m2["student_id"])
    words = " ".join(["word"] * 130)
    r = a.post(f"/me/committees/{com['id']}/speeches", {"kind": "opening", "title": "Opening", "body": words,
                                                        "next": f"/me/committees/{com['id']}/prepare"})
    assert "130 words" in r.text and "about 60 seconds" in r.text
    d = db_one(app, "SELECT * FROM speech_draft WHERE student_id = ?", (m1["student_id"],))
    assert "word word" not in b.get(f"/me/committees/{com['id']}/prepare").text
    assert b.post(f"/me/committees/{com['id']}/speeches", {"kind": "opening", "body": "mine now", "draft_id": str(d["id"])}).status_code == 403
    assert b.post(f"/me/committees/{com['id']}/speeches", {"delete": "1", "draft_id": str(d["id"])}).status_code == 403
    # Saving the opening statement again updates the one draft.
    a.post(f"/me/committees/{com['id']}/speeches", {"kind": "opening", "body": "Shorter."})
    assert len(db_rows(app, "SELECT id FROM speech_draft WHERE student_id = ? AND deleted_at IS NULL", (m1["student_id"],))) == 1
    assert a.post(f"/me/committees/{com['id']}/speeches", {"kind": "speech", "body": "x", "next": "https://evil.example/"}).url.path.startswith("/me/")


def test_friends_and_foes_covers_operative_clauses_only(coord, app):
    com = ga(app)
    m1, m2 = member_of(app, com["id"])[:2]
    a = join_as(app, m1["student_id"])
    page = a.get(f"/me/committees/{com['id']}/friends-foes").text
    ops = _operative(app, com)
    assert "Operative clause 1" in page and "preambular" not in page.lower().split("the preamble is left out")[1]
    assert "engine's estimate" in page and ("Estimate only" in page or "Sourced" in page or "Unknown" in page)
    a.post(f"/me/committees/{com['id']}/friends-foes", {"clause": str(ops[0]["id"]), f"stance_{m2['delegation_id']}": "friend",
                                                        f"note_{m2['delegation_id']}": "said yes in caucus"})
    e = db_one(app, "SELECT * FROM ff_entry WHERE student_id = ?", (m1["student_id"],))
    assert e["stance"] == "friend" and e["note"] == "said yes in caucus" and e["paragraph_id"] == ops[0]["id"]
    pre = db_one(app, "SELECT p.id FROM paragraph p JOIN resolution r ON r.id = p.resolution_id WHERE r.committee_id = ? "
                      "AND p.kind = 'preambular' LIMIT 1", (com["id"],))
    if pre:
        assert "operative clause" in a.post(f"/me/committees/{com['id']}/friends-foes",
                                              {"clause": str(pre["id"]), f"stance_{m2['delegation_id']}": "foe"}).text
    # Another student's sheet is their own.
    b = join_as(app, m2["student_id"])
    b.get(f"/me/committees/{com['id']}/friends-foes")
    assert not db_rows(app, "SELECT id FROM ff_entry WHERE student_id = ?", (m2["student_id"],))


def test_close_debate_moves_to_voting_procedure_and_failed_vote_reopens_with_another_draft(coord, app):
    com = ga(app)
    s = _open(coord, app, com)
    _stage(app, s["id"], "floor")
    cd = db_one(app, "SELECT id FROM procedure_motion WHERE rule_set_id = ? AND code = 'close_debate'", (com["procedure_rule_set_id"],))
    m = member_of(app, com["id"])
    coord.post(f"/chair/{s['id']}/motions", {"procedure_motion_id": str(cd["id"]), "proposer_delegation_id": str(m[0]["delegation_id"])})
    mid = db_one(app, "SELECT id FROM motion WHERE session_id = ?", (s["id"],))["id"]
    coord.post(f"/chair/{s['id']}/motions/{mid}", {"action": "second", "delegation_id": str(m[1]["delegation_id"])})
    coord.post(f"/chair/{s['id']}/motions/{mid}", {"action": "consent"})
    sess = db_one(app, "SELECT * FROM live_session WHERE id = ?", (s["id"],))
    assert sess["stage"] == "voting_procedure" and sess["mode"] == "voting"
    guide = coord.get(f"/chair/{s['id']}/guide").text
    assert "Roll-call vote order" in guide
    # A second draft exists; the first fails; the floor reopens with the second.
    coord.post(f"/mun/committees/{com['id']}/resolutions", {"title": "Alternative draft"})
    r1 = db_one(app, "SELECT id FROM resolution WHERE committee_id = ? ORDER BY id LIMIT 1", (com["id"],))["id"]
    r2 = db_one(app, "SELECT id FROM resolution WHERE committee_id = ? AND title = 'Alternative draft'", (com["id"],))["id"]
    coord.post(f"/chair/{s['id']}/divisions", {"target": f"resolution:{r1}"})
    did = db_one(app, "SELECT id FROM division WHERE session_id = ? AND status = 'open'", (s["id"],))["id"]
    for x in m:
        join_as(app, x["student_id"]).post(f"/live/{s['id']}/vote", {"vote": "no"})
    coord.post(f"/chair/{s['id']}/divisions/{did}", {"action": "close"})
    assert "Reopen the floor with it" in coord.get(f"/chair/{s['id']}/guide").text
    coord.post(f"/chair/{s['id']}/floor", {"action": "reopen", "resolution_id": str(r2)})
    sess = db_one(app, "SELECT * FROM live_session WHERE id = ?", (s["id"],))
    assert sess["stage"] == "floor" and sess["resolution_id"] == r2 and sess["mode"] == "formal"


def test_student_tabs_render_and_remember_the_tab(coord, app):
    com = ga(app)
    s = _open(coord, app, com)
    m = member_of(app, com["id"])[0]
    st = join_as(app, m["student_id"])
    page = st.get(f"/live/{s['id']}?tab=messages").text
    for label in ("Floor", "Motions and votes", "Points", "Messages", "My speech", "Amendments", "Friends and foes"):
        assert f"{label}</a>" in page
    assert 'id="tab-messages"' in page and 'aria-selected="true"' in page.split('id="tab-messages"')[1][:300]
    assert 'data-panel="floor" hidden' in page and 'data-panel="messages" >' in page.replace('data-panel="messages"  >', 'data-panel="messages" >')
    frag = st.get(f"/live/{s['id']}/f?tab=points").text
    assert 'data-panel="points" >' in frag.replace('data-panel="points"  >', 'data-panel="points" >') and "Raise the point" in frag


def test_prepare_page_has_the_brief_and_the_statement_pad(coord, app):
    com = ga(app)
    m = member_of(app, com["id"])[0]
    st = join_as(app, m["student_id"])
    page = st.get(f"/me/committees/{com['id']}/prepare").text
    assert "Your country:" in page and "The proposed resolution" in page and "Your opening statement" in page
    assert "never writes it for you" in page
    assert "Prepare</a>" in st.get("/me").text


def test_security_council_closing_debate_needs_nine(coord, app):
    com = sc(app)
    if not com:
        return
    rows = db_rows(app, "SELECT ps.chair_next FROM procedure_stage ps JOIN procedure_rule_set r ON r.id = ps.rule_set_id "
                        "WHERE r.code = 'sc_simplified' AND ps.code = 'floor'")
    assert "nine of the fifteen" in rows[0]["chair_next"]


def test_upgrade_maps_old_stages_and_adds_the_floor(tmp_path, monkeypatch):
    """An existing laptop database (nine stages, a session mid-caucus, a session at division, a tabled amendment)
    upgrades to the six-stage flow without losing anything."""
    import shutil
    import sqlite3
    from app import db as DB
    from app.db.seed import seed_content_updates
    real = DB.MIGRATIONS_DIR
    old = tmp_path / "mig"
    old.mkdir()
    for f in sorted(real.glob("*.sql")):
        if int(f.name.split("_")[0]) <= 6:
            shutil.copy(f, old / f.name)
    conn = sqlite3.connect(str(tmp_path / "t.db"))
    conn.row_factory = sqlite3.Row
    monkeypatch.setattr(DB, "MIGRATIONS_DIR", old)
    DB.migrate(conn)
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("INSERT INTO procedure_rule_set (id, code, name) VALUES (1, 'ga_simplified', 'GA')")
    for i, code in enumerate(["roll_call", "agenda", "opening_speeches", "caucus", "draft_resolution", "amendments",
                              "voting_procedure", "division", "debrief"], 1):
        conn.execute("INSERT INTO procedure_stage (rule_set_id, code, position, name, chair_script) VALUES (1, ?, ?, ?, 'edited by Ben')",
                     (code, i, code.title()))
    conn.execute("INSERT INTO live_session (id, committee_id, projector_token, created_at, stage) VALUES (1, 1, 'a', 'x', 'caucus')")
    conn.execute("INSERT INTO live_session (id, committee_id, projector_token, created_at, stage) VALUES (2, 1, 'b', 'x', 'division')")
    conn.execute("INSERT INTO amendment (id, paragraph_id, base_version_id, kind, created_at) VALUES (1, 1, 1, 'replace', '2026-10-01')")
    conn.commit()
    monkeypatch.undo()                       # back to the real migrations folder: 0007 applies
    DB.migrate(conn)
    seed_content_updates(conn)
    codes = [r["code"] for r in conn.execute("SELECT code FROM procedure_stage ORDER BY position")]
    assert codes == ["roll_call", "agenda", "opening_speeches", "floor", "voting_procedure", "debrief"]
    assert conn.execute("SELECT chair_script FROM procedure_stage WHERE code = 'agenda'").fetchone()[0] == "edited by Ben"
    assert [r["stage"] for r in conn.execute("SELECT stage FROM live_session ORDER BY id")] == ["floor", "voting_procedure"]
    assert conn.execute("SELECT submitted_at FROM amendment WHERE id = 1").fetchone()[0] == "2026-10-01"


def test_erasing_a_student_removes_their_floor_writing(coord, app):
    from app.db import Actor
    from app.retention import erase_student
    com = ga(app)
    s = _open(coord, app, com)
    _stage(app, s["id"], "floor")
    m1, m2 = member_of(app, com["id"])[:2]
    a = join_as(app, m1["student_id"])
    a.post(f"/live/{s['id']}/messages", {"to_delegation_id": str(m2["delegation_id"]), "body": "A private note from me"})
    a.post(f"/me/committees/{com['id']}/speeches", {"kind": "opening", "body": "My own opening words"})
    a.post(f"/live/{s['id']}/points", {"kind": "inquiry", "note": "How long is the caucus?"})
    para = _operative(app, com)[0]
    a.post(f"/me/committees/{com['id']}/friends-foes", {"clause": str(para["id"]), f"stance_{m2['delegation_id']}": "foe"})
    with app.state.db.write(Actor("coordinator", None, "Coordinator")) as w:
        counts = erase_student(w, m1["student_id"])
    assert counts["speech_draft"] == 1 and counts["ff_entry"] == 1 and counts["delegate_message"] == 1
    assert db_one(app, "SELECT body FROM delegate_message")["body"] == "[erased]"
    assert db_one(app, "SELECT note, student_id FROM floor_point") == {"note": "", "student_id": None}
    logs = " ".join(str(r["after_json"]) for r in db_rows(app, "SELECT after_json FROM event_log"))
    assert "A private note from me" not in logs and "My own opening words" not in logs


def test_security_council_veto_warning_and_minutes_record_the_floor(coord, app):
    com = sc(app)
    assert com, "the demo has a Security Council"
    s = _open(coord, app, com)
    _stage(app, s["id"], "floor")
    members = member_of(app, com["id"])
    p5 = next((m for m in members if m["iso3"] in ("CHN", "FRA", "RUS", "GBR", "USA")), None)
    assert p5, "a permanent member is held by a student in the demo"
    st = join_as(app, p5["student_id"])
    st.post(f"/live/{s['id']}/points", {"kind": "inquiry", "note": "Is a P5 abstention a veto?"})
    pid = db_one(app, "SELECT id FROM floor_point WHERE session_id = ?", (s["id"],))["id"]
    coord.post(f"/chair/{s['id']}/points/{pid}", {"status": "answered"})
    res = db_one(app, "SELECT id FROM resolution WHERE committee_id = ?", (com["id"],))
    assert res
    coord.post(f"/chair/{s['id']}/divisions", {"target": f"resolution:{res['id']}"})
    st.post(f"/live/{s['id']}/vote", {"vote": "no"})
    country = db_one(app, "SELECT name FROM country WHERE iso3 = ?", (p5["iso3"],))["name"]
    assert "Veto:" in coord.get(f"/chair/{s['id']}/f/division").text and country in coord.get(f"/chair/{s['id']}/f/division").text
    tok = db_one(app, "SELECT projector_token FROM live_session WHERE id = ?", (s["id"],))["projector_token"]
    assert "Veto:" in coord.get(f"/projector/{tok}").text
    minutes = coord.get(f"/chair/{s['id']}/minutes").text
    assert "Point of parliamentary inquiry from" in minutes and "answered" in minutes
