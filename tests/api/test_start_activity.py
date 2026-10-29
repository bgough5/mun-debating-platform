"""D-084 stage 2: Start an activity. One screen for every kind, any number of students, difficulty from year levels."""
import re
from types import SimpleNamespace

from app.fakedata import DEMO_STAFF_PASSPHRASE
from app.modules.core import start as S
from tests.conftest import Client, db_one, db_rows, login_staff


def students(app, n=None, where="1=1"):
    sql = f"SELECT id FROM student WHERE active = 1 AND deleted_at IS NULL AND {where} ORDER BY id"
    out = [r["id"] for r in db_rows(app, sql)]
    return out[:n] if n else out


def go(c, kind, ids, **extra):
    return c.post("/start", {"op": "start", "kind": kind, "student_id": [str(i) for i in ids], **extra}, follow_redirects=False)


def test_page_lists_every_kind_and_students_by_year(app, coord):
    page = coord.get("/start").text
    assert "<title>Start an activity" in page and "Start an activity</h1>" in page
    for name, _ in S.KINDS.values():
        assert name in page
    assert "Year 7" in page and "Year 12" in page and "First time here?" in page
    assert len(re.findall(r'name="student_id"', page)) == len(students(app))
    assert 'href="/start"' in coord.get("/").text                     # the dashboard points here


def test_level_suggested_from_year_levels():
    assert S.suggest_level([7, 8, 8, 9]) == "junior"
    assert S.suggest_level([9, 10, 11]) == "middle"
    assert S.suggest_level([11, 12, 10]) == "senior"
    assert S.suggest_level([None, None]) == "middle"


def test_unaa_seats_any_number_and_opens_the_chair(app, coord):
    ids = students(app, 12)
    r = go(coord, "unaa", ids, level="senior")
    assert r.status_code == 303 and r.headers["location"].startswith("/chair/")
    sid = int(r.headers["location"].rsplit("/", 1)[1])
    sess = db_one(app, "SELECT * FROM live_session WHERE id = ?", (sid,))
    assert sess["speaking_time_s"] == 120
    com = db_one(app, "SELECT * FROM committee WHERE id = ?", (sess["committee_id"],))
    seated = {r["student_id"] for r in db_rows(app, "SELECT dm.student_id FROM delegation_member dm JOIN delegation d ON d.id = dm.delegation_id "
                                                    "WHERE d.committee_id = ? AND dm.deleted_at IS NULL", (com["id"],))}
    assert seated == set(ids)
    assert coord.get(r.headers["location"]).status_code == 200


def test_evatt_takes_more_students_than_seats(app, coord):
    ids = students(app, 20)
    r = go(coord, "evatt", ids, level="junior")
    sid = int(r.headers["location"].rsplit("/", 1)[1])
    com = db_one(app, "SELECT c.*, s.speaking_time_s FROM committee c JOIN live_session s ON s.committee_id = c.id WHERE s.id = ?", (sid,))
    seated = {r["student_id"] for r in db_rows(app, "SELECT dm.student_id FROM delegation_member dm JOIN delegation d ON d.id = dm.delegation_id "
                                                    "WHERE d.committee_id = ? AND dm.deleted_at IS NULL", (com["id"],))}
    assert seated == set(ids) and com["speaking_time_s"] == 60


def _run_speakers(app, rid):
    return db_rows(app, "SELECT * FROM class_run_speaker WHERE run_id = ? AND deleted_at IS NULL", (rid,))


def test_debate_for_two_odd_and_many(app, coord):
    two = students(app, 2)
    r = go(coord, "debate", two, level="junior")
    rid = int(r.headers["location"].rsplit("/", 1)[1])
    run = db_one(app, "SELECT * FROM class_run WHERE id = ?", (rid,))
    assert run["speakers_per_side"] == 1 and run["speech_seconds"] == 180 and run["reply"] == 0
    assert run["motion"] in {m["motion"] for m in db_rows(app, "SELECT motion FROM motion_bank WHERE level = 'junior'")}
    assert {s["student_id"] for s in _run_speakers(app, rid)} == set(two)

    five = students(app, 5)
    r = go(coord, "debate", five, level="senior")
    rid = int(r.headers["location"].rsplit("/", 1)[1])
    sp = _run_speakers(app, rid)
    assert len(sp) == 6 and sum(1 for s in sp if s["student_id"]) == 5      # one spare slot on the short side
    assert db_one(app, "SELECT reply FROM class_run WHERE id = ?", (rid,))["reply"] == 1
    assert "spare slot" in coord.get(r.headers["location"]).text

    many = students(app, 17)
    before = db_one(app, "SELECT COALESCE(MAX(id), 0) AS m FROM class_run")["m"]
    r = go(coord, "debate", many, level="middle")
    assert r.headers["location"] == "/debating"
    runs = db_rows(app, "SELECT * FROM class_run WHERE id > ? ORDER BY id", (before,))
    assert len(runs) == 3 and all(x["title"].startswith(f"Debate {i} of 3") for i, x in enumerate(runs, 1))
    assert len({x["motion"] for x in runs}) == 1                          # every room debates the same motion
    linked = [s["student_id"] for x in runs for s in _run_speakers(app, x["id"]) if s["student_id"]]
    assert sorted(linked) == sorted(many)
    assert {sum(1 for s in _run_speakers(app, x["id"]) if s["student_id"]) for x in runs} <= {5, 6}


def test_debate_uses_the_chosen_motion_and_needs_two(app, coord):
    m = db_one(app, "SELECT * FROM motion_bank WHERE level = 'senior' LIMIT 1")
    r = go(coord, "debate", students(app, 4), motion_id=str(m["id"]))
    run = db_one(app, "SELECT * FROM class_run WHERE id = ?", (int(r.headers["location"].rsplit("/", 1)[1]),))
    assert run["motion"] == m["motion"]
    r = coord.post("/start", {"op": "start", "kind": "debate", "student_id": [str(students(app, 1)[0])]})
    assert r.status_code == 400 and "Public speaking" in r.text


def test_public_speaking_takes_everyone_and_splits_past_thirty(app, coord):
    ids = students(app, 35)
    before = db_one(app, "SELECT COALESCE(MAX(id), 0) AS m FROM class_run")["m"]
    r = go(coord, "speeches", ids, level="middle", topic_mode="impromptu")
    runs = db_rows(app, "SELECT * FROM class_run WHERE id > ? ORDER BY id", (before,))
    assert r.headers["location"] == f"/debating/runs/{runs[0]['id']}"
    assert [len(_run_speakers(app, x["id"])) for x in runs] == [30, 5]
    assert all(x["kind"] == "speeches" and x["topic_mode"] == "impromptu" and x["speech_seconds"] == 120 for x in runs)
    assert sorted(s["student_id"] for x in runs for s in _run_speakers(app, x["id"])) == sorted(ids)


def test_suggested_difficulty_follows_who_is_ticked(app, coord):
    young = students(app, where="year_level = 7")
    r = go(coord, "speeches", young, level="suggested")
    run = db_one(app, "SELECT * FROM class_run WHERE id = ?", (int(r.headers["location"].rsplit("/", 1)[1]),))
    assert run["speech_seconds"] == 90 and run["level"] == "junior"


def test_custom_opens_the_full_settings(app, coord):
    r = go(coord, "custom", students(app, 3))
    assert re.fullmatch(r"/debating/runs/\d+/edit", r.headers["location"])
    assert coord.get(r.headers["location"]).status_code == 200


def test_first_timers_are_added_and_ticked_without_starting_anything(app, coord):
    keep = students(app, 2)
    runs = db_one(app, "SELECT COUNT(*) AS n FROM class_run")["n"]
    r = coord.post("/start", {"op": "add", "kind": "debate", "student_id": [str(i) for i in keep],
                              "new_names": "Wren\nAsh T, 11", "new_year_level": "8"})
    assert r.status_code == 200 and "Added 2 student(s)." in r.text and "ticked below" in r.text
    new = db_rows(app, "SELECT * FROM student WHERE first_name IN ('Wren', 'Ash')")
    assert {(n["first_name"], n["last_initial"], n["year_level"]) for n in new} == {("Wren", "", 8), ("Ash", "T", 11)}
    assert all(n["login_code"] for n in new)
    for sid in keep + [n["id"] for n in new]:
        assert re.search(rf'value="{sid}" checked', r.text)
    assert 'value="debate" required checked' in r.text                      # the choice made so far is kept
    assert db_one(app, "SELECT COUNT(*) AS n FROM class_run")["n"] == runs


def test_first_timers_need_a_year_level(app, coord):
    r = coord.post("/start", {"op": "add", "new_names": "Gus"})
    assert r.status_code == 400 and "year level" in r.text
    assert not db_rows(app, "SELECT id FROM student WHERE first_name = 'Gus'")


def test_page_has_find_and_year_filter(app, coord):
    page = coord.get("/start").text
    assert "data-find-name" in page and "data-find-year" in page and 'data-year="yr-9"' in page
    with app.state.db.write(None) as w:          # two students with the same name in different groups
        a, b = (db_one(app, "SELECT id FROM class WHERE code = ?", (c,))["id"] for c in ("DEMO9M", "DEMO8D"))
        for cid in (a, b):
            w.conn.execute("INSERT INTO student (class_id, first_name, last_initial, year_level) VALUES (?, 'Zadie', '', 9)", (cid,))
    page = coord.get("/start").text
    assert "Zadie <span class=\"hint\">(Year 9 Model UN (demo))" in page and "Zadie <span class=\"hint\">(Year 8 Debating (demo))" in page


def test_needs_a_kind_and_a_student(app, coord):
    assert coord.post("/start", {"op": "start", "student_id": [str(students(app, 1)[0])]}).status_code == 400
    r = coord.post("/start", {"op": "start", "kind": "speeches"})
    assert r.status_code == 400 and "Tick at least one" in r.text


def test_staff_only_tick_their_own_groups(app):
    staff_id = db_one(app, "SELECT id FROM staff WHERE name = 'Demo Chair'")["id"]
    club = db_one(app, "SELECT id FROM class WHERE code = 'DEMO3C'")["id"]
    with app.state.db.write(None) as w:
        w.conn.execute("DELETE FROM staff_class WHERE staff_id = ? AND class_id != ?", (staff_id, club))
    t = login_staff(Client(app, base_url="http://testserver").__enter__(), staff_id, DEMO_STAFF_PASSPHRASE)
    mine = students(app, where=f"class_id = {club}")
    other = students(app, 1, where=f"class_id != {club}")
    assert len(re.findall(r'name="student_id"', t.get("/start").text)) == len(mine)
    r = go(t, "speeches", mine + other)
    rid = int(r.headers["location"].rsplit("/", 1)[1])
    assert db_one(app, "SELECT class_id FROM class_run WHERE id = ?", (rid,))["class_id"] == club
    assert sorted(s["student_id"] for s in _run_speakers(app, rid)) == sorted(mine)    # the other group's student is ignored
    assert t.post("/start", {"op": "add", "new_names": "Zed"}).status_code == 403


def test_students_cannot_start_activities(app, coord):
    code = db_one(app, "SELECT login_code FROM student WHERE active = 1 LIMIT 1")["login_code"]
    s = Client(app, base_url="http://testserver").__enter__()
    s.get(f"/s/{code}")
    assert s.get("/start", follow_redirects=False).status_code in (303, 401, 403)
    assert s.post("/start", {"op": "start", "kind": "speeches"}, follow_redirects=False).status_code in (303, 401, 403)


def test_kinds_follow_the_modules_switched_on():
    only_debating = SimpleNamespace(module_on=lambda m: m == "debating")
    assert set(S.available_kinds(only_debating)) == {"debate", "speeches", "custom"}
    only_mun = SimpleNamespace(module_on=lambda m: m in ("mun", "chair"))
    assert set(S.available_kinds(only_mun)) == {"unaa", "evatt"}


def test_writes_are_logged(app, coord):
    go(coord, "speeches", students(app, 3))
    rid = db_one(app, "SELECT MAX(id) AS m FROM class_run")["m"]
    n = db_one(app, "SELECT COUNT(*) AS n FROM event_log WHERE entity = 'class_run_speaker' AND entity_id IN "
                    "(SELECT id FROM class_run_speaker WHERE run_id = ?)", (rid,))["n"]
    assert n >= 3
