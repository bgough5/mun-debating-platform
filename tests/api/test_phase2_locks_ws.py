"""Paragraph locks (one editor at a time) and WebSocket access and replay."""
import json

from app.util import set_clock
from tests.api.helpers import ga, join_as, member_of
from tests.conftest import db_one


def _owned_paragraph(app, coord, delegation_id):
    com = ga(app)
    res = db_one(app, "SELECT id FROM resolution WHERE committee_id = ?", (com["id"],))["id"]
    p = db_one(app, "SELECT * FROM paragraph WHERE resolution_id = ? AND kind='operative' AND position=4", (res,))
    coord.post(f"/mun/paragraphs/{p['id']}", {"text": "Shared text.", "tags": ["agriculture"], "version_id": p["current_version_id"],
                                             "owner_delegation_id": delegation_id})
    return db_one(app, "SELECT * FROM paragraph WHERE id = ?", (p["id"],))


def test_one_editor_per_paragraph(app, coord):
    com = ga(app)
    # find a delegation with two students
    from tests.conftest import db_rows
    d = db_one(app, "SELECT delegation_id FROM delegation_member dm JOIN delegation d ON d.id = dm.delegation_id WHERE d.committee_id = ? "
                    "AND dm.deleted_at IS NULL GROUP BY delegation_id HAVING COUNT(*) >= 1 LIMIT 1", (com["id"],))["delegation_id"]
    students = [r["student_id"] for r in db_rows(app, "SELECT student_id FROM delegation_member WHERE delegation_id = ?", (d,))]
    p = _owned_paragraph(app, coord, d)
    a = join_as(app, students[0])
    assert a.post(f"/mun/paragraphs/{p['id']}/lock").json()["state"] == "held"
    # staff (or a second delegate) can't take it while it is held
    r = coord.post(f"/mun/paragraphs/{p['id']}/lock")
    assert r.status_code == 409 and "editing" in r.json()["message"]
    r = coord.post(f"/mun/paragraphs/{p['id']}", {"text": "Clash", "tags": [], "version_id": p["current_version_id"]})
    assert r.status_code == 409 and "wasn't saved" in r.text
    # the holder saves; the lock is released
    assert a.post(f"/mun/paragraphs/{p['id']}", {"text": "Holder's edit.", "tags": ["agriculture"], "version_id": p["current_version_id"]}).status_code == 200
    assert coord.post(f"/mun/paragraphs/{p['id']}/lock").json()["state"] == "held"


def test_lock_lapses_without_heartbeat(app, coord):
    com = ga(app)
    m = member_of(app, com["id"])[0]
    p = _owned_paragraph(app, coord, m["delegation_id"])
    a = join_as(app, m["student_id"])
    t = [1_900_000_000.0]
    set_clock(lambda: t[0])
    try:
        a.post(f"/mun/paragraphs/{p['id']}/lock")
        assert coord.post(f"/mun/paragraphs/{p['id']}/lock").status_code == 409
        t[0] += 61
        assert coord.post(f"/mun/paragraphs/{p['id']}/lock").status_code == 200
    finally:
        set_clock(None)


def test_websocket_access_and_live_message(app, coord):
    com = ga(app)
    coord.post(f"/chair/committee/{com['id']}/open")
    s = db_one(app, "SELECT * FROM live_session WHERE committee_id = ?", (com["id"],))
    m = member_of(app, com["id"])[0]
    c = join_as(app, m["student_id"])
    with c.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"subscribe": [f"session:{s['id']}", "class:999", "session:99999"], "since": 0}))
        hello = json.loads(ws.receive_text())
        assert hello["subscribed"] == [f"session:{s['id']}"] and len(hello["denied"]) == 2
        d = db_one(app, "SELECT id FROM delegation WHERE committee_id = ? AND iso3 = 'FJI'", (com["id"],))["id"]
        coord.post(f"/chair/{s['id']}/speakers", {"delegation_id": d})
        msg = json.loads(ws.receive_text())
        assert f"session:{s['id']}" in msg["channels"] and msg["seq"] > hello["seq"]
        last = msg["seq"]
    # reconnect with `since`: changes made while away are replayed, none lost
    coord.post(f"/chair/{s['id']}/next")
    coord.post(f"/chair/{s['id']}/state", {"state": "suspended"})
    with c.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"subscribe": [f"session:{s['id']}"], "since": last}))
        json.loads(ws.receive_text())
        replay = [json.loads(ws.receive_text()), json.loads(ws.receive_text())]
        assert all(r["replay"] for r in replay) and replay[0]["seq"] < replay[1]["seq"]


def test_projector_websocket_token(app, coord, client):
    com = ga(app)
    coord.post(f"/chair/committee/{com['id']}/open")
    s = db_one(app, "SELECT * FROM live_session WHERE committee_id = ?", (com["id"],))
    with client.websocket_connect(f"/ws?projector={s['projector_token']}") as ws:
        ws.send_text(json.dumps({"subscribe": [f"session:{s['id']}", f"committee:{com['id']}"]}))
        hello = json.loads(ws.receive_text())
        assert hello["subscribed"] == [f"session:{s['id']}"]
    with client.websocket_connect("/ws?projector=wrong") as ws:
        ws.send_text(json.dumps({"subscribe": [f"session:{s['id']}"]}))
        assert json.loads(ws.receive_text())["subscribed"] == []
