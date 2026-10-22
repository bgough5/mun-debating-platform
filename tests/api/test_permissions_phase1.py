"""Role-based access on the server (spec §8.3): staff see only their classes; nobody but the coordinator reaches admin."""
from tests.conftest import db_one, login_staff, new_client


def _staff(coord, app, classes):
    coord.post("/people/staff", {"action": "create", "name": "Ms Test", "passphrase": "staff passphrase 1"})
    sid = db_one(app, "SELECT id FROM staff WHERE name = 'Ms Test'")["id"]
    data = {"action": "classes", "staff_id": sid}
    r = coord.post("/people/staff", {**data, "class_id": [str(c) for c in classes]})
    assert r.status_code == 200
    return sid


def test_staff_scope(coord, app):
    mun_class = db_one(app, "SELECT id FROM class WHERE name LIKE 'Year 9%'")["id"]
    small_class = db_one(app, "SELECT id FROM class WHERE name LIKE 'Lunchtime%'")["id"]
    sid = _staff(coord, app, [small_class])
    ga = db_one(app, "SELECT id FROM committee WHERE class_id = ?", (mun_class,))["id"]
    sc = db_one(app, "SELECT id FROM committee WHERE class_id = ?", (small_class,))["id"]
    with new_client(app) as c:
        login_staff(c, sid, "staff passphrase 1")
        assert c.get(f"/mun/committees/{sc}").status_code == 200
        assert c.get(f"/mun/committees/{ga}").status_code == 403
        assert c.get(f"/people/classes/{mun_class}").status_code == 403
        assert c.get(f"/people/classes/{small_class}").status_code == 200
        assert c.get("/admin").status_code == 403
        assert c.get("/admin/csv/student.csv").status_code == 403
        assert c.post("/people/classes", {"name": "Sneaky"}).status_code == 403
        assert "Year 9" not in c.get("/people").text


def test_deactivated_staff_signed_out(coord, app):
    small_class = db_one(app, "SELECT id FROM class WHERE name LIKE 'Lunchtime%'")["id"]
    sid = _staff(coord, app, [small_class])
    with new_client(app) as c:
        login_staff(c, sid, "staff passphrase 1")
        assert c.get("/people").status_code == 200
        coord.post("/people/staff", {"action": "deactivate", "staff_id": sid})
        r = c.get("/people", follow_redirects=False)
        assert r.status_code == 303 and "/login" in r.headers["location"]


def test_anonymous_redirected_everywhere(client):
    for url in ("/mun", "/people", "/admin", "/mun/calibration", "/mun/committees/1"):
        r = client.get(url, follow_redirects=False)
        assert r.status_code == 303, url
