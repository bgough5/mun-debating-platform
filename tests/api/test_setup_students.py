"""D-084 stage 1: one student list with year levels, first-timers added once, tournament tools hidden by default."""
import re

from app.fakedata import DEMO_STAFF_PASSPHRASE
from tests.conftest import Client, db_one, db_rows, login_staff


def test_demo_groups_mix_year_levels(app):
    for code, allowed in (("DEMO9M", {9, 10, 11}), ("DEMO3C", {7, 10, 12}), ("DEMO8D", {7, 8, 9})):
        ys = {r["year_level"] for r in db_rows(app, "SELECT st.year_level FROM student st JOIN class c ON c.id = st.class_id WHERE c.code = ?", (code,))}
        assert ys <= allowed and len(ys) >= 2, (code, ys)


def test_one_list_across_groups_filtered_by_year(app, coord):
    page = coord.get("/people/students").text
    total = db_one(app, "SELECT COUNT(*) AS n FROM student WHERE active = 1 AND deleted_at IS NULL")["n"]
    assert f"{total} students" in page
    assert "Year 9 Model UN (demo)" in page and "Year 8 Debating (demo)" in page      # from every group, in one list
    n9 = db_one(app, "SELECT COUNT(*) AS n FROM student WHERE year_level = 9 AND active = 1")["n"]
    assert f"{n9} students" in coord.get("/people/students?year=9").text or (n9 == 1 and "1 student" in coord.get("/people/students?year=9").text)


def test_first_timers_join_the_list_with_a_year_level_and_a_code(app, coord):
    r = coord.post("/people/students", {"names": "Priya\nTom K", "year_level": "11"})
    assert r.status_code == 200 and "Added 2 student(s)." in r.text
    added = db_rows(app, "SELECT st.*, c.name AS g FROM student st JOIN class c ON c.id = st.class_id WHERE first_name IN ('Priya', 'Tom')")
    assert {(a["first_name"], a["last_initial"], a["year_level"], a["g"]) for a in added} == {("Priya", "", 11, "Students"), ("Tom", "K", 11, "Students")}
    assert all(a["login_code"] for a in added)
    # Adding more later reuses the same default group.
    coord.post("/people/students", {"names": "Ana", "year_level": ""})
    assert db_one(app, "SELECT COUNT(*) AS n FROM class WHERE name = 'Students' AND deleted_at IS NULL")["n"] == 1
    assert db_one(app, "SELECT year_level FROM student WHERE first_name = 'Ana'")["year_level"] is None


def test_year_level_can_be_changed_and_is_checked(app, coord):
    st = db_one(app, "SELECT id FROM student WHERE active = 1 ORDER BY id LIMIT 1")
    r = coord.post(f"/people/students/{st['id']}", {"action": "year", "year_level": "12", "back": "/people/students?year=12"},
                   follow_redirects=False)
    assert r.headers["location"] == "/people/students?year=12"
    assert db_one(app, "SELECT year_level FROM student WHERE id = ?", (st["id"],))["year_level"] == 12
    assert coord.post(f"/people/students/{st['id']}", {"action": "year", "year_level": "13"}).status_code == 400
    coord.post(f"/people/students/{st['id']}", {"action": "year", "year_level": ""})
    assert db_one(app, "SELECT year_level FROM student WHERE id = ?", (st["id"],))["year_level"] is None


def test_cards_for_the_students_shown(app, coord):
    page = coord.get("/people/cards?year=12").text
    ys = db_rows(app, "SELECT login_code FROM student WHERE year_level = 12 AND active = 1")
    assert ys and all(f"/s/{s['login_code']}" in page for s in ys)
    other = db_one(app, "SELECT login_code FROM student WHERE year_level = 7 AND active = 1 LIMIT 1")
    assert f"/s/{other['login_code']}" not in page


def test_staff_see_their_groups_and_cannot_add_to_the_list(app):
    staff_id = db_one(app, "SELECT id FROM staff WHERE name = 'Demo Chair'")["id"]
    with app.state.db.write(None) as w:          # this teacher now has only the lunchtime club
        w.conn.execute("DELETE FROM staff_class WHERE staff_id = ? AND class_id != (SELECT id FROM class WHERE code = 'DEMO3C')", (staff_id,))
    t = login_staff(Client(app, base_url="http://testserver").__enter__(), staff_id, DEMO_STAFF_PASSPHRASE)
    page = t.get("/people/students").text
    assert "3 students" in page and "Year 9 Model UN (demo)" not in page
    assert t.post("/people/students", {"names": "Zed", "year_level": "8"}).status_code == 403


def test_tournament_tools_hidden_until_switched_on(app, coord):
    assert 'id="h-tourn"' not in coord.get("/debating").text
    coord.post("/debating/tournaments", {"show": "1"})
    page = coord.get("/debating").text
    assert 'id="h-tourn"' in page and re.search(r"Hide these tools", page)
    coord.post("/debating/tournaments", {"show": "0"})
    assert 'id="h-tourn"' not in coord.get("/debating").text


def test_only_the_coordinator_switches_tournament_tools(app):
    staff_id = db_one(app, "SELECT id FROM staff WHERE name = 'Demo Chair'")["id"]
    t = login_staff(Client(app, base_url="http://testserver").__enter__(), staff_id, DEMO_STAFF_PASSPHRASE)
    assert t.post("/debating/tournaments", {"show": "1"}).status_code == 403
    assert not app.state.settings.get("show_tournaments")
