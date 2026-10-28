"""Phase 5 permissions audit: every route × every role, enforced on the server (spec §8.3).

1. Static: every route is either listed as public (with a reason) or depends on a
   require_* check. A new route without one fails here.
2. Dynamic: every route is requested by every role that should NOT reach it, and
   must be refused (sign-in redirect for anonymous, 403 for a signed-in role), and
   none of those requests may change any data.
3. Scope: signed-in users who pass the role check are still refused other
   classes' committees, sessions, debates and records.
"""
import re

from app.fakedata import DEMO_STAFF_PASSPHRASE
from app.web.route_audit import classify
from tests.api.helpers import join_as
from tests.conftest import db_one, db_rows, login_staff, new_client

PASSES = {"public": {"anonymous", "student", "staff", "coordinator"}, "signed_in": {"student", "staff", "coordinator"},
          "student": {"student"}, "staff": {"staff", "coordinator"}, "coordinator": {"coordinator"}}
SAMPLE = {"name": "country", "kind": "resolution", "part": "floor", "token": "not-a-token", "code": "ZZZZZZ"}


def _url(path: str) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: SAMPLE.get(m.group(1), "1"), path)


def test_every_route_has_a_server_side_check(app):
    table = classify(app)
    unchecked = [f"{r['method']} {r['path']}" for r in table if r["level"] == "UNCHECKED"]
    assert unchecked == []
    by = {(r["method"], r["path"]): r["level"] for r in table}
    assert all(lvl == "coordinator" for (m, p), lvl in by.items() if p.startswith("/admin"))
    assert all(lvl == "student" for (m, p), lvl in by.items() if p.startswith(("/me/", "/live/")) or p == "/me")
    assert by[("POST", "/people/staff")] == "coordinator"
    assert by[("POST", "/intel/ai")] == "coordinator"
    assert len(table) > 150


def _seq(app):
    return db_one(app, "SELECT COALESCE(MAX(seq), 0) AS s FROM event_log")["s"]


def test_every_route_refuses_every_role_below_it(app, coord):
    staff = db_one(app, "SELECT id FROM staff WHERE name = 'Demo Chair'")["id"]
    stu = db_one(app, "SELECT st.id FROM student st JOIN class c ON c.id = st.class_id WHERE c.code = 'DEMO9M' ORDER BY st.id LIMIT 1")["id"]
    anon = new_client(app).__enter__()
    teacher = new_client(app).__enter__()
    login_staff(teacher, staff, DEMO_STAFF_PASSPHRASE)
    pupil = join_as(app, stu)
    clients = {"anonymous": anon, "student": pupil, "staff": teacher, "coordinator": coord}
    before = _seq(app)
    checked, problems = 0, []
    for r in classify(app):
        if r["method"] == "WS" or r["level"] == "public":
            continue
        for role, c in clients.items():
            if role in PASSES[r["level"]]:
                continue
            url = _url(r["path"])
            resp = c.get(url, follow_redirects=False) if r["method"] == "GET" else c.post(url, {}, follow_redirects=False)
            checked += 1
            if role == "anonymous":
                ok = resp.status_code == 303 and re.search(r"/(login|join)", resp.headers.get("location", ""))
            else:
                ok = resp.status_code == 403
            if not ok:
                problems.append((role, r["method"], url, resp.status_code))
    for c in (anon, teacher, pupil):
        c.__exit__(None, None, None)
    assert problems == []
    assert _seq(app) == before            # no refused request changed anything
    assert checked > 300


def test_scope_other_class(app, coord):
    """Passing the role check is not enough: other classes' things stay closed."""
    ga = db_one(app, "SELECT cm.* FROM committee cm JOIN class c ON c.id = cm.class_id WHERE c.code = 'DEMO9M' LIMIT 1")
    res = db_one(app, "SELECT * FROM resolution WHERE committee_id = ? LIMIT 1", (ga["id"],))
    para = db_one(app, "SELECT * FROM paragraph WHERE resolution_id = ? LIMIT 1", (res["id"],))
    r = coord.post(f"/chair/committee/{ga['id']}/open", follow_redirects=False)
    sid = int(r.headers["location"].rstrip("/").rsplit("/", 1)[1])
    outsider = db_one(app, "SELECT st.id FROM student st JOIN class c ON c.id = st.class_id WHERE c.code = 'DEMO8D' ORDER BY st.id LIMIT 1")["id"]
    pupil = join_as(app, outsider)
    before = _seq(app)
    denied = {
        "GET": [f"/mun/committees/{ga['id']}", f"/mun/resolutions/{res['id']}", f"/mun/resolutions/{res['id']}/fragment",
                f"/mun/resolutions/{res['id']}/print", f"/mun/resolutions/{res['id']}/export.docx",
                f"/mun/paragraphs/{para['id']}/history", f"/mun/paragraphs/{para['id']}/compare",
                f"/mun/predict/resolution/{res['id']}", f"/live/{sid}", f"/live/{sid}/f"],
        "POST": [f"/mun/paragraphs/{para['id']}/lock", f"/mun/paragraphs/{para['id']}", f"/mun/paragraphs/{para['id']}/amendments",
                 f"/live/{sid}/speak", f"/live/{sid}/vote", f"/live/{sid}/motion"],
    }
    problems = []
    for method, urls in denied.items():
        for u in urls:
            resp = pupil.get(u, follow_redirects=False) if method == "GET" else pupil.post(u, {"text": "x", "vote": "yes"}, follow_redirects=False)
            if resp.status_code not in (403, 404):
                problems.append((method, u, resp.status_code))
    # A debate ballot the student doesn't adjudicate.
    pairing = db_one(app, "SELECT id FROM pairing WHERE neg_team_id IS NOT NULL LIMIT 1")
    if pairing:
        for method in ("GET", "POST"):
            u = f"/debating/pairings/{pairing['id']}/ballot"
            resp = pupil.get(u, follow_redirects=False) if method == "GET" else pupil.post(u, {}, follow_redirects=False)
            if resp.status_code not in (403, 404):
                problems.append((method, u, resp.status_code))
    pupil.__exit__(None, None, None)
    assert problems == []
    assert _seq(app) == before

    # Staff assigned only to another class.
    coord.post("/people/staff", {"action": "create", "name": "Mr Other", "passphrase": "other staff passphrase"})
    other = db_one(app, "SELECT id FROM staff WHERE name = 'Mr Other'")["id"]
    small = db_one(app, "SELECT id FROM class WHERE code = 'DEMO3C'")["id"]
    coord.post("/people/staff", {"action": "classes", "staff_id": other, "class_id": [str(small)]})
    ev = db_one(app, "SELECT * FROM debate_event WHERE class_id IS NOT NULL AND class_id != ? LIMIT 1", (small,))
    before = _seq(app)
    with new_client(app) as t:
        login_staff(t, other, "other staff passphrase")
        urls = [f"/chair/{sid}", f"/chair/{sid}/f/floor", f"/chair/{sid}/minutes", f"/mun/committees/{ga['id']}",
                f"/people/classes/{ga['class_id']}", f"/mun/predict/resolution/{res['id']}"]
        if ev:
            urls += [f"/debating/events/{ev['id']}", f"/debating/events/{ev['id']}/setup", f"/debating/events/{ev['id']}/results"]
        for u in urls:
            assert t.get(u, follow_redirects=False).status_code in (403, 404), u
        for u in (f"/chair/{sid}/next", f"/chair/{sid}/state", f"/mun/paragraphs/{para['id']}/lock"):
            assert t.post(u, {}, follow_redirects=False).status_code in (403, 404), u
        st = db_rows(app, "SELECT id FROM student WHERE class_id = ? LIMIT 1", (ga["class_id"],))[0]["id"]
        assert t.post(f"/people/students/{st}", {"action": "delete", "confirm": "yes"}, follow_redirects=False).status_code == 403
    assert _seq(app) == before
