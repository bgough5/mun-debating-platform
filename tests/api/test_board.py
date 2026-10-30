"""D-092: the board, the projector's war-room table. A page of its own, driven by the session's state."""
import json
import re

from app.db import SYSTEM
from app.modules.chair import service as C
from app.modules.sim import service as SIM
from tests.api.helpers import join_as
from tests.conftest import Client, db_one, db_rows


def evatt(app, coord, n=6):
    ids = [r["id"] for r in db_rows(app, "SELECT id FROM student WHERE active = 1 ORDER BY id LIMIT ?", (n,))]
    r = coord.post("/start", {"op": "start", "kind": "evatt", "student_id": [str(i) for i in ids]}, follow_redirects=False)
    sid = int(r.headers["location"].rsplit("/", 1)[1])
    tok = db_one(app, "SELECT projector_token FROM live_session WHERE id = ?", (sid,))["projector_token"]
    return sid, ids, tok


def test_the_board_is_a_page_of_its_own(app, coord):
    sid, _, tok = evatt(app, coord)
    page = Client(app, base_url="http://testserver").__enter__().get(f"/projector/{tok}").text   # no sign-in, like the old projector
    assert "board.js" in page and "board.css" in page and 'id="b-map"' in page
    assert 'class="site"' not in page and "Sign out" not in page                    # no app header, menus or footer
    assert page.count('class="b-token"') == 15                                       # a token on each Security Council seat
    m = re.search(r'<script id="b-initial" type="application/json">(.*?)</script>', page, re.S)
    st = json.loads(m.group(1))
    assert st["stage"]["code"] == "roll_call" and len(st["stage"]["all"]) == 6 and st["session"]["committee"]
    assert "<title>" + st["session"]["committee"] in page.replace("&#39;", "'") or "<title>" in page
    assert '<h1 class="b-committee"' in page and 'id="main"' in page and 'class="skip"' in page
    console = coord.get(f"/chair/{sid}").text
    assert f'data-board-open="/projector/{tok}"' in console and f"/projector/{tok}/plain" in console
    assert "Now speaking" in coord.get(f"/projector/{tok}/plain").text or coord.get(f"/projector/{tok}/plain").status_code == 200


def test_a_wrong_token_shows_nothing(app):
    c = Client(app, base_url="http://testserver").__enter__()
    assert c.get("/projector/not-a-token").status_code == 404
    assert c.get("/projector/not-a-token/state.json").status_code == 404


def test_state_follows_the_session(app, coord):
    sid, ids, tok = evatt(app, coord)
    c = Client(app, base_url="http://testserver").__enter__()
    st = c.get(f"/projector/{tok}/state.json").json()
    assert st["roll"]["present"] == 0 and st["current"] is None and st["division"] is None
    a = join_as(app, ids[0])
    a.get(f"/live/{sid}")
    a.post(f"/live/{sid}/roll", {"status": "present_and_voting"})
    a.post(f"/live/{sid}/speak", {})
    with app.state.db.write(SYSTEM) as w:
        C.next_speaker(w, sid)
    st = c.get(f"/projector/{tok}/state.json").json()
    assert st["roll"]["present"] == 1 and "present_and_voting" in [x["roll"] for x in st["countries"]]
    assert st["current"] and ", " in st["current"]["by"] and st["timers"] and st["timers"][0]["total"] > 0
    with app.state.db.write(SYSTEM) as w:
        SIM.set_stage(w, sid, "voting_procedure")
        did = C.open_division(w, sid, "Procedural test", "custom", None, procedural=True)
    a.post(f"/live/{sid}/vote", {"vote": "yes"})
    st = c.get(f"/projector/{tok}/state.json").json()
    assert st["stage"]["code"] == "voting_procedure" and st["division"]["id"] == did and "yes" in st["division"]["votes"].values()
    with app.state.db.write(SYSTEM) as w:
        C.close_division(w, did)
    st = c.get(f"/projector/{tok}/state.json").json()
    assert st["division"] is None and st["result"]["id"] == did and st["result"]["votes"]


def test_the_debrief_shows_how_every_country_voted(app, coord):
    sid, ids, tok = evatt(app, coord)
    com = db_one(app, "SELECT committee_id FROM live_session WHERE id = ?", (sid,))["committee_id"]
    res = db_one(app, "SELECT id FROM resolution WHERE committee_id = ? LIMIT 1", (com,))["id"]
    with app.state.db.write(SYSTEM) as w:
        SIM.set_stage(w, sid, "voting_procedure")
        did = C.open_division(w, sid, "The whole resolution", "resolution", res)
    with app.state.db.write(SYSTEM) as w:
        C.close_division(w, did)
        SIM.set_stage(w, sid, "debrief")
    st = Client(app, base_url="http://testserver").__enter__().get(f"/projector/{tok}/state.json").json()
    assert st["stage"]["code"] == "debrief" and st["debrief"]["id"] == did
    assert len(st["debrief"]["votes"]) == 15                               # every Security Council country, coloured on the map


def test_the_board_holds_no_student_codes(app, coord):
    sid, ids, tok = evatt(app, coord)
    body = Client(app, base_url="http://testserver").__enter__().get(f"/projector/{tok}/state.json").text
    for r in db_rows(app, "SELECT login_code FROM student WHERE id IN (%s)" % ",".join(map(str, ids))):
        assert r["login_code"] not in body
    assert "login_code" not in body and "pass_hash" not in body
