"""Live session: speakers list, timers, motions, divisions with computed delegations, minutes, cap, small groups."""
import pytest

from app.util import set_clock
from tests.api.helpers import ga, join_as, member_of, sc
from tests.conftest import db_one, db_rows


@pytest.fixture
def frozen_clock():
    t = [1_800_000_000.0]
    set_clock(lambda: t[0])
    yield t
    set_clock(None)


def _open(coord, app, com):
    r = coord.post(f"/chair/committee/{com['id']}/open")
    assert r.status_code == 200
    return db_one(app, "SELECT * FROM live_session WHERE committee_id = ? AND state = 'open'", (com["id"],))


def test_reopen_returns_same_session(coord, app):
    com = ga(app)
    s1 = _open(coord, app, com)
    s2 = _open(coord, app, com)
    assert s1["id"] == s2["id"]       # chair reconnect: the open session is resumed, not duplicated


def test_speakers_list_and_timer(coord, app, frozen_clock):
    com = ga(app)
    s = _open(coord, app, com)
    dels = db_rows(app, "SELECT id, iso3 FROM delegation WHERE committee_id = ? ORDER BY iso3 LIMIT 3", (com["id"],))
    for d in dels:
        coord.post(f"/chair/{s['id']}/speakers", {"delegation_id": d["id"]})
    r = coord.post(f"/chair/{s['id']}/speakers", {"delegation_id": dels[0]["id"]})
    assert r.status_code == 400 and "already waiting" in r.text
    e = db_rows(app, "SELECT * FROM speakers_list_entry WHERE session_id = ? ORDER BY position", (s["id"],))
    coord.post(f"/chair/{s['id']}/entries/{e[2]['id']}", {"action": "up"})
    order = [r["delegation_id"] for r in db_rows(app, "SELECT delegation_id FROM speakers_list_entry WHERE session_id = ? AND status='waiting' ORDER BY position", (s["id"],))]
    assert order == [dels[0]["id"], dels[2]["id"], dels[1]["id"]]
    coord.post(f"/chair/{s['id']}/next")
    t = db_one(app, "SELECT * FROM timer WHERE session_id = ? AND kind = 'speaker'", (s["id"],))
    assert t["duration_s"] == 90 and t["state"] == "idle"
    coord.post(f"/chair/{s['id']}/timers/{t['id']}", {"action": "start"})
    frozen_clock[0] += 30
    coord.post(f"/chair/{s['id']}/timers/{t['id']}", {"action": "pause"})
    from app.modules.chair.service import remaining
    t = db_one(app, "SELECT * FROM timer WHERE id = ?", (t["id"],))
    assert remaining(t) == pytest.approx(60)
    coord.post(f"/chair/{s['id']}/timers/{t['id']}", {"action": "extend", "seconds": "30"})
    frozen_clock[0] += 100        # paused: no time passes
    t = db_one(app, "SELECT * FROM timer WHERE id = ?", (t["id"],))
    assert remaining(t) == pytest.approx(90) and t["state"] == "paused"
    coord.post(f"/chair/{s['id']}/yield", {"to": "questions"})
    assert db_one(app, "SELECT yielded_to FROM speakers_list_entry WHERE id = ?", (e[0]["id"],))["yielded_to"] == "questions"


def test_extra_time_for_a_student(coord, app):
    com = ga(app)
    s = _open(coord, app, com)
    m = member_of(app, com["id"])[0]
    coord.post(f"/chair/{s['id']}/adjust", {"student_id": m["student_id"], "extra_percent": "50"})
    c = join_as(app, m["student_id"])
    c.get(f"/live/{s['id']}")
    c.post(f"/live/{s['id']}/speak")
    coord.post(f"/chair/{s['id']}/next")
    t = db_one(app, "SELECT * FROM timer WHERE session_id = ? AND kind = 'speaker'", (s["id"],))
    assert t["duration_s"] == 135 and "+50% time" in t["label"]


def test_motion_by_consent_starts_moderated_caucus(coord, app):
    com = ga(app)
    s = _open(coord, app, com)
    mod = db_one(app, "SELECT pm.id FROM procedure_motion pm JOIN committee cm ON cm.procedure_rule_set_id = pm.rule_set_id WHERE cm.id = ? AND pm.code = 'mod'", (com["id"],))
    m1, m2 = member_of(app, com["id"])[:2]
    c1 = join_as(app, m1["student_id"])
    c1.get(f"/live/{s['id']}")
    c1.post(f"/live/{s['id']}/motion", {"procedure_motion_id": mod["id"], "duration_min": "5", "speaking_time_s": "45", "topic": "Finance"})
    mo = db_one(app, "SELECT * FROM motion WHERE session_id = ?", (s["id"],))
    r = coord.post(f"/chair/{s['id']}/motions/{mo['id']}", {"action": "consent"})
    assert r.status_code == 400 and "needs a second" in r.text
    c2 = join_as(app, m2["student_id"])
    c2.get(f"/live/{s['id']}")
    c2.post(f"/live/{s['id']}/second/{mo['id']}")
    coord.post(f"/chair/{s['id']}/motions/{mo['id']}", {"action": "consent"})
    ls = db_one(app, "SELECT * FROM live_session WHERE id = ?", (s["id"],))
    assert ls["mode"] == "moderated" and ls["speaking_time_s"] == 45 and ls["mode_topic"] == "Finance"
    t = db_one(app, "SELECT * FROM timer WHERE session_id = ? AND kind = 'caucus'", (s["id"],))
    assert t["duration_s"] == 300 and t["state"] == "running"


def test_division_with_computed_delegations_records_calibration(coord, app):
    com = ga(app)        # 31 delegations, 25 students -> 6 computed
    s = _open(coord, app, com)
    para = db_one(app, "SELECT p.id FROM paragraph p JOIN resolution r ON r.id = p.resolution_id WHERE r.committee_id = ? AND p.kind='operative' AND p.position=3", (com["id"],))["id"]
    coord.post(f"/chair/{s['id']}/divisions", {"target": f"paragraph:{para}"})
    dv = db_one(app, "SELECT * FROM division WHERE session_id = ?", (s["id"],))
    computed = db_rows(app, "SELECT * FROM division_vote WHERE division_id = ? AND computed = 1", (dv["id"],))
    assert len(computed) == 6 and dv["prediction_id"]
    humans = member_of(app, com["id"])
    seen = set()
    for i, m in enumerate(humans):
        if m["delegation_id"] in seen:
            continue
        seen.add(m["delegation_id"])
        c = join_as(app, m["student_id"])
        c.get(f"/live/{s['id']}")
        assert c.post(f"/live/{s['id']}/vote", {"vote": "yes" if i % 4 else "no"}).status_code == 200
    # a computed delegation can't be voted for by the chair
    r = coord.post(f"/chair/{s['id']}/divisions/{dv['id']}", {"action": "vote", "delegation_id": computed[0]["delegation_id"], "vote": "no"})
    assert r.status_code == 400 and "voted by the engine" in r.text
    r = coord.post(f"/chair/{s['id']}/divisions/{dv['id']}", {"action": "close"})
    assert "Result:" in r.text and "computed by the engine" in r.text
    dv = db_one(app, "SELECT * FROM division WHERE id = ?", (dv["id"],))
    assert dv["computed"] == 6 and dv["yes"] + dv["no"] + dv["abstain"] == 31
    actual = db_rows(app, "SELECT * FROM actual_vote WHERE target_kind = 'paragraph' AND target_id = ?", (para,))
    assert len(actual) == 25 and all(a["prediction_id"] == dv["prediction_id"] for a in actual)   # human votes only


def test_security_council_veto_live(coord, app):
    """3 students in a 15-member Security Council: 12 computed; a P5 'no' vetoes."""
    com = sc(app)
    s = _open(coord, app, com)
    para = db_one(app, "SELECT p.id FROM paragraph p JOIN resolution r ON r.id = p.resolution_id WHERE r.committee_id = ? AND p.kind='operative' LIMIT 1", (com["id"],))["id"]
    coord.post(f"/chair/{s['id']}/divisions", {"target": f"paragraph:{para}"})
    dv = db_one(app, "SELECT * FROM division WHERE session_id = ?", (s["id"],))
    assert db_one(app, "SELECT COUNT(*) AS n FROM division_vote WHERE division_id = ? AND computed = 1", (dv["id"],))["n"] == 12
    # Force a P5 'no' to check the veto is applied to whatever the computed votes are
    with app.state.db.read() as conn:
        conn.execute("UPDATE division_vote SET vote = 'yes' WHERE division_id = ?", (dv["id"],))
        conn.execute("UPDATE division_vote SET vote = 'no' WHERE division_id = ? AND iso3 = 'RUS'", (dv["id"],))
        conn.commit()
    for m in member_of(app, com["id"]):
        c = join_as(app, m["student_id"])
        c.get(f"/live/{s['id']}")
        c.post(f"/live/{s['id']}/vote", {"vote": "yes"})
    r = coord.post(f"/chair/{s['id']}/divisions/{dv['id']}", {"action": "close"})
    assert "vetoed by RUS" in r.text and "failed" in r.text


@pytest.mark.parametrize("n_students", [1, 2, 3])
def test_small_groups_procedural_vote(coord, app, n_students):
    """Procedural votes count only delegations with students; SC's 9-vote minimum is scaled to the group (D-040)."""
    com = sc(app)
    mem = member_of(app, com["id"])
    for extra in mem[n_students:]:
        db_row = db_one(app, "SELECT id FROM delegation_member WHERE student_id = ? AND delegation_id = ?", (extra["student_id"], extra["delegation_id"]))
        coord.post(f"/mun/members/{db_row['id']}/remove")
    mem = member_of(app, com["id"])
    assert len(mem) == n_students
    s = _open(coord, app, com)
    unmod = db_one(app, "SELECT pm.id FROM procedure_motion pm JOIN committee cm ON cm.procedure_rule_set_id = pm.rule_set_id WHERE cm.id = ? AND pm.code = 'unmod'", (com["id"],))
    coord.post(f"/chair/{s['id']}/motions", {"procedure_motion_id": unmod["id"], "proposer_delegation_id": mem[0]["delegation_id"], "duration_min": "3"})
    mo = db_one(app, "SELECT * FROM motion WHERE session_id = ?", (s["id"],))
    seconder = mem[1]["delegation_id"] if n_students > 1 else db_one(app, "SELECT id FROM delegation WHERE committee_id = ? AND iso3 = 'FRA'", (com["id"],))["id"]
    coord.post(f"/chair/{s['id']}/motions/{mo['id']}", {"action": "second", "delegation_id": seconder})
    coord.post(f"/chair/{s['id']}/motions/{mo['id']}", {"action": "vote"})
    dv = db_one(app, "SELECT * FROM division WHERE session_id = ?", (s["id"],))
    for m in mem:
        c = join_as(app, m["student_id"])
        c.get(f"/live/{s['id']}")
        assert c.post(f"/live/{s['id']}/vote", {"vote": "yes"}).status_code == 200
    r = coord.post(f"/chair/{s['id']}/divisions/{dv['id']}", {"action": "close"})
    assert "passed" in r.text
    assert db_one(app, "SELECT mode FROM live_session WHERE id = ?", (s["id"],))["mode"] == "unmoderated"


def test_solo_student_substantive_vote(coord, app):
    """One student, 14 computed delegations: the vote still runs and the result is under SC rules."""
    com = sc(app)
    mem = member_of(app, com["id"])
    for extra in mem[1:]:
        row = db_one(app, "SELECT id FROM delegation_member WHERE student_id = ? AND delegation_id = ?", (extra["student_id"], extra["delegation_id"]))
        coord.post(f"/mun/members/{row['id']}/remove")
    s = _open(coord, app, com)
    para = db_one(app, "SELECT p.id FROM paragraph p JOIN resolution r ON r.id = p.resolution_id WHERE r.committee_id = ? AND p.kind='operative' LIMIT 1", (com["id"],))["id"]
    coord.post(f"/chair/{s['id']}/divisions", {"target": f"paragraph:{para}"})
    c = join_as(app, mem[0]["student_id"])
    c.get(f"/live/{s['id']}")
    c.post(f"/live/{s['id']}/vote", {"vote": "abstain"})
    dv = db_one(app, "SELECT * FROM division WHERE session_id = ?", (s["id"],))
    r = coord.post(f"/chair/{s['id']}/divisions/{dv['id']}", {"action": "close"})
    dv = db_one(app, "SELECT * FROM division WHERE id = ?", (dv["id"],))
    assert dv["computed"] == 14 and dv["status"] == "closed" and dv["yes"] + dv["no"] + dv["abstain"] == 15


def test_25_student_cap(coord, app):
    com = ga(app)
    cls = com["class_id"]
    coord.post(f"/people/classes/{cls}/students", {"names": "Extra"})
    extra = db_one(app, "SELECT id FROM student WHERE class_id = ? AND first_name = 'Extra'", (cls,))["id"]
    s = _open(coord, app, com)
    ids = [r["id"] for r in db_rows(app, "SELECT id FROM student WHERE class_id = ? AND id != ? ORDER BY id", (cls, extra))]
    assert len(ids) == 25
    for sid in ids:
        assert join_as(app, sid).get(f"/live/{s['id']}").status_code == 200
    r = join_as(app, extra).get(f"/live/{s['id']}")
    assert r.status_code == 409 and "full" in r.text and "25" in r.text
    # already-admitted students can still come back
    assert join_as(app, ids[0]).get(f"/live/{s['id']}").status_code == 200


def test_minutes_generated_edited_and_exported(coord, app):
    com = ga(app)
    s = _open(coord, app, com)
    d = db_one(app, "SELECT id FROM delegation WHERE committee_id = ? AND iso3 = 'FJI'", (com["id"],))["id"]
    coord.post(f"/chair/{s['id']}/speakers", {"delegation_id": d})
    coord.post(f"/chair/{s['id']}/next")
    para = db_one(app, "SELECT p.id FROM paragraph p JOIN resolution r ON r.id = p.resolution_id WHERE r.committee_id = ? AND p.kind='operative' LIMIT 1", (com["id"],))["id"]
    coord.post(f"/chair/{s['id']}/divisions", {"target": f"paragraph:{para}"})
    dv = db_one(app, "SELECT id FROM division WHERE session_id = ?", (s["id"],))["id"]
    coord.post(f"/chair/{s['id']}/divisions/{dv}", {"action": "close"})
    r = coord.get(f"/chair/{s['id']}/minutes")
    assert "Fiji spoke" in r.text and "Division — Operative paragraph 1" in r.text
    coord.post(f"/chair/{s['id']}/minutes", {"body": "Edited minutes."})
    assert db_one(app, "SELECT body FROM minutes WHERE session_id = ? ORDER BY version DESC LIMIT 1", (s["id"],))["body"] == "Edited minutes."
    r = coord.get(f"/chair/{s['id']}/minutes.docx")
    assert r.status_code == 200 and r.content[:2] == b"PK"


def test_projector_needs_token_only(app, coord, client):
    com = ga(app)
    s = _open(coord, app, com)
    assert client.get(f"/projector/{s['projector_token']}").status_code == 200
    assert client.get("/projector/not-a-token").status_code == 404
    assert client.get(f"/chair/{s['id']}", follow_redirects=False).status_code == 303
