"""Student sign-in with a personal code (D-079, replacing D-003's class code and name list): the code has the name
built in, works on any laptop, signs the student out of the previous laptop, and is throttled."""
import re

from tests.api.helpers import join_as
from tests.conftest import db_one, db_rows, new_client


def _student(app):
    return db_one(app, "SELECT st.*, c.code FROM student st JOIN class c ON c.id = st.class_id WHERE c.name LIKE 'Year 9%' ORDER BY st.id LIMIT 1")


def test_every_student_has_a_unique_code_without_lookalike_characters(app):
    codes = [r["login_code"] for r in db_rows(app, "SELECT login_code FROM student")]
    assert all(codes) and len(set(codes)) == len(codes)
    assert all(len(c) == 6 and not set(c) & set("0O1I") for c in codes)


def test_sign_in_with_your_own_link_or_code(app):
    st = _student(app)
    with new_client(app) as c:
        r = c.get(f"/s/{st['login_code']}")
        assert r.status_code == 200 and f"Welcome, {st['first_name']}" in r.text
        assert f"Hi {st['first_name']}" in c.get("/me").text
    code = st["login_code"]
    for typed in (code.lower(), f"{code[:3]}-{code[3:]}", f"http://10.0.0.5:8080/s/{code}"):
        with new_client(app) as c:
            assert c.post("/join", {"code": typed}).status_code == 200, typed


def test_no_list_of_names_and_wrong_codes_are_explained(client, app):
    st = _student(app)
    page = client.get("/join").text
    assert st["first_name"] not in page and "Your code" in page
    r = client.post("/join", {"code": "ZZZZZZ"})
    assert r.status_code == 400 and "didn't match" in r.text
    r = client.post("/join", {"code": st["code"]})                  # the class code is not a sign-in code
    assert r.status_code == 400 and "That's the class code" in r.text
    assert client.get(f"/join/{st['code']}").status_code == 404     # the old name list is gone


def test_signing_in_on_another_laptop_signs_out_the_first(app):
    st = _student(app)
    first = join_as(app, st["id"])
    second = join_as(app, st["id"])
    assert second.get("/me").status_code == 200
    assert first.get("/me", follow_redirects=False).status_code == 303
    assert db_one(app, "SELECT COUNT(*) AS n FROM device_session WHERE student_id = ? AND revoked_at IS NULL", (st["id"],))["n"] == 1


def test_teacher_gives_a_new_code_and_the_old_one_stops_working(app, coord):
    st = _student(app)
    c = join_as(app, st["id"])
    r = coord.post(f"/people/students/{st['id']}", {"action": "new_code"})
    assert "The old code no longer works" in r.text
    assert c.get("/me", follow_redirects=False).status_code == 303          # signed out
    new = db_one(app, "SELECT login_code FROM student WHERE id = ?", (st["id"],))["login_code"]
    assert new != st["login_code"]
    with new_client(app) as n:
        assert n.post("/join", {"code": st["login_code"]}).status_code == 400
        assert n.post("/join", {"code": new}).status_code == 200


def test_cards_carry_each_students_own_code_and_no_qr(app, coord):
    c = db_one(app, "SELECT * FROM class WHERE code = 'DEMO9M'")
    page = coord.get(f"/people/classes/{c['id']}/join-cards").text
    for st in db_rows(app, "SELECT first_name, login_code FROM student WHERE class_id = ? AND active = 1", (c["id"],)):
        assert f"/s/{st['login_code']}" in page and f"{st['login_code'][:3]}-{st['login_code'][3:]}" in page
    # A whole-word check: codes use Q and R, so a bare "QR" substring failed about 12% of runs by chance.
    assert "jc-qr" not in page and not re.search(r"\bQR\b", page)
    app.state.settings.values["join_base_url"] = "http://10.1.2.3:8080/"
    assert "10.1.2.3:8080/s/" in coord.get(f"/people/classes/{c['id']}/join-cards").text
    assert "10.1.2.3:8080" in coord.get(f"/people/classes/{c['id']}/poster").text
    app.state.settings.values.pop("join_base_url")


def test_new_students_get_codes_and_codes_stay_out_of_exports(app, coord):
    cls = db_one(app, "SELECT id FROM class WHERE name LIKE 'Year 8%'")["id"]
    coord.post(f"/people/classes/{cls}/students", {"names": "Sam Leeworthy"})
    s = db_one(app, "SELECT first_name, last_initial, login_code FROM student WHERE class_id = ? ORDER BY id DESC LIMIT 1", (cls,))
    assert (s["first_name"], s["last_initial"]) == ("Sam", "L") and len(s["login_code"]) == 6
    assert s["login_code"] not in coord.get("/admin/csv/student.csv").text


def test_wrong_codes_are_throttled(client):
    for _ in range(12):
        r = client.post("/join", {"code": "ZZZZZZ"})
    assert r.status_code == 429
