from tests.conftest import db_one, db_rows, new_client


def join_as(app, student_id: int):
    """A new browser that joins as the given student (code + tap name)."""
    st = db_one(app, "SELECT st.*, c.code FROM student st JOIN class c ON c.id = st.class_id WHERE st.id = ?", (student_id,))
    c = new_client(app)
    c.__enter__()
    r = c.post("/join", {"code": st["code"].lower()})
    assert r.status_code == 200, r.text[:300]
    r = c.post(f"/join/{st['code']}/{student_id}")
    assert r.status_code == 200
    return c


def ga(app):
    com = db_one(app, "SELECT * FROM committee WHERE name LIKE 'United Nations General Assembly%'")
    return com


def sc(app):
    return db_one(app, "SELECT * FROM committee WHERE name = 'Security Council'")


def member_of(app, committee_id, iso3=None):
    q = "SELECT dm.student_id, d.id AS delegation_id, d.iso3 FROM delegation_member dm JOIN delegation d ON d.id = dm.delegation_id WHERE d.committee_id = ? AND dm.deleted_at IS NULL"
    rows = db_rows(app, q + (" AND d.iso3 = ?" if iso3 else "") + " ORDER BY d.iso3", (committee_id, iso3) if iso3 else (committee_id,))
    return rows
