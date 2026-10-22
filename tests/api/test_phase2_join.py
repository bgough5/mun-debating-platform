"""Student join: class code + tap name, device lock, second-device approval (D-003, spec §8.4)."""
from tests.api.helpers import join_as
from tests.conftest import db_one, new_client


def _student(app):
    return db_one(app, "SELECT st.*, c.code FROM student st JOIN class c ON c.id = st.class_id WHERE c.name LIKE 'Year 9%' ORDER BY st.id LIMIT 1")


def test_join_with_code_and_name(app):
    st = _student(app)
    c = join_as(app, st["id"])
    r = c.get("/me")
    assert r.status_code == 200 and f"Hi {st['first_name']}" in r.text
    assert db_one(app, "SELECT COUNT(*) AS n FROM device_session WHERE student_id = ? AND revoked_at IS NULL", (st["id"],))["n"] == 1


def test_wrong_code_plain_english(client):
    r = client.post("/join", {"code": "ZZZZZZ"})
    assert r.status_code == 400 and "didn't match a class" in r.text


def test_second_device_needs_teacher_approval(app, coord):
    st = _student(app)
    join_as(app, st["id"])
    other = new_client(app)
    with other:
        r = other.post(f"/join/{st['code']}/{st['id']}")
        assert "Waiting for your teacher" in r.text
        assert other.get("/me", follow_redirects=False).status_code == 303   # not signed in
        req = db_one(app, "SELECT * FROM claim_request WHERE student_id = ?", (st["id"],))
        # teacher sees it and approves
        page = coord.get(f"/people/classes/{st['class_id']}").text
        assert "Second-device requests" in page
        coord.post(f"/people/classes/{st['class_id']}", {"action": "decide_claim", "request_id": req["id"], "decision": "approve"})
        r = other.get("/join/wait")
        assert r.status_code == 200 and "My page" in r.text


def test_denied_second_device(app, coord):
    st = _student(app)
    join_as(app, st["id"])
    with new_client(app) as other:
        other.post(f"/join/{st['code']}/{st['id']}")
        req = db_one(app, "SELECT * FROM claim_request WHERE student_id = ?", (st["id"],))
        coord.post(f"/people/classes/{st['class_id']}", {"action": "decide_claim", "request_id": req["id"], "decision": "deny"})
        assert "didn't approve" in other.get("/join/wait").text


def test_release_name_and_rotate_code(app, coord):
    st = _student(app)
    c = join_as(app, st["id"])
    coord.post(f"/people/students/{st['id']}", {"action": "release"})
    assert c.get("/me", follow_redirects=False).status_code == 303
    coord.post(f"/people/classes/{st['class_id']}", {"action": "rotate_code"})
    with new_client(app) as n:
        assert n.post("/join", {"code": st["code"]}).status_code == 400


def test_full_names_cut_to_initial(app, coord):
    cls = db_one(app, "SELECT id FROM class WHERE name LIKE 'Year 8%'")["id"]
    coord.post(f"/people/classes/{cls}/students", {"names": "Sam Leeworthy"})
    s = db_one(app, "SELECT first_name, last_initial FROM student WHERE class_id = ? ORDER BY id DESC LIMIT 1", (cls,))
    assert s == {"first_name": "Sam", "last_initial": "L"}
