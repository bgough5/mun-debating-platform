"""D-096: scoring. Model UN contributions start at 0 each session and only count up, from what happens in the committee
(capped) plus the Chair's own awards with a reason; each student sees only their own. Debating marks are a teacher's:
only staff enter ballots, and house points are entered by hand."""
from app.db import SYSTEM
from app.modules.chair import service as C
from app.modules.mun import points as PTS
from tests.api.helpers import join_as
from tests.conftest import db_one, db_rows


def start(app, coord, n=4):
    ids = [r["id"] for r in db_rows(app, "SELECT id FROM student WHERE active = 1 ORDER BY id LIMIT ?", (n,))]
    r = coord.post("/start", {"op": "start", "kind": "evatt", "country_mode": "random", "student_id": [str(i) for i in ids]},
                   follow_redirects=False)
    sid = int(r.headers["location"].rsplit("/", 1)[1])
    return sid, ids


def total(app, sid, student_id):
    with app.state.db.read() as conn:
        return PTS.mine(conn, sid, student_id)


def test_everyone_starts_at_zero_and_only_sees_their_own(app, coord):
    sid, ids = start(app, coord)
    a = join_as(app, ids[0])
    page = a.get(f"/live/{sid}").text
    assert "Your contributions: 0" in page and "Only you and your teacher see this" in page
    a.post(f"/live/{sid}/roll", {"status": "present"})
    a.post(f"/live/{sid}/roll", {"status": "present_and_voting"})                 # answering again doesn't count twice
    t = total(app, sid, ids[0])
    assert t["total"] == 1 and t["strands"]["procedure"] == 1
    assert "Your contributions: 1" in a.get(f"/live/{sid}").text
    assert total(app, sid, ids[1])["total"] == 0                                    # others still on 0


def test_speeches_count_up_to_a_cap(app, coord):
    sid, ids = start(app, coord)
    did = db_one(app, "SELECT delegation_id FROM delegation_member dm JOIN delegation d ON d.id = dm.delegation_id "
                      "JOIN live_session s ON s.committee_id = d.committee_id WHERE s.id = ? AND dm.student_id = ?", (sid, ids[0]))["delegation_id"]
    for _ in range(5):
        with app.state.db.write(SYSTEM) as w:
            C.add_speaker(w, sid, did, ids[0])
            C.next_speaker(w, sid)
        with app.state.db.write(SYSTEM) as w:
            C.next_speaker(w, sid)                                                  # their speech is done
    t = total(app, sid, ids[0])
    rule = PTS.RULES["speech"]
    assert t["strands"]["speaking"] == rule[2] * rule[3]                            # five speeches, capped at three


def test_the_chair_adds_points_with_a_reason(app, coord):
    sid, ids = start(app, coord)
    page = coord.get(f"/chair/{sid}/contributions").text
    assert "Contributions:" in page and "Add points" in page and "How points are counted" in page
    assert f"/chair/{sid}/contributions" in coord.get(f"/chair/{sid}").text
    r = coord.post(f"/chair/{sid}/contributions", {"op": "award", "student_id": str(ids[0]), "strand": "negotiation", "points": "2",
                                                   "reason": "brought a quiet bloc in"})
    assert r.status_code == 200
    assert total(app, sid, ids[0])["total"] == 2
    a, b = join_as(app, ids[0]), join_as(app, ids[1])
    assert "brought a quiet bloc in" in a.get(f"/live/{sid}").text
    assert "brought a quiet bloc in" not in b.get(f"/live/{sid}").text            # no one else sees it
    assert coord.post(f"/chair/{sid}/contributions", {"op": "award", "student_id": str(ids[0]), "strand": "negotiation",
                                                      "points": "5", "reason": "too many"}).status_code >= 400
    assert coord.post(f"/chair/{sid}/contributions", {"op": "award", "student_id": str(ids[0]), "strand": "speaking",
                                                      "points": "1", "reason": ""}).status_code >= 400
    assert a.get(f"/chair/{sid}/contributions").status_code in (303, 403)          # staff only
    aw = db_one(app, "SELECT id FROM mun_award WHERE session_id = ?", (sid,))["id"]
    coord.post(f"/chair/{sid}/contributions", {"op": "withdraw", "award_id": str(aw)})
    assert total(app, sid, ids[0])["total"] == 0


def test_the_engine_and_casting_the_vote_earn_nothing(app, coord):
    sid, ids = start(app, coord)
    coord.post(f"/chair/{sid}/roll", {"action": "computed"})                       # engine answers for empty countries
    with app.state.db.read() as conn:
        t = PTS.tally(conn, sid)
    assert set(t) <= set(ids) and all(v["total"] == 0 for v in t.values())


def test_erasing_a_student_removes_their_awards(app, coord):
    sid, ids = start(app, coord, n=2)
    coord.post(f"/chair/{sid}/contributions", {"op": "award", "student_id": str(ids[0]), "strand": "speaking", "points": "1",
                                               "reason": "clear yield"})
    from app.retention import erase_student
    with app.state.db.write(SYSTEM) as w:
        erase_student(w, ids[0])
    assert not db_one(app, "SELECT 1 AS x FROM mun_award WHERE student_id = ?", (ids[0],))


def test_debating_ballots_are_teachers_and_show_running_totals(app, coord):
    p = db_one(app, "SELECT p.id FROM pairing p WHERE p.neg_team_id IS NOT NULL AND p.deleted_at IS NULL LIMIT 1")
    page = coord.get(f"/debating/pairings/{p['id']}/ballot").text
    assert "data-ballot" in page and "data-speaker-total" in page and "data-team-total" in page and "data-ballot-margin" in page
    ev = db_one(app, "SELECT r.event_id FROM pairing p JOIN debate_round r ON r.id = p.round_id WHERE p.id = ?", (p["id"],))["event_id"]
    results = coord.get(f"/debating/events/{ev}/results").text
    assert "Award for all rounds" not in results and "Award final placings" not in results and "entered by hand" in results
    assert coord.post(f"/debating/events/{ev}/housepoints", {"action": "final"}).status_code >= 400
