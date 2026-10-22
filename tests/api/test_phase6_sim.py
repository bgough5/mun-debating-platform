"""Phase 6: guided simulation (D-060), whip-count exercise (D-061) and practice v3."""
import json

import pytest

from app.engine.rules import GA_SIMPLE, SC_SUBSTANTIVE
from app.modules.sim import service as SIM
from tests.api.helpers import ga, join_as, member_of, sc
from tests.conftest import db_one, db_rows


def _open(coord, app, com):
    coord.post(f"/chair/committee/{com['id']}/open")
    return db_one(app, "SELECT * FROM live_session WHERE committee_id = ? AND state = 'open'", (com["id"],))


def test_stages_follow_procedure_and_scripts_are_data(coord, app):
    com = ga(app)
    s = _open(coord, app, com)
    assert s["stage"] == "roll_call"
    guide = coord.get(f"/chair/{s['id']}/guide").text
    assert "Roll call" in guide and "welcome to the " + com["name"] in guide and "What happens next" in guide
    codes = [r["code"] for r in db_rows(app, "SELECT ps.code FROM procedure_stage ps JOIN procedure_rule_set r ON r.id = ps.rule_set_id "
                                             "WHERE r.code = 'ga_simplified' ORDER BY ps.position")]
    assert codes == SIM.STAGES
    # Admin can edit the script; the chair sees the edit.
    ps = db_one(app, "SELECT ps.* FROM procedure_stage ps WHERE ps.rule_set_id = ? AND code = 'roll_call'", (com["procedure_rule_set_id"],))
    coord.post(f"/admin/t/procedure_stage/{ps['id']}", {"rule_set_id": ps["rule_set_id"], "code": "roll_call", "position": "1",
                                                        "name": "Roll call", "chair_script": "Order, order, {committee}! Majority {majority}.",
                                                        "chair_next": "x", "student_prompt": "Say present."})
    assert "Order, order, " + com["name"] + "! Majority …" in coord.get(f"/chair/{s['id']}/guide").text
    coord.post(f"/chair/{s['id']}/stage", {"stage": "agenda"})
    assert db_one(app, "SELECT stage FROM live_session WHERE id = ?", (s["id"],))["stage"] == "agenda"
    r = coord.post(f"/chair/{s['id']}/stage", {"stage": "lunch"})
    assert r.status_code == 400


def test_fill_handles_missing_and_bad_placeholders():
    assert SIM.fill("{committee} needs {majority}", {"committee": "GA", "majority": None}) == "GA needs …"
    assert SIM.fill("Unbalanced {brace", {}) == "Unbalanced {brace"


def test_roll_call_agenda_and_student_view(coord, app):
    com = ga(app)
    s = _open(coord, app, com)
    m = member_of(app, com["id"])[0]
    pupil = join_as(app, m["student_id"])
    page = pupil.get(f"/live/{s['id']}").text
    assert "What you can do now" in page and "Answer the roll" in page
    pupil.post(f"/live/{s['id']}/roll", {"status": "present_and_voting"})
    coord.post(f"/chair/{s['id']}/roll", {"action": "computed"})
    roll = db_rows(app, "SELECT * FROM roll_call WHERE session_id = ?", (s["id"],))
    mine = next(r for r in roll if r["delegation_id"] == m["delegation_id"])
    assert mine["status"] == "present_and_voting" and mine["computed"] == 0
    dels = db_rows(app, "SELECT d.id, (SELECT COUNT(*) FROM delegation_member dm WHERE dm.delegation_id = d.id AND dm.deleted_at IS NULL) AS n "
                        "FROM delegation d WHERE d.committee_id = ? AND d.deleted_at IS NULL", (com["id"],))
    assert {r["delegation_id"] for r in roll if r["computed"]} == {d["id"] for d in dels if d["n"] == 0}
    coord.post(f"/chair/{s['id']}/stage", {"stage": "agenda"})
    coord.post(f"/chair/{s['id']}/agenda", {"agenda": "Climate finance"})
    present = len([r for r in roll if r["status"] != "absent"])
    guide = coord.get(f"/chair/{s['id']}/guide").text
    assert f"With {present} delegations present, a simple majority is {present // 2 + 1}" in guide
    assert "Agenda: Climate finance" in pupil.get(f"/live/{s['id']}/f").text
    r = pupil.post(f"/live/{s['id']}/roll", {"status": "absent"})
    assert r.status_code == 400
    pupil.__exit__(None, None, None)


def _whip(coord, app, com, s, per=3):
    para = db_one(app, "SELECT p.id FROM paragraph p JOIN resolution r ON r.id = p.resolution_id WHERE r.committee_id = ? "
                       "AND p.kind = 'operative' ORDER BY p.position LIMIT 1", (com["id"],))
    coord.post(f"/chair/{s['id']}/stage", {"stage": "voting_procedure"})
    r = coord.post(f"/chair/{s['id']}/whip", {"target": f"paragraph:{para['id']}", "per_student": str(per)})
    assert r.status_code == 200, r.text[:300]
    return db_one(app, "SELECT * FROM whip_round WHERE session_id = ? ORDER BY id DESC LIMIT 1", (s["id"],)), para


def test_whip_count_scored_against_actual_votes(coord, app):
    com = ga(app)
    s = _open(coord, app, com)
    members = member_of(app, com["id"])
    rnd, para = _whip(coord, app, com, s, per=3)
    preds = db_rows(app, "SELECT * FROM whip_prediction WHERE round_id = ?", (rnd["id"],))
    students = {m["student_id"] for m in members}
    assert {p["student_id"] for p in preds} == students
    by_student = {}
    for p in preds:
        by_student.setdefault(p["student_id"], []).append(p)
    own = {m["student_id"]: m["delegation_id"] for m in members}
    assert all(len(v) == 3 and own[k] not in [p["delegation_id"] for p in v] for k, v in by_student.items())
    cover = {}
    for p in preds:
        cover[p["delegation_id"]] = cover.get(p["delegation_id"], 0) + 1
    assert max(cover.values()) - min(cover.values()) <= 1           # named delegations spread evenly
    # Two students predict; one tries a delegation that isn't theirs.
    a, b = members[0], members[1]
    ca, cb = join_as(app, a["student_id"]), join_as(app, b["student_id"])
    mine_a = [p for p in preds if p["student_id"] == a["student_id"]]
    for i, p in enumerate(mine_a):
        assert ca.post(f"/live/{s['id']}/whip/{rnd['id']}", {"delegation_id": p["delegation_id"], "vote": ["yes", "no", "abstain"][i % 3]}).status_code == 200
    not_mine = next(d for d in cover if d not in [p["delegation_id"] for p in mine_a])
    assert ca.post(f"/live/{s['id']}/whip/{rnd['id']}", {"delegation_id": not_mine, "vote": "yes"}).status_code == 403
    assert "Whip count" in ca.get(f"/live/{s['id']}/f").text
    # Opening the vote locks predictions.
    coord.post(f"/chair/{s['id']}/whip/{rnd['id']}", {"action": "open"})
    rnd = db_one(app, "SELECT * FROM whip_round WHERE id = ?", (rnd["id"],))
    assert rnd["status"] == "locked" and rnd["division_id"]
    r = cb.post(f"/live/{s['id']}/whip/{rnd['id']}", {"delegation_id": [p for p in preds if p["student_id"] == b["student_id"]][0]["delegation_id"], "vote": "yes"})
    assert r.status_code == 409
    for m in members:
        c = join_as(app, m["student_id"])
        c.post(f"/live/{s['id']}/vote", {"vote": "yes" if m["student_id"] % 2 else "no"})
        c.__exit__(None, None, None)
    coord.post(f"/chair/{s['id']}/divisions/{rnd['division_id']}", {"action": "close"})
    with app.state.db.read() as conn:
        scores = SIM.whip_scores(conn, rnd["id"])
        actual = {r["delegation_id"]: r for r in db_rows(app, "SELECT * FROM division_vote WHERE division_id = ?", (rnd["division_id"],))}
    sa = next(x for x in scores["students"] if x["student_id"] == a["student_id"])
    expect_h = sum(1 for i, p in enumerate(mine_a) if not actual[p["delegation_id"]]["computed"]
                   and actual[p["delegation_id"]]["vote"] == ["yes", "no", "abstain"][i % 3])
    expect_c = sum(1 for i, p in enumerate(mine_a) if actual[p["delegation_id"]]["computed"]
                   and actual[p["delegation_id"]]["vote"] == ["yes", "no", "abstain"][i % 3])
    assert (sa["human_ok"], sa["computed_ok"]) == (expect_h, expect_c)
    assert sa["human_n"] + sa["computed_n"] == 3
    sb = next(x for x in scores["students"] if x["student_id"] == b["student_id"])
    assert sb["missing"] == 3 and sb["accuracy"] is None
    # Debriefs: the chair sees everyone; a student sees only their own whip score and profile.
    page = coord.get(f"/chair/{s['id']}/debrief/{rnd['division_id']}").text
    assert "How the engine did on this vote" in page and "Which votes decided it" in page
    names = {x["name"] for x in scores["students"]}
    assert all(n in page for n in names)
    mine_page = ca.get(f"/live/{s['id']}/debrief/{rnd['division_id']}").text
    other = next(x["name"] for x in scores["students"] if x["student_id"] == b["student_id"])
    own_name = sa["name"]
    assert own_name + ":" in mine_page and other + ":" not in mine_page
    ca.__exit__(None, None, None)
    cb.__exit__(None, None, None)


def test_pivotal_and_veto():
    votes = {"A": "yes", "B": "yes", "C": "no", "D": "abstain"}
    piv = {p["iso3"]: p["flip_to"] for p in SIM.pivotal(GA_SIMPLE, votes, 4)}
    # 2-1 passes. A or B switching to no (or abstaining) breaks it; D's abstention becoming a no ties it 2-2, which fails;
    # C switching only widens the margin.
    assert set(piv) == {"A", "B", "D"} and piv["D"] == ["no"]
    sc_votes = {iso: "yes" for iso in ["CHN", "FRA", "RUS", "GBR", "USA", "A", "B", "C", "D"]}
    sc_votes.update({"E": "abstain", "F": "abstain", "G": "abstain", "H": "abstain", "I": "abstain", "J": "abstain"})
    piv = {p["iso3"] for p in SIM.pivotal(SC_SUBSTANTIVE, sc_votes, 15)}
    assert {"CHN", "FRA", "RUS", "GBR", "USA"} <= piv and "A" in piv and "E" not in piv


def test_fidelity_override_and_profiles(coord, app):
    com = ga(app)
    s = _open(coord, app, com)
    rnd, para = _whip(coord, app, com, s)
    coord.post(f"/chair/{s['id']}/whip/{rnd['id']}", {"action": "open"})
    did = db_one(app, "SELECT division_id FROM whip_round WHERE id = ?", (rnd["id"],))["division_id"]
    m = member_of(app, com["id"])[0]
    c = join_as(app, m["student_id"])
    c.post(f"/live/{s['id']}/vote", {"vote": "no"})
    c.__exit__(None, None, None)
    coord.post(f"/chair/{s['id']}/divisions/{did}", {"action": "close"})
    with app.state.db.read() as conn:
        d = SIM.debrief(conn, did)
    p = next(x for x in d["profiles"] if x["delegation_id"] == m["delegation_id"])
    assert p["fidelity"] in ("consistent", "inconsistent", "borderline", "unjudged") and p["coalition"] in ("won", "lost")
    coord.post(f"/chair/{s['id']}/debrief/{did}/fidelity", {"delegation_id": m["delegation_id"], "consistent": "1", "reason": "Argued well"})
    with app.state.db.read() as conn:
        p = next(x for x in SIM.debrief(conn, did)["profiles"] if x["delegation_id"] == m["delegation_id"])
    assert p["fidelity"] == "consistent" and "Argued well" in p["why"]
    assert p["profile"]["name"] == ("Statesman" if p["coalition"] == "won" else "Principled Isolate")


def test_whip_with_one_student_and_security_council(coord, app):
    com = sc(app)
    s = _open(coord, app, com)
    members = member_of(app, com["id"])
    assert 1 <= len(members) <= 3                  # the demo Security Council is a small group
    rnd, para = _whip(coord, app, com, s, per=5)
    n = db_one(app, "SELECT COUNT(*) AS n FROM whip_prediction WHERE round_id = ? AND student_id = ?", (rnd["id"], members[0]["student_id"]))["n"]
    assert n == 5
    r = coord.post(f"/chair/{s['id']}/whip", {"target": f"paragraph:{para['id']}"})
    assert r.status_code == 400 and "already running" in r.text


# ---------- practice v3 ----------

def _practice(app, student_id):
    st = db_one(app, "SELECT class_id FROM student WHERE id = ?", (student_id,))
    com = db_one(app, "SELECT * FROM committee WHERE class_id = ? LIMIT 1", (st["class_id"],))
    para = db_one(app, "SELECT p.id FROM paragraph p JOIN resolution r ON r.id = p.resolution_id WHERE r.committee_id = ? "
                       "AND p.kind = 'operative' ORDER BY p.position LIMIT 1", (com["id"],))
    iso = db_one(app, "SELECT iso3 FROM delegation WHERE committee_id = ? ORDER BY iso3 LIMIT 1", (com["id"],))["iso3"]
    return com, para, iso


def test_practice_against_computed_chamber(app):
    m = member_of(app, ga(app)["id"])[0]
    com, para, iso = _practice(app, m["student_id"])
    c = join_as(app, m["student_id"])
    evidence_before = db_one(app, "SELECT COUNT(*) AS n FROM evidence")["n"]
    events_before = db_one(app, "SELECT COUNT(*) AS n FROM event_log WHERE entity IN ('evidence', 'amendment', 'paragraph_version')")["n"]
    r = c.post("/me/sim", {"committee_id": com["id"], f"paragraph_id_{com['id']}": para["id"], f"iso3_{com['id']}": iso})
    assert r.status_code == 200 and "Lobby a delegation" in r.text
    pid = db_one(app, "SELECT id FROM sim_practice ORDER BY id DESC LIMIT 1")["id"]
    p = db_one(app, "SELECT * FROM sim_practice WHERE id = ?", (pid,))
    with app.state.db.read() as conn:
        hm1, hm2 = SIM.hidden_mandates(conn, p), SIM.hidden_mandates(conn, p)
    assert hm1 == hm2                                    # deterministic for the run
    targets = [k for k in sorted(hm1) if k != iso]
    # Lobbying a delegation played by a student is refused; the conversation limit holds.
    assert c.post(f"/me/sim/{pid}", {"action": "lobby", "iso3": iso}).status_code == 400
    for t in targets[:SIM.LOBBY_LIMIT]:
        assert c.post(f"/me/sim/{pid}", {"action": "lobby", "iso3": t}).status_code == 200
    r = c.post(f"/me/sim/{pid}", {"action": "lobby", "iso3": targets[SIM.LOBBY_LIMIT]})
    assert r.status_code == 400 and "all 5 conversations" in r.text
    lob = db_rows(app, "SELECT * FROM sim_practice_lobby WHERE practice_id = ? ORDER BY id", (pid,))
    assert all(l["heard"] for l in lob)
    # Read the first two correctly (from the hidden truth) and the third wrongly.
    truth_pos = {"yes": 1, "abstain": 0, "no": -1}
    with app.state.db.read() as conn:
        before = SIM.practice_prediction(conn, p)["result"].p_pass
    for i, l in enumerate(lob[:3]):
        v = hm1[l["iso3"]]["vote"]
        pos = truth_pos[v] if i < 2 else (-1 if v != "no" else 1)
        c.post(f"/me/sim/{pid}", {"action": "read", "lobby_id": l["id"], "position": pos, "note": "test"})
    with app.state.db.read() as conn:
        after = SIM.practice_prediction(conn, db_one(app, "SELECT * FROM sim_practice WHERE id = ?", (pid,)))["result"].p_pass
    assert before != after                               # readings move the student's whip count
    # Amend: unknown tags are ignored; at least one tag is required.
    tags = [t["code"] for t in db_rows(app, "SELECT code FROM tag WHERE topic_id = ?", (com["topic_id"],))]
    assert c.post(f"/me/sim/{pid}", {"action": "amend", "tags": ["nonsense"]}).status_code == 400
    c.post(f"/me/sim/{pid}", {"action": "amend", "tags": tags[:2]})
    assert db_one(app, "SELECT tags FROM sim_practice WHERE id = ?", (pid,))["tags"] == ",".join(tags[:2])
    c.post(f"/me/sim/{pid}", {"action": "my_vote", "vote": "yes"})
    r = c.post(f"/me/sim/{pid}", {"action": "vote"})
    assert r.status_code == 200 and "How well you read the room" in r.text
    res = json.loads(db_one(app, "SELECT result_json FROM sim_practice WHERE id = ?", (pid,))["result_json"])
    p2 = db_one(app, "SELECT * FROM sim_practice WHERE id = ?", (pid,))
    with app.state.db.read() as conn:
        truth = SIM.hidden_mandates(conn, p2)
    assert res["votes"][iso] == "yes"
    assert all(res["votes"][k] == truth[k]["vote"] for k in truth if k != iso)        # the chamber votes its hidden mandates
    reads = [x for x in res["readings"] if x["read_vote"] is not None]
    assert [x["correct"] for x in reads] == [True, True, False]       # scored against the mandate when they spoke
    assert all(x["moved_after"] == (x["then_vote"] != truth[x["iso3"]]["vote"]) for x in reads)
    # Nothing in the class's own work changed.
    assert db_one(app, "SELECT COUNT(*) AS n FROM evidence")["n"] == evidence_before
    assert db_one(app, "SELECT COUNT(*) AS n FROM event_log WHERE entity IN ('evidence', 'amendment', 'paragraph_version')")["n"] == events_before
    assert c.post(f"/me/sim/{pid}", {"action": "lobby", "iso3": targets[0]}).status_code == 400   # already voted
    c.__exit__(None, None, None)


def test_practice_is_private_and_small(app):
    ms = member_of(app, ga(app)["id"])
    a, b, c_, d = ms[0], ms[1], ms[2], ms[3]
    com, para, iso = _practice(app, a["student_id"])
    ca = join_as(app, a["student_id"])
    ca.post("/me/sim", {"committee_id": com["id"], f"paragraph_id_{com['id']}": para["id"], f"iso3_{com['id']}": iso})
    pid = db_one(app, "SELECT id FROM sim_practice ORDER BY id DESC LIMIT 1")["id"]
    cb = join_as(app, b["student_id"])
    assert cb.get(f"/me/sim/{pid}").status_code == 403
    others = [r["iso3"] for r in db_rows(app, "SELECT iso3 FROM delegation WHERE committee_id = ? AND iso3 != ? ORDER BY iso3", (com["id"], iso))]
    assert ca.post(f"/me/sim/{pid}", {"action": "add_member", "student_id": b["student_id"], "iso3": others[0]}).status_code == 200
    assert cb.get(f"/me/sim/{pid}").status_code == 200
    ca.post(f"/me/sim/{pid}", {"action": "add_member", "student_id": c_["student_id"], "iso3": others[1]})
    r = ca.post(f"/me/sim/{pid}", {"action": "add_member", "student_id": d["student_id"], "iso3": others[2]})
    assert r.status_code == 400 and "one to three" in r.text
    ca.__exit__(None, None, None)
    cb.__exit__(None, None, None)
