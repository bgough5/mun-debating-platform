"""Retention purge (D-019): soft deletes go after 30 days, history after a year."""
from app.datasets import open_dataset
from app.db import Actor, one, scalar
from app.retention import purge
from app.util import set_clock

from tests.conftest import make_settings

DAY = 86400
ME = Actor("coordinator", None, "Coordinator")


def test_purge_soft_deletes_and_old_history(tmp_path):
    t = [1_800_000_000.0]
    set_clock(lambda: t[0])
    try:
        db = open_dataset(make_settings(tmp_path, "real"), "real")
        with db.write(ME) as w:
            cid = w.insert("class", {"name": "Fake 9X", "year": 9, "code": "ABCDEF", "code_set_at": "x"})
            gone = w.insert("student", {"class_id": cid, "first_name": "Testa"})
            fresh = w.insert("student", {"class_id": cid, "first_name": "Testb"})
            w.soft_delete("student", gone)
        t[0] += 29 * DAY
        with db.write(ME) as w:
            w.soft_delete("student", fresh)
        # Day 29: nothing old enough.
        assert purge(db)["purged"] == {}
        # A soft-deleted class still holding a student is kept, not force-deleted.
        with db.write(ME) as w:
            w.soft_delete("class", cid)
        t[0] += 2 * DAY
        r = purge(db)
        assert r["purged"] == {"student": 1}
        conn = db.connect()
        try:
            assert one(conn, "SELECT id FROM student WHERE id = ?", (gone,)) is None
            assert one(conn, "SELECT id FROM student WHERE id = ?", (fresh,)) is not None
            # The history no longer holds the purged student's name.
            assert scalar(conn, "SELECT COUNT(*) FROM event_log WHERE entity='student' AND entity_id=? "
                                "AND (before_json LIKE '%Testa%' OR after_json LIKE '%Testa%')", (str(gone),)) == 0
        finally:
            conn.close()
        # A month later the class's last student is purged, then the class goes on the next run.
        t[0] += 31 * DAY
        r = purge(db)
        assert r["purged"].get("student") == 1
        assert r["kept_referenced"] == {"class": 1}     # its student was still there when the class came up
        r = purge(db)
        conn = db.connect()
        try:
            assert one(conn, "SELECT id FROM class WHERE id = ?", (cid,)) is None
            before = scalar(conn, "SELECT COUNT(*) FROM event_log")
        finally:
            conn.close()
        # After a year, every earlier history entry is gone (only the purge records remain).
        t[0] += 366 * DAY
        r = purge(db)
        assert r["event_log_deleted"] == before
        conn = db.connect()
        try:
            assert scalar(conn, "SELECT COUNT(*) FROM event_log WHERE action != 'purge'") == 0
        finally:
            conn.close()
    finally:
        set_clock(None)


def test_referenced_row_is_kept(tmp_path):
    t = [1_800_000_000.0]
    set_clock(lambda: t[0])
    try:
        db = open_dataset(make_settings(tmp_path, "real"), "real")
        with db.write(ME) as w:
            cid = w.insert("class", {"name": "Fake 9Y", "year": 9, "code": "GHJKLM", "code_set_at": "x"})
            w.insert("student", {"class_id": cid, "first_name": "Testc"})
            w.soft_delete("class", cid)
        t[0] += 31 * DAY
        r = purge(db)
        assert r["kept_referenced"] == {"class": 1}
        conn = db.connect()
        try:
            assert one(conn, "SELECT deleted_at FROM class WHERE id = ?", (cid,))["deleted_at"]
        finally:
            conn.close()
    finally:
        set_clock(None)


def test_coordinator_erases_a_student(app, coord):
    from tests.api.helpers import join_as
    from tests.conftest import db_one, db_rows
    st = db_one(app, "SELECT st.* FROM student st JOIN class c ON c.id = st.class_id WHERE c.code = 'DEMO3C' "
                     "ORDER BY st.id LIMIT 1") or db_one(app, "SELECT * FROM student ORDER BY id LIMIT 1")
    sid, name = st["id"], st["first_name"]
    pupil = join_as(app, sid)
    rubric = db_one(app, "SELECT id FROM rubric WHERE code = 'speech_practice'")["id"]
    with app.state.db.write(Actor("student", sid, name, st["class_id"])) as w:
        w.insert("practice_speech", {"student_id": sid, "rubric_id": rubric, "reflection": "My secret reflection",
                                     "created_at": "2026-10-22T00:00:00+00:00"})
    # Staff can't erase; the coordinator must confirm.
    r = coord.post(f"/people/students/{sid}", {"action": "erase"})
    assert "Tick the confirmation box" in r.text
    r = coord.post(f"/people/students/{sid}", {"action": "erase", "confirm": "yes"})
    assert r.status_code == 200 and "Student erased" in r.text
    assert db_one(app, "SELECT first_name, last_initial, active FROM student WHERE id = ?", (sid,)) == \
        {"first_name": "Erased", "last_initial": "", "active": 0}
    assert db_rows(app, "SELECT id FROM practice_speech WHERE student_id = ?", (sid,)) == []
    assert db_rows(app, "SELECT id FROM device_session WHERE student_id = ?", (sid,)) == []
    leaks = db_rows(app, "SELECT seq FROM event_log WHERE (actor_kind = 'student' AND actor_id = ? AND actor_label != 'Erased') "
                         "OR before_json LIKE '%secret reflection%' OR after_json LIKE '%secret reflection%' "
                         "OR (entity = 'student' AND entity_id = ? AND (before_json LIKE ? OR after_json LIKE ?))",
                    (sid, str(sid), f"%{name}%", f"%{name}%"))
    assert leaks == []
    # The erased student's browser is signed out.
    r = pupil.get("/me", follow_redirects=False)
    assert r.status_code in (302, 303, 401, 403)
    pupil.__exit__(None, None, None)


def test_staff_cannot_erase(app, coord):
    from tests.conftest import db_one, login_staff, new_client
    from app.fakedata import DEMO_STAFF_PASSPHRASE
    staff = db_one(app, "SELECT id FROM staff WHERE name = 'Demo Chair'")
    # A student in a class this teacher runs: only the coordinator check stops them.
    sid = db_one(app, "SELECT st.id FROM student st JOIN staff_class sc ON sc.class_id = st.class_id "
                      "WHERE sc.staff_id = ? ORDER BY st.id LIMIT 1", (staff["id"],))["id"]
    with new_client(app) as c:
        login_staff(c, staff["id"], DEMO_STAFF_PASSPHRASE)
        r = c.post(f"/people/students/{sid}", {"action": "erase", "confirm": "yes"})
        assert r.status_code == 403 and "Only the coordinator" in r.text
    assert db_one(app, "SELECT first_name FROM student WHERE id = ?", (sid,))["first_name"] != "Erased"
