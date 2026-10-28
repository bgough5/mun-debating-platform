"""Security hardening (D-083, docs/security-audit.md). One section per finding from the 29 Oct 2026 stress test.

Each test states the secure behaviour. All five failed on the code before the fixes, which is how each finding
was confirmed as real rather than only read off the code. Fake demo data only.
"""
import csv
import io

from app.util import hash_passphrase
from tests.api.helpers import ga, join_as, member_of
from tests.conftest import COORD_PASS, Client, db_one, db_rows, login_staff


# ---------- S-1 CSV exports must not carry spreadsheet formulas ----------

def test_csv_cells_that_start_like_formulas_are_neutralised():
    from app.exports import csv_bytes, read_csv
    rows = [{"a": "=1+1", "b": "+A1", "c": "-A1", "d": "@SUM(A1)", "e": "\t=A1", "f": 5, "g": -3, "h": "plain", "i": "a=b"}]
    out = list(csv.reader(io.StringIO(csv_bytes(rows).decode("utf-8-sig"))))
    assert out[1] == ["'=1+1", "'+A1", "'-A1", "'@SUM(A1)", "'\t=A1", "5", "-3", "plain", "a=b"]
    # Re-importing an export gives back the original text, not a growing pile of apostrophes.
    assert read_csv(csv_bytes(rows))[0]["a"] == "=1+1"


def test_student_text_reaches_exports_neutralised(app, coord):
    com = ga(app)
    st = member_of(app, com["id"])[0]
    para = db_one(app, "SELECT p.id FROM paragraph p JOIN resolution r ON r.id = p.resolution_id "
                       "WHERE r.committee_id = ? AND p.kind = 'operative' LIMIT 1", (com["id"],))
    c = join_as(app, st["student_id"])
    r = c.post(f"/mun/committees/{com['id']}/evidence", {"subject_kind": "country", "iso3": st["iso3"], "target_kind": "paragraph",
                                                         "target_id_paragraph": str(para["id"]), "position": "1",
                                                         "source": "caucus", "summary": "=1+1"})
    assert r.status_code == 200, r.text[:300]
    rows = list(csv.DictReader(io.StringIO(coord.get("/admin/csv/evidence.csv").content.decode("utf-8-sig"))))
    assert "=1+1" not in [x["summary"] for x in rows]
    assert "'=1+1" in [x["summary"] for x in rows]


# ---------- S-2 wrong passphrases from one laptop must not lock the coordinator out everywhere ----------

def _laptop(app, ip: str) -> Client:
    c = Client(app, base_url="http://testserver", client=(ip, 50000))
    c.__enter__()
    return c


def test_throttle_is_per_laptop_not_per_account(app):
    noisy = _laptop(app, "10.0.0.66")
    for _ in range(5):
        assert noisy.post("/login", {"who": "coordinator", "passphrase": "not it"}).status_code == 401
    assert noisy.post("/login", {"who": "coordinator", "passphrase": COORD_PASS}).status_code == 429   # still throttled there
    teacher = _laptop(app, "10.0.0.2")
    r = teacher.post("/login", {"who": "coordinator", "passphrase": COORD_PASS})
    assert r.status_code == 200, r.text[:200]                                                          # but not on the teacher's laptop


# ---------- S-3 redirect targets from forms and headers stay on this site ----------

def test_safe_path_rules():
    from app.web.safety import safe_path
    assert safe_path("/mun/committees/1") == "/mun/committees/1"
    assert safe_path("/x?y=1#z") == "/x?y=1#z"
    for bad in ("//example.org", "/\\example.org", "\\\\example.org", "https://example.org/", "example.org",
                "/x\r\nSet-Cookie: a=b", "", None, " //example.org"):
        assert safe_path(bad) == "/", bad


def test_login_next_cannot_leave_the_site(client):
    for nxt in ("/\\example.org", "//example.org", "https://example.org"):
        r = client.post("/login", {"who": "coordinator", "passphrase": COORD_PASS, "next": nxt}, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/", (nxt, r.headers.get("location"))
    r = client.post("/login", {"who": "coordinator", "passphrase": COORD_PASS, "next": "/mun"}, follow_redirects=False)
    assert r.headers["location"] == "/mun"


def test_back_links_and_referer_cannot_leave_the_site(app, coord):
    com = ga(app)
    st = member_of(app, com["id"])[0]
    para = db_one(app, "SELECT p.id FROM paragraph p JOIN resolution r ON r.id = p.resolution_id "
                       "WHERE r.committee_id = ? AND p.kind = 'operative' LIMIT 1", (com["id"],))
    r = coord.post(f"/mun/committees/{com['id']}/evidence", {"subject_kind": "country", "iso3": st["iso3"], "target_kind": "paragraph",
                                                             "target_id_paragraph": str(para["id"]), "position": "1", "source": "x",
                                                             "source_type": "student_intel", "back": "/\\example.org"},
                   follow_redirects=False)
    assert r.status_code == 303 and "example.org" not in r.headers["location"]
    r = coord.post("/mun/undo", {}, headers={"referer": "http://example.org/x"}, follow_redirects=False)
    assert r.status_code == 303 and "example.org" not in r.headers["location"]
    r = coord.post("/mun/undo", {}, headers={"referer": "http://testserver/mun/committees/1"}, follow_redirects=False)
    assert r.headers["location"] == "/mun/committees/1"


# ---------- S-4 only the person who recorded evidence (or a teacher of that committee) can remove it ----------

def _record(app, c, com, iso3, summary) -> int:
    para = db_one(app, "SELECT p.id FROM paragraph p JOIN resolution r ON r.id = p.resolution_id "
                       "WHERE r.committee_id = ? AND p.kind = 'operative' LIMIT 1", (com["id"],))
    r = c.post(f"/mun/committees/{com['id']}/evidence", {"subject_kind": "country", "iso3": iso3, "target_kind": "paragraph",
                                                         "target_id_paragraph": str(para["id"]), "position": "1",
                                                         "source": "caucus", "summary": summary})
    assert r.status_code == 200, r.text[:300]
    return db_one(app, "SELECT id FROM evidence WHERE summary = ?", (summary,))["id"]


def _deleted(app, eid) -> bool:
    return db_one(app, "SELECT deleted_at FROM evidence WHERE id = ?", (eid,))["deleted_at"] is not None


def test_same_display_name_does_not_make_you_the_owner(app):
    com = ga(app)
    m = member_of(app, com["id"])
    a, c = m[0], m[3]
    owner = db_one(app, "SELECT first_name, last_initial FROM student WHERE id = ?", (c["student_id"],))
    with app.state.db.write(None) as w:                       # two students who share a display name
        w.conn.execute("UPDATE student SET first_name = ?, last_initial = ? WHERE id = ?",
                       (owner["first_name"], owner["last_initial"], a["student_id"]))
    cc, ca = join_as(app, c["student_id"]), join_as(app, a["student_id"])
    eid = _record(app, cc, com, c["iso3"], "evidence owned by C")
    r = ca.post(f"/mun/evidence/{eid}/delete", {"committee_id": str(com["id"])})
    assert r.status_code == 403 and not _deleted(app, eid)
    r = cc.post(f"/mun/evidence/{eid}/delete", {"committee_id": str(com["id"])})
    assert r.status_code == 200 and _deleted(app, eid)          # the real owner still can


def test_teacher_of_another_class_cannot_delete_by_naming_their_own_committee(app, coord):
    com = ga(app)
    st = member_of(app, com["id"])[0]
    eid = _record(app, join_as(app, st["student_id"]), com, st["iso3"], "evidence in the GA")
    club = db_one(app, "SELECT id FROM class WHERE code = 'DEMO3C'")["id"]
    sc = db_one(app, "SELECT id FROM committee WHERE class_id = ? AND deleted_at IS NULL LIMIT 1", (club,))["id"]
    with app.state.db.write(None) as w:                       # a second teacher who teaches only the lunchtime club
        sid = w.conn.execute("INSERT INTO staff (name, pass_hash) VALUES (?, ?)", ("Club Teacher", hash_passphrase("club teacher pass"))).lastrowid
        w.conn.execute("INSERT INTO staff_class (staff_id, class_id) VALUES (?, ?)", (sid, club))
    t = login_staff(Client(app, base_url="http://testserver").__enter__(), sid, "club teacher pass")
    r = t.post(f"/mun/evidence/{eid}/delete", {"committee_id": str(sc)})
    assert r.status_code == 403 and not _deleted(app, eid)
    r = coord.post(f"/mun/evidence/{eid}/delete", {"committee_id": str(com["id"])})
    assert r.status_code == 200 and _deleted(app, eid)          # the coordinator can


# ---------- S-5 stored flag markup is limited to safe SVG ----------

def test_unsafe_flag_markup_is_not_rendered(app, coord):
    com = ga(app)
    iso3 = member_of(app, com["id"])[0]["iso3"]
    for bad in ('<svg viewBox="0 0 24 16"><script>window.x=1</script></svg>',
                '<svg viewBox="0 0 24 16" onload="window.x=1"><rect width="24" height="16"/></svg>',
                '<svg viewBox="0 0 24 16"><a href="javascript:void(0)"><rect width="24" height="16"/></a></svg>'):
        with app.state.db.write(None) as w:
            w.conn.execute("UPDATE country SET flag_svg = ? WHERE iso3 = ?", (bad, iso3))
        for page in (f"/mun/committees/{com['id']}", f"/admin/t/country?q={iso3}"):
            body = coord.get(page).content
            assert b"<script>window.x" not in body and b'onload="window.x' not in body and b"javascript:void" not in body, (bad, page)


def test_every_seeded_flag_still_renders(app):
    from app.web.safety import safe_svg
    flags = db_rows(app, "SELECT iso3, flag_svg FROM country WHERE flag_svg != ''")
    assert flags and all(str(safe_svg(f["flag_svg"])) for f in flags), [f["iso3"] for f in flags if not str(safe_svg(f["flag_svg"]))]


def test_admin_refuses_to_save_unsafe_flag_markup(app, coord):
    row = db_one(app, "SELECT * FROM country WHERE iso3 = 'AUS'")
    form = {"iso3": "AUS", "name": row["name"], "un_member": "1" if row["un_member"] else "", "p5": "", "region": row["region"] or "",
            "notes": row["notes"] or "", "flag_svg": '<svg viewBox="0 0 24 16" onload="window.x=1"></svg>'}
    r = coord.post("/admin/t/country/AUS", form)
    assert r.status_code == 400
    assert "window.x" not in (db_one(app, "SELECT flag_svg FROM country WHERE iso3 = 'AUS'")["flag_svg"] or "")
