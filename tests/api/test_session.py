"""D-101, phase 2: The Session's shell. Anyone can open the title screen and set up a session. A guest's session is
signed by the server and kept in their browser, never stored; it can't be edited. A signed-in student's session is
saved on every move, is theirs alone, and goes when the student is erased."""
import json

from app.db import SYSTEM
from tests.api.helpers import join_as
from tests.conftest import Client, db_one


def api(c, body):
    return c.request("POST", "/session/api", json=body, headers={"X-CSRF-Token": c.csrf()})


def guest(app) -> Client:
    return Client(app, base_url="http://testserver").__enter__()


def test_anyone_can_open_the_title_and_set_up(app):
    c = guest(app)
    t = c.get("/session")
    assert t.status_code == 200 and "<h1" in t.text and "The Session" in t.text and "New session" in t.text and "Quick vote" in t.text
    n = c.get("/session/new").text
    assert "Comet Halcyon-7" in n and "Beginner" in n and "Expert" in n and "Take your seat" in n
    seats = c.get("/session/seats/comet_halcyon").text
    assert 'data-pick="iso3"' in seats and 'id="b-map"' in seats and ("Easier" in seats or "Balanced" in seats or "Harder" in seats)
    assert c.get("/session/seats/nope").status_code == 404


def test_a_guest_session_is_signed_kept_in_the_browser_and_cant_be_edited(app):
    c = guest(app)
    before = db_one(app, "SELECT COUNT(*) AS n FROM campaign_save")["n"]
    r = api(c, {"do": "new", "pack": "comet_halcyon", "iso3": "NZL", "length": "quick", "difficulty": "easy", "path": "consensus"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["url"] == "/session/guest/comet_halcyon" and j["state"]["iso3"] == "NZL" and len(j["sig"]) == 64
    assert j["view"]["you"]["name"] == "New Zealand" and j["view"]["mandate"]["must"]["label"]
    page = c.get("/session/guest/comet_halcyon").text
    assert 'data-mode="guest"' in page and 'id="b-map"' in page
    as_js = json.loads(json.dumps(j["state"]), parse_float=lambda t: int(float(t)) if float(t).is_integer() else float(t))
    assert json.dumps(as_js) != json.dumps(j["state"])      # a browser keeps 0.0 as 0: the signature must still hold
    m = api(c, {"do": "move", "state": as_js, "sig": j["sig"], "action": {"do": "end_turn"}})
    assert m.status_code == 200 and m.json()["view"]["turn"] == 2 and m.json()["sig"] != j["sig"]
    rich = {**j["state"], "influence": 99}
    bad = api(c, {"do": "move", "state": rich, "sig": j["sig"], "action": {"do": "end_turn"}})
    assert bad.status_code == 400 and "changed outside" in bad.json()["error"]
    illegal = api(c, {"do": "move", "state": j["state"], "sig": j["sig"], "action": {"do": "lobby", "iso3": "NZL"}})
    assert illegal.status_code == 400 and "another delegation" in illegal.json()["error"]
    assert c.request("POST", "/session/api", json={"do": "view", "state": j["state"], "sig": j["sig"]}).status_code == 403   # CSRF
    assert db_one(app, "SELECT COUNT(*) AS n FROM campaign_save")["n"] == before          # nothing about a guest is kept


def test_a_students_session_is_saved_and_theirs_alone(app):
    from app.retention import erase_student
    st = db_one(app, "SELECT id FROM student WHERE active = 1 ORDER BY id DESC LIMIT 1")["id"]
    a = join_as(app, st)
    j = api(a, {"do": "new", "pack": "veloria", "iso3": "FRA", "length": "standard", "difficulty": "standard", "path": "mandate"}).json()
    assert j["url"].startswith("/session/s/") and "state" not in j
    sid = int(j["url"].rsplit("/", 1)[1])
    assert db_one(app, "SELECT student_id, phase FROM campaign_save WHERE id = ?", (sid,)) == {"student_id": st, "phase": "chapter"}
    assert 'data-mode="saved"' in a.get(j["url"]).text and "Veloria" in a.get("/session").text
    m = api(a, {"do": "move", "save_id": sid, "action": {"do": "end_turn"}}).json()
    assert m["view"]["turn"] == 2 and db_one(app, "SELECT chapter FROM campaign_save WHERE id = ?", (sid,))["chapter"] == 1
    other = join_as(app, db_one(app, "SELECT id FROM student WHERE active = 1 AND id != ? ORDER BY id LIMIT 1", (st,))["id"])
    assert other.get(j["url"]).status_code == 403
    assert api(other, {"do": "view", "save_id": sid}).status_code == 403
    assert api(guest(app), {"do": "view", "save_id": sid}).status_code == 403
    with app.state.db.write(SYSTEM) as w:
        erase_student(w, st)
    assert db_one(app, "SELECT COUNT(*) AS n FROM campaign_save WHERE student_id = ?", (st,))["n"] == 0
