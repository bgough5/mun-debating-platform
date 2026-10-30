"""D-084 stage 3: activities in progress on the Dashboard, and "who's here today?" when one is resumed."""
import re

from app.db import SYSTEM
from app.fakedata import DEMO_STAFF_PASSPHRASE
from app.modules.debating import classroom as R
from tests.conftest import Client, db_one, db_rows, login_staff


def students(app, n=None, where="1=1"):
    out = [r["id"] for r in db_rows(app, f"SELECT id FROM student WHERE active = 1 AND deleted_at IS NULL AND {where} ORDER BY id")]
    return out[:n] if n else out


def start(c, kind, ids, **extra):
    r = c.post("/start", {"op": "start", "kind": kind, "student_id": [str(i) for i in ids], **extra}, follow_redirects=False)
    assert r.status_code == 303, r.text[:300]
    return int(re.search(r"/(\d+)", r.headers["location"]).group(1))


def advance(app, rid, n):
    for _ in range(n):
        with app.state.db.write(SYSTEM) as w:
            R.act(w, db_one(app, "SELECT * FROM class_run WHERE id = ?", (rid,)), "next")


def order(app, rid):
    return [(s["side"], s["position"], s["student_id"]) for s in
            db_rows(app, "SELECT * FROM class_run_speaker WHERE run_id = ? AND deleted_at IS NULL ORDER BY side, position", (rid,))]


def resume(c, what, key, ids, **extra):
    return c.post(f"/start/resume/{what}/{key}", {"op": "resume", "student_id": [str(i) for i in ids], **extra}, follow_redirects=False)


def test_dashboard_lists_unfinished_activities(app, coord):
    rid = start(coord, "speeches", students(app, 3))
    done = start(coord, "speeches", students(app, 2))
    advance(app, done, 3)                                            # past the last speaker: finished
    assert db_one(app, "SELECT status FROM class_run WHERE id = ?", (done,))["status"] == "finished"
    page = coord.get("/").text
    assert "In progress" in page and f'href="/start/resume/run/{rid}"' in page and f'href="/debating/runs/{rid}"' in page
    assert f"/start/resume/run/{done}" not in page
    sid = int(start(coord, "unaa", students(app, 5)))
    assert f'href="/start/resume/session/{sid}"' in coord.get("/").text


def test_resume_page_ticks_last_times_students(app, coord):
    ids = students(app, 4)
    rid = start(coord, "speeches", ids)
    page = coord.get(f"/start/resume/run/{rid}").text
    assert "<title>Who's here today?" in page and "Who's here today?</h1>" in page and 'class="breadcrumb"' in page
    ticked = {int(x) for x in re.findall(r'value="(\d+)" checked', page)}
    assert ticked == set(ids)


def test_speaking_round_keeps_who_has_spoken_and_reorders_the_rest(app, coord):
    ids = students(app, 5)
    rid = start(coord, "speeches", ids)
    advance(app, rid, 2)                                             # two have spoken; the third is up
    before = order(app, rid)
    spoken = [s for _, _, s in before[:2]]
    rest = [s for _, _, s in before[2:]]
    away, new = rest[0], students(app, 1, where=f"id NOT IN ({','.join(map(str, ids))})")[0]
    here = spoken[:1] + rest[1:] + [new]                          # one who spoke is away today too: they keep their place
    r = resume(coord, "run", rid, here)
    assert r.status_code == 303 and r.headers["location"] == f"/debating/runs/{rid}"
    after = order(app, rid)
    assert [s for _, _, s in after] == spoken + rest[1:] + [new]
    assert [p for _, p, _ in after] == [1, 2, 3, 4, 5]
    run = db_one(app, "SELECT * FROM class_run WHERE id = ?", (rid,))
    assert run["step"] == 2                                          # the next speaker is the first one still here
    with app.state.db.read() as conn:
        assert R.steps(run, R.speakers(conn, rid))[2]["speaker"]["student_id"] == rest[1]
    flash = coord.get(r.headers["location"]).text
    assert "2 already spoken" in flash and "1 away" in flash and "1 new" in flash


def test_debate_frees_an_away_slot_and_fills_it(app, coord):
    ids = students(app, 4)
    rid = start(coord, "debate", ids, level="junior")
    advance(app, rid, 1)                                             # first affirmative has spoken
    slots = {(side, pos): sid for side, pos, sid in order(app, rid)}
    aff1, neg1 = slots[("aff", 1)], slots[("neg", 1)]
    new = students(app, 1, where=f"id NOT IN ({','.join(map(str, ids))})")[0]
    here = [s for s in ids if s not in (aff1, neg1)] + [new]          # aff1 (spoken) and neg1 (not yet) are away
    r = resume(coord, "run", rid, here)
    assert r.status_code == 303
    after = {(side, pos): sid for side, pos, sid in order(app, rid)}
    assert after[("aff", 1)] == aff1                                 # already spoke: kept
    assert after[("neg", 1)] == new                                  # freed, then filled
    assert "given a slot" in coord.get(r.headers["location"]).text


def test_debate_says_who_did_not_fit(app, coord):
    ids = students(app, 2)
    rid = start(coord, "debate", ids)
    extra = students(app, 2, where=f"id NOT IN ({','.join(map(str, ids))})")
    r = resume(coord, "run", rid, ids + extra)
    assert "2 student(s) didn't fit" in coord.get(r.headers["location"]).text


def test_model_un_seats_newcomers_and_leaves_the_away_alone(app, coord):
    ids = students(app, 6)
    sid = start(coord, "evatt", ids)
    com = db_one(app, "SELECT committee_id FROM live_session WHERE id = ?", (sid,))["committee_id"]
    new = students(app, 2, where=f"id NOT IN ({','.join(map(str, ids))})")
    r = resume(coord, "session", sid, ids[2:] + new)
    assert r.headers["location"] == f"/chair/{sid}"
    seated = {x["student_id"] for x in db_rows(app, "SELECT dm.student_id FROM delegation_member dm JOIN delegation d ON d.id = dm.delegation_id "
                                                    "WHERE d.committee_id = ? AND dm.deleted_at IS NULL", (com,))}
    assert seated == set(ids) | set(new)                             # away students keep their country
    assert "voted by the engine" in coord.get(r.headers["location"]).text


def test_first_timers_can_be_added_while_resuming(app, coord):
    rid = start(coord, "speeches", students(app, 2))
    r = coord.post(f"/start/resume/run/{rid}", {"op": "add", "student_id": [str(i) for i in students(app, 2)],
                                                "new_names": "Juno, 10"})
    assert r.status_code == 200 and "ticked below" in r.text
    juno = db_one(app, "SELECT id, year_level FROM student WHERE first_name = 'Juno'")
    assert juno["year_level"] == 10 and re.search(rf'value="{juno["id"]}" checked', r.text)


def test_finished_and_closed_cannot_be_resumed(app, coord):
    rid = start(coord, "speeches", students(app, 1))
    advance(app, rid, 1)
    r = coord.get(f"/start/resume/run/{rid}")
    assert r.status_code == 400 and "Reopen" in r.text
    assert coord.get("/start/resume/run/99999").status_code == 404
    assert coord.get("/start/resume/nothing/1").status_code == 404


def test_staff_resume_only_what_they_run(app, coord):
    staff_id = db_one(app, "SELECT id FROM staff WHERE name = 'Demo Chair'")["id"]
    club = db_one(app, "SELECT id FROM class WHERE code = 'DEMO3C'")["id"]
    other = start(coord, "speeches", students(app, 2, where=f"class_id != {club}"))
    with app.state.db.write(None) as w:
        w.conn.execute("DELETE FROM staff_class WHERE staff_id = ? AND class_id != ?", (staff_id, club))
    t = login_staff(Client(app, base_url="http://testserver").__enter__(), staff_id, DEMO_STAFF_PASSPHRASE)
    assert t.get(f"/start/resume/run/{other}").status_code == 403
    assert resume(t, "run", other, []).status_code == 403
    assert f"/start/resume/run/{other}" not in t.get("/").text
    mine = start(t, "speeches", students(app, where=f"class_id = {club}"))
    assert f"/start/resume/run/{mine}" in t.get("/").text


def test_resume_writes_are_logged(app, coord):
    ids = students(app, 3)
    rid = start(coord, "speeches", ids)
    seq = db_one(app, "SELECT MAX(seq) AS s FROM event_log")["s"]
    resume(coord, "run", rid, ids[1:])
    assert db_rows(app, "SELECT * FROM event_log WHERE seq > ? AND entity = 'class_run_speaker'", (seq,))
