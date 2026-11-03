"""Phase 3: debating end to end — setup, draws, ballots, ladder, house points, documents, practice, access."""
import time

from tests.api.helpers import join_as
from tests.conftest import db_one, db_rows


def test_carnival_325_students_end_to_end(coord, app):
    """Spec Phase 3 exit: a 325-student carnival generated from fake data runs end to end."""
    from app.db import SYSTEM
    from app.modules.debating import service as S
    from app.modules.debating.demo import make_carnival
    t0 = time.perf_counter()
    with app.state.db.write(SYSTEM) as w:
        info = make_carnival(w, n_students=325, n_rounds=4, seed=7)
    seconds = time.perf_counter() - t0
    eid = info["event_id"]
    assert info["students"] == 325
    members = db_one(app, "SELECT COUNT(DISTINCT tm.student_id) AS n FROM team_member tm JOIN team t ON t.id = tm.team_id "
                          "WHERE t.event_id = ? AND tm.deleted_at IS NULL", (eid,))["n"]
    assert members == 325                         # every student is in a team (leftovers become reserves)
    teams = db_one(app, "SELECT COUNT(*) AS n FROM team WHERE event_id = ?", (eid,))["n"]
    same_house_teams = db_one(app, "SELECT COUNT(*) AS n FROM team t WHERE t.event_id = ? AND EXISTS (SELECT 1 FROM team_member tm "
                                   "JOIN student st ON st.id = tm.student_id WHERE tm.team_id = t.id AND st.house_id != t.house_id)", (eid,))["n"]
    assert same_house_teams == 0                  # one house per team
    rounds = db_rows(app, "SELECT * FROM debate_round WHERE event_id = ? ORDER BY number", (eid,))
    assert len(rounds) == 4 and rounds[0]["kind"] == "random" and rounds[1]["kind"] == "power"
    # every debate has a ballot; no repeat pairings; no same-house debates
    pairs = db_rows(app, "SELECT p.* FROM pairing p JOIN debate_round r ON r.id = p.round_id WHERE r.event_id = ? AND p.deleted_at IS NULL", (eid,))
    debates = [p for p in pairs if p["neg_team_id"]]
    keys = [frozenset((p["aff_team_id"], p["neg_team_id"])) for p in debates]
    assert len(keys) == len(set(keys))
    with app.state.db.read() as conn:
        assert all(S.pairing_result(conn, p["id"]) for p in debates)
        houses = {t["id"]: t["house_id"] for t in db_rows(app, "SELECT id, house_id FROM team WHERE event_id = ?", (eid,))}
        assert not [p for p in debates if houses[p["aff_team_id"]] == houses[p["neg_team_id"]]]
        ladder = S.ladder(conn, eid)
        tab = S.speaker_tab(conn, eid)
        totals = S.house_totals(conn, eid)
    assert len(ladder) == teams and ladder[0]["wins"] >= ladder[-1]["wins"]
    assert len(tab) >= 300                       # speakers who were scored (reserves may not speak)
    entries = db_one(app, "SELECT SUM(points) AS s FROM house_points_entry WHERE event_id = ?", (eid,))["s"]
    assert abs(sum(h["points"] for h in totals) - entries) < 1e-9
    # documents and pages render
    for kind in ("run_sheet", "mc_script"):
        r = coord.get(f"/debating/events/{eid}/documents/{kind}")
        assert r.status_code == 200 and "Round 4" in r.text.replace("ROUND 4", "Round 4")
    for url in (f"/debating/events/{eid}", f"/debating/events/{eid}/results", f"/debating/rounds/{rounds[3]['id']}", f"/debating/events/{eid}/setup"):
        assert coord.get(url).status_code == 200, url
    print(f"\ncarnival: 325 students, {teams} teams, {len(debates)} debates over 4 rounds in {seconds:.1f} s")
    assert seconds < 120


def _class_event(coord, app):
    cls = db_one(app, "SELECT id FROM class WHERE name LIKE 'Year 8%'")["id"]
    fmt = db_one(app, "SELECT id FROM debate_format WHERE code = 'small_2v2'")["id"]
    coord.post("/debating/events", {"name": "Test event", "kind": "class", "format_id": fmt, "class_id": cls})
    eid = db_one(app, "SELECT id FROM debate_event WHERE name = 'Test event'")["id"]
    coord.post(f"/debating/events/{eid}/setup", {"action": "auto_teams", "class_id": cls})
    coord.post(f"/debating/events/{eid}/setup", {"action": "rooms", "count": "6"})
    coord.post(f"/debating/events/{eid}/setup", {"action": "adjudicator", "name": "Ms Adj", "rating": "8"})
    return eid, cls


def test_round_ballot_validation_and_ladder(coord, app):
    eid, cls = _class_event(coord, app)
    r = coord.post(f"/debating/events/{eid}/rounds", {"motion": "That zoos do more harm than good"})
    assert r.status_code == 200 and "Draw generated" in r.text
    rid = db_one(app, "SELECT id FROM debate_round WHERE event_id = ?", (eid,))["id"]
    p = db_one(app, "SELECT * FROM pairing WHERE round_id = ? AND neg_team_id IS NOT NULL ORDER BY position LIMIT 1", (rid,))
    crit = db_rows(app, "SELECT rc.* FROM rubric_criterion rc JOIN debate_event e ON e.rubric_id = rc.rubric_id WHERE e.id = ? ORDER BY position", (eid,))
    def form(aff_score, neg_score, winner=None, bad=None):
        f = {}
        for tid, val in ((p["aff_team_id"], aff_score), (p["neg_team_id"], neg_score)):
            for pos in (1, 2):
                for c in crit:
                    f[f"s_{tid}_{pos}_{c['id']}"] = str(min(c["max_score"], val if c["max_score"] >= val else c["max_score"]))
        if bad:
            f[f"s_{p['aff_team_id']}_1_{crit[0]['id']}"] = bad
        if winner:
            f["winner"] = str(winner)
        return f
    r = coord.post(f"/debating/pairings/{p['id']}/ballot", form(30, 25, bad="99"))
    assert r.status_code == 400 and "between" in r.text
    r = coord.post(f"/debating/pairings/{p['id']}/ballot", form(30, 25, winner=p["neg_team_id"]))
    assert r.status_code == 400 and "higher total" in r.text
    r = coord.post(f"/debating/pairings/{p['id']}/ballot", form(30, 30))
    assert r.status_code == 400 and "level" in r.text
    r = coord.post(f"/debating/pairings/{p['id']}/ballot", form(30, 30, winner=p["neg_team_id"]))
    assert r.status_code == 200
    r = coord.post(f"/debating/pairings/{p['id']}/ballot", form(32, 25))      # replaces the earlier ballot
    assert db_one(app, "SELECT COUNT(*) AS n FROM ballot WHERE pairing_id = ? AND deleted_at IS NULL", (p["id"],))["n"] == 1
    from app.modules.debating import service as S
    with app.state.db.read() as conn:
        lad = S.ladder(conn, eid)
    winner = next(t for t in lad if t["team_id"] == p["aff_team_id"])
    assert winner["wins"] == 1 and winner["rank"] == 1
    # power pairing refuses while results are missing
    r = coord.post(f"/debating/events/{eid}/rounds", {"kind": "power"})
    assert r.status_code == 400 and "no ballot yet" in r.text


def test_panel_majority_and_chair_casting(app):
    from app.db import SYSTEM
    from app.modules.debating import service as S
    from tests.conftest import db_one as one_
    with app.state.db.write(SYSTEM) as w:
        fmt = one_(app, "SELECT id FROM debate_format WHERE code = 'duo_1v1'")["id"]
        eid = S.create_event(w, "Panel test", "competition", fmt)
        sids = [r["id"] for r in w.conn.execute("SELECT id FROM student LIMIT 2")]
        a = S.add_team(w, eid, "A", None, [sids[0]])
        b = S.add_team(w, eid, "B", None, [sids[1]])
        adj = [S.add_adjudicator(w, eid, f"J{i}", 5) for i in range(3)]
        rid = w.insert("debate_round", {"event_id": eid, "number": 1, "kind": "random", "seed": 1, "created_at": "x"})
        pid = w.insert("pairing", {"round_id": rid, "aff_team_id": a, "neg_team_id": b, "position": 1})
        for i, aid in enumerate(adj):
            w.insert("pairing_adjudicator", {"pairing_id": pid, "adjudicator_id": aid, "role": "chair" if i == 0 else "panel"})
        crit = S.criteria(w.conn, S.get_event(w.conn, eid)["rubric_id"])

        def ballot(aid, sa, sb):
            S.submit_ballot(w, pid, aid, {(a, 1): {c["id"]: sa for c in crit}, (b, 1): {c["id"]: sb for c in crit}}, {}, None)
        ballot(adj[0], 15, 18)       # chair: B
        ballot(adj[1], 18, 15)       # A
        ballot(adj[2], 19, 15)       # A  -> 2-1 to A
        res = S.pairing_result(w.conn, pid)
        assert res["winner"] == a and res["split"] == "2–1"
        w.soft_delete("ballot", w.conn.execute("SELECT id FROM ballot WHERE adjudicator_id = ?", (adj[2],)).fetchone()[0])
        assert S.pairing_result(w.conn, pid)["winner"] == b      # 1-1: the chair's ballot decides


def test_house_points_reversible_and_attributed(coord, app):
    from app.db import SYSTEM
    from app.modules.debating.demo import make_carnival
    with app.state.db.write(SYSTEM) as w:
        eid = make_carnival(w, n_students=24, n_rounds=2, seed=3)["event_id"]
    e = db_one(app, "SELECT * FROM house_points_entry WHERE event_id = ? ORDER BY id LIMIT 1", (eid,))
    before = db_one(app, "SELECT SUM(points) AS s FROM house_points_entry WHERE event_id = ? AND house_id = ?", (eid, e["house_id"]))["s"]
    coord.post(f"/debating/events/{eid}/housepoints", {"action": "reverse", "entry_id": e["id"], "reason": "scoring error"})
    after = db_one(app, "SELECT SUM(points) AS s FROM house_points_entry WHERE event_id = ? AND house_id = ?", (eid, e["house_id"]))["s"]
    assert after == before - e["points"]
    rev = db_one(app, "SELECT * FROM house_points_entry WHERE reverses_id = ?", (e["id"],))
    assert rev["entered_by"] == "Coordinator" and "scoring error" in rev["reason"]
    # house points are entered by hand now (D-096): the automatic award is refused and adds nothing
    assert coord.post(f"/debating/events/{eid}/housepoints", {"action": "all_rounds"}).status_code >= 400
    assert db_one(app, "SELECT SUM(points) AS s FROM house_points_entry WHERE event_id = ? AND house_id = ?", (eid, e["house_id"]))["s"] == after


def test_practice_small_groups(coord, app):
    cls = db_one(app, "SELECT id FROM class WHERE name LIKE 'Lunchtime%'")["id"]
    sids = [r["id"] for r in db_rows(app, "SELECT id FROM student WHERE class_id = ? ORDER BY id", (cls,))]
    # 3 students: 1 v 1 with a student adjudicator
    r = coord.post("/debating/practice", {"class_id": cls, "student_id": [str(s) for s in sids]})
    assert r.status_code == 200 and "Practice set up: 1 room" in r.text
    ev = db_one(app, "SELECT * FROM debate_event WHERE kind = 'practice' ORDER BY id DESC LIMIT 1")
    assert db_one(app, "SELECT COUNT(*) AS n FROM adjudicator WHERE event_id = ? AND student_id IS NOT NULL", (ev["id"],))["n"] == 1
    # 2 students: 1 v 1, no adjudicator
    coord.post("/debating/practice", {"class_id": cls, "student_id": [str(s) for s in sids[:2]]})
    ev2 = db_one(app, "SELECT * FROM debate_event WHERE kind = 'practice' ORDER BY id DESC LIMIT 1")
    assert db_one(app, "SELECT COUNT(*) AS n FROM team WHERE event_id = ?", (ev2["id"],))["n"] == 2
    # 1 student: solo speech practice
    r = coord.post("/debating/practice", {"class_id": cls, "student_id": [str(sids[0])]})
    assert "solo speech practice" in r.text


def test_only_staff_enter_ballots_and_student_sees_own_scores(coord, app):
    ev = db_one(app, "SELECT * FROM debate_event WHERE name LIKE 'Year 8 class debates%'")
    adj = db_one(app, "SELECT a.*, pa.pairing_id FROM adjudicator a JOIN pairing_adjudicator pa ON pa.adjudicator_id = a.id "
                      "WHERE a.event_id = ? AND a.student_id IS NOT NULL LIMIT 1", (ev["id"],))
    if adj:
        c = join_as(app, adj["student_id"])                # every mark is a teacher's judgement (D-096): not even their own debate
        assert c.get(f"/debating/pairings/{adj['pairing_id']}/ballot").status_code == 403
        assert "give your marks to your teacher" in c.get("/me").text
    speaker = db_one(app, "SELECT bs.speaker_student_id FROM ballot_score bs WHERE bs.speaker_student_id IS NOT NULL LIMIT 1")["speaker_student_id"]
    c = join_as(app, speaker)
    page = c.get("/me").text
    assert "My scores against the rubric" in page and "Matter" in page
    assert c.get("/debating").status_code == 403 and c.get(f"/debating/events/{ev['id']}/results").status_code in (303, 403)


def test_solo_speech_practice_counts_toward_pathway(app):
    sid = db_one(app, "SELECT id FROM student ORDER BY id LIMIT 1")["id"]
    c = join_as(app, sid)
    page = c.get("/me/practice")
    assert page.status_code == 200 and "Practise a speech" in page.text
    crit = db_rows(app, "SELECT rc.id FROM rubric_criterion rc JOIN rubric r ON r.id = rc.rubric_id WHERE r.kind = 'speech'")
    data = {"topic": "That zoos do more harm than good", "target_seconds": "180", "actual_seconds": "171", "reflection": "Slow down."}
    data.update({f"c_{x['id']}": "3" for x in crit})
    assert c.post("/me/practice", data).status_code == 200
    assert db_one(app, "SELECT COUNT(*) AS n FROM practice_speech WHERE student_id = ?", (sid,))["n"] == 1
    assert "suggested: Recorded 1 practice speech" in c.get("/me").text


def test_debating_projector_and_live_channel(app, coord, client):
    import json
    ev = db_one(app, "SELECT * FROM debate_event WHERE name LIKE 'Year 8 class debates%'")
    r = client.get(f"/debating/projector/{ev['projector_token']}")
    assert r.status_code == 200 and "Round 1" in r.text
    with client.websocket_connect(f"/ws?projector={ev['projector_token']}") as ws:
        ws.send_text(json.dumps({"subscribe": [f"debate:{ev['id']}"]}))
        assert json.loads(ws.receive_text())["subscribed"] == [f"debate:{ev['id']}"]


def test_corrected_ballot_moves_win_points(app):
    """A corrected ballot that changes the winner reverses the old win entry and awards the new winner's house."""
    from app.db import SYSTEM
    from app.modules.debating import service as S
    from tests.conftest import db_one as one_
    with app.state.db.write(SYSTEM) as w:
        fmt = one_(app, "SELECT id FROM debate_format WHERE code = 'duo_1v1'")["id"]
        houses = [r[0] for r in w.conn.execute("SELECT id FROM house ORDER BY id LIMIT 2")]
        eid = S.create_event(w, "Correction test", "carnival", fmt)
        sids = [r[0] for r in w.conn.execute("SELECT id FROM student LIMIT 2")]
        a = S.add_team(w, eid, "A", houses[0], [sids[0]])
        b = S.add_team(w, eid, "B", houses[1], [sids[1]])
        rid = w.insert("debate_round", {"event_id": eid, "number": 1, "kind": "random", "seed": 1, "created_at": "x"})
        pid = w.insert("pairing", {"round_id": rid, "aff_team_id": a, "neg_team_id": b, "position": 1})
        crit = S.criteria(w.conn, S.get_event(w.conn, eid)["rubric_id"])

        def ballot(sa, sb):
            S.submit_ballot(w, pid, None, {(a, 1): {c["id"]: sa for c in crit}, (b, 1): {c["id"]: sb for c in crit}}, {}, None)
        ballot(18, 15)                                   # A wins
        S.award_house_points(w, eid, rid)
        ballot(15, 18)                                   # corrected: B won
        S.award_house_points(w, eid, rid)
        S.award_house_points(w, eid, rid)                # and again: nothing changes
        wins = {h: w.conn.execute("SELECT COALESCE(SUM(points), 0) FROM house_points_entry WHERE event_id = ? AND house_id = ? "
                                  "AND source_kind IN ('win', 'reversal')", (eid, h)).fetchone()[0] for h in houses}
        win_pts = w.conn.execute("SELECT points FROM house_points_rule WHERE kind = 'win'").fetchone()[0]
    assert wins == {houses[0]: 0, houses[1]: win_pts}
    rev = one_(app, "SELECT reason FROM house_points_entry WHERE event_id = ? AND source_kind = 'reversal'", (eid,))
    assert "ballot corrected" in rev["reason"]
