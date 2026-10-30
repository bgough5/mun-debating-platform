"""D-085: saved groups. A named list of students ticked in one go; a student can be in many; shared but owner-edited."""
import re

from app.fakedata import DEMO_STAFF_PASSPHRASE
from tests.conftest import Client, db_one, db_rows, login_staff


def students(app, n=None, where="1=1"):
    out = [r["id"] for r in db_rows(app, f"SELECT id FROM student WHERE active = 1 AND deleted_at IS NULL AND {where} ORDER BY id")]
    return out[:n] if n else out


def make(c, name, ids):
    r = c.post("/people/groups", {"op": "create", "group_name": name, "student_id": [str(i) for i in ids]}, follow_redirects=False)
    assert r.status_code == 303, r.text[:300]
    return int(r.headers["location"].rsplit("/", 1)[1])


def members(app, gid):
    return {r["student_id"] for r in db_rows(app, "SELECT student_id FROM student_group_member WHERE group_id = ? AND deleted_at IS NULL", (gid,))}


def test_people_has_tabs_for_students_groups_and_access(app, coord):
    page = coord.get("/people").text
    for href in ("/people/students", "/people/groups", "/people/access", "/people/staff"):
        assert f'href="{href}"' in page
    assert "Year 9 Model UN (demo)" not in page                       # the old groups are off the People page
    assert "Year 9 Model UN (demo)" in coord.get("/people/access").text
    assert coord.get("/people/classes", follow_redirects=False).headers["location"] == "/people/access"


def test_make_a_group_and_a_student_can_be_in_two(app, coord):
    ids = students(app, 6)
    jr = make(coord, "Debating Jr BGO", ids[:4])
    club = make(coord, "MUN club", ids[2:])
    assert members(app, jr) == set(ids[:4]) and members(app, club) == set(ids[2:])
    page = coord.get("/people/groups").text
    assert "Debating Jr BGO" in page and "MUN club" in page and f'href="/start?group={jr}"' in page
    assert "<title>Debating Jr BGO" in coord.get(f"/people/groups/{jr}").text


def test_names_are_required_and_unique(app, coord):
    ids = students(app, 2)
    make(coord, "Seniors", ids)
    r = coord.post("/people/groups", {"op": "create", "group_name": "seniors ", "student_id": [str(i) for i in ids]})
    assert r.status_code == 400 and "already a group" in r.text
    assert coord.post("/people/groups", {"op": "create", "group_name": " ", "student_id": [str(ids[0])]}).status_code == 400
    assert coord.post("/people/groups", {"op": "create", "group_name": "Empty"}).status_code == 400


def test_rename_change_members_and_delete(app, coord):
    ids = students(app, 5)
    gid = make(coord, "Jr", ids[:3])
    r = coord.post(f"/people/groups/{gid}", {"op": "save", "group_name": "Juniors", "student_id": [str(i) for i in ids[1:5]]}, follow_redirects=False)
    assert r.status_code == 303
    assert db_one(app, "SELECT name FROM student_group WHERE id = ?", (gid,))["name"] == "Juniors"
    assert members(app, gid) == set(ids[1:5])
    coord.post(f"/people/groups/{gid}", {"op": "delete"})
    assert db_one(app, "SELECT deleted_at FROM student_group WHERE id = ?", (gid,))["deleted_at"]
    assert coord.get(f"/people/groups/{gid}").status_code == 404
    assert len(students(app)) >= 5                                      # the students are still on the list


def test_start_with_a_group_ticks_its_members(app, coord):
    ids = students(app, 4)
    gid = make(coord, "Debating Jr BGO", ids)
    page = coord.get(f"/start?group={gid}").text
    assert {int(x) for x in re.findall(r'value="(\d+)" checked', page)} == set(ids)
    assert f'name="tick_group" value="{gid}"' in page


def test_tick_a_group_keeps_what_was_already_chosen(app, coord):
    ids = students(app, 6)
    gid = make(coord, "Pair", ids[:2])
    r = coord.post("/start", {"tick_group": str(gid), "kind": "debate", "level": "senior", "student_id": [str(ids[5])]})
    assert r.status_code == 200 and "Ticked Pair: 2 students." in r.text
    assert {int(x) for x in re.findall(r'value="(\d+)" checked', r.text) if int(x) in ids} == {ids[0], ids[1], ids[5]}
    assert 'value="debate" required checked' in r.text and 'value="senior" checked' in r.text


def test_save_the_ticked_students_as_a_group_from_start_and_resume(app, coord):
    ids = students(app, 3)
    r = coord.post("/start", {"op": "save_group", "group_name": "Thursday lunch", "student_id": [str(i) for i in ids]})
    assert r.status_code == 200 and "Saved “Thursday lunch”: 3 students." in r.text
    gid = db_one(app, "SELECT id FROM student_group WHERE name = 'Thursday lunch'")["id"]
    assert members(app, gid) == set(ids)
    run = coord.post("/start", {"op": "start", "kind": "speeches", "student_id": [str(i) for i in ids]}, follow_redirects=False)
    rid = int(run.headers["location"].rsplit("/", 1)[1])
    r = coord.post(f"/start/resume/run/{rid}", {"tick_group": str(gid), "student_id": []})
    assert r.status_code == 200 and "Ticked Thursday lunch" in r.text
    assert 'name="group_name"' in coord.get(f"/start/resume/run/{rid}").text


def test_cards_for_a_group(app, coord):
    ids = students(app, 2)
    gid = make(coord, "Card pair", ids)
    page = coord.get(f"/people/cards?group={gid}").text
    codes = [r["login_code"] for r in db_rows(app, "SELECT login_code FROM student WHERE id IN (?, ?)", tuple(ids))]
    assert all(f"/s/{c}" in page for c in codes) and "Card pair" in page
    other = db_one(app, f"SELECT login_code FROM student WHERE id NOT IN ({ids[0]}, {ids[1]}) AND active = 1 LIMIT 1")["login_code"]
    assert f"/s/{other}" not in page


def _club_teacher(app):
    staff_id = db_one(app, "SELECT id FROM staff WHERE name = 'Demo Chair'")["id"]
    club = db_one(app, "SELECT id FROM class WHERE code = 'DEMO3C'")["id"]
    with app.state.db.write(None) as w:
        w.conn.execute("DELETE FROM staff_class WHERE staff_id = ? AND class_id != ?", (staff_id, club))
    return login_staff(Client(app, base_url="http://testserver").__enter__(), staff_id, DEMO_STAFF_PASSPHRASE), club


def test_staff_see_only_members_they_can_see_and_edit_only_their_own(app, coord):
    t, club = _club_teacher(app)
    mine_ids = students(app, where=f"class_id = {club}")
    others = students(app, 3, where=f"class_id != {club}")
    mixed = make(coord, "Mixed", mine_ids[:1] + others)                 # coordinator's group
    hidden = make(coord, "Hidden", others)
    page = t.get("/people/groups").text
    assert "Mixed" in page and "Hidden" not in page                    # no members this teacher can see
    assert t.get(f"/people/groups/{hidden}").status_code == 404
    g = t.get(f"/people/groups/{mixed}").text
    assert "Only the coordinator can change this group" in g
    assert t.post(f"/people/groups/{mixed}", {"op": "save", "group_name": "Mine now", "student_id": []}).status_code == 403
    assert t.post(f"/people/groups/{mixed}", {"op": "delete"}).status_code == 403
    # Ticking it gives only the member this teacher can see.
    r = t.post("/start", {"tick_group": str(mixed)})
    assert "Ticked Mixed: 1 student." in r.text
    # Their own group, built from students they can see; ids they can't see are ignored.
    gid = make(t, "Club", mine_ids + others)
    assert members(app, gid) == set(mine_ids)
    assert db_one(app, "SELECT staff_id FROM student_group WHERE id = ?", (gid,))["staff_id"] is not None


def test_owner_edits_leave_members_they_cannot_see(app, coord):
    t, club = _club_teacher(app)
    mine_ids = students(app, where=f"class_id = {club}")
    gid = make(t, "Club", mine_ids)
    other = students(app, 1, where=f"class_id != {club}")[0]
    with app.state.db.write(None) as w:                                # the coordinator later adds someone from elsewhere
        w.conn.execute("INSERT INTO student_group_member (group_id, student_id) VALUES (?, ?)", (gid, other))
    t.post(f"/people/groups/{gid}", {"op": "save", "group_name": "Club", "student_id": [str(mine_ids[0])]})
    assert members(app, gid) == {mine_ids[0], other}


def test_erasing_a_student_removes_them_from_groups(app, coord):
    ids = students(app, 2)
    gid = make(coord, "Erase test", ids)
    from app.retention import erase_student
    from app.db import SYSTEM
    with app.state.db.write(SYSTEM) as w:
        erase_student(w, ids[0])
    assert not db_rows(app, "SELECT id FROM student_group_member WHERE student_id = ?", (ids[0],))
    assert members(app, gid) == {ids[1]}


def test_dashboard_shows_saved_groups(app, coord):
    gid = make(coord, "Debating Jr BGO", students(app, 2))
    page = coord.get("/").text
    assert "Debating Jr BGO" in page and f'href="/start?group={gid}"' in page
