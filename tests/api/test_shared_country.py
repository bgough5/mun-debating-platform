"""D-086: several students on one country, in uneven numbers (1, 2, 4 and 5 here). Each has every tab, and everything
a student does is signed "Ben G, Australia", so co-delegates and the chair can tell who did it."""
import re

import pytest

from app.db import SYSTEM
from app.modules.chair import service as C
from app.modules.mun import service as M
from app.modules.sim import service as SIM
from app.util import display_name
from tests.api.helpers import join_as
from tests.conftest import db_one, db_rows

SIZES = (1, 2, 4, 5)
TABS = ("floor", "motions", "points", "messages", "speech", "amendments", "friends")


@pytest.fixture
def room(app, coord):
    """An Evatt committee where four countries hold 1, 2, 4 and 5 students, with an open session on the floor."""
    first = db_one(app, "SELECT id FROM student WHERE active = 1 ORDER BY id LIMIT 1")["id"]
    r = coord.post("/start", {"op": "start", "kind": "evatt", "student_id": [str(first)]}, follow_redirects=False)
    sid = int(r.headers["location"].rsplit("/", 1)[1])
    com = db_one(app, "SELECT committee_id FROM live_session WHERE id = ?", (sid,))["committee_id"]
    dels = db_rows(app, "SELECT d.id, d.iso3, c.name FROM delegation d JOIN country c ON c.iso3 = d.iso3 "
                        "WHERE d.committee_id = ? AND d.deleted_at IS NULL ORDER BY d.iso3", (com,))
    holder = db_one(app, "SELECT dm.delegation_id FROM delegation_member dm JOIN delegation d ON d.id = dm.delegation_id "
                         "WHERE dm.student_id = ? AND d.committee_id = ? AND dm.deleted_at IS NULL", (first, com))["delegation_id"]
    countries = [next(d for d in dels if d["id"] == holder)] + [d for d in dels if d["id"] != holder][:3]
    spare = [r["id"] for r in db_rows(app, "SELECT id FROM student WHERE active = 1 AND id != ? ORDER BY id LIMIT 11", (first,))]
    people = {countries[0]["id"]: [first]}
    with app.state.db.write(SYSTEM) as w:
        for d, n in zip(countries[1:], SIZES[1:]):
            people[d["id"]] = [spare.pop(0) for _ in range(n)]
            for i, st in enumerate(people[d["id"]]):
                M.assign_member(w, d["id"], st, "head" if i == 0 else "delegate")
        SIM.set_stage(w, sid, "floor")
    names = {r["id"]: display_name(r["first_name"], r["last_initial"]) for r in db_rows(app, "SELECT * FROM student")}
    return {"sid": sid, "com": com, "countries": countries, "people": people, "names": names}


def by(room, student_id, delegation):
    return f"{room['names'][student_id]}, {delegation['name']}"


def test_country_sizes_are_uneven_as_set_up(app, room):
    got = [db_one(app, "SELECT COUNT(*) AS n FROM delegation_member WHERE delegation_id = ? AND deleted_at IS NULL", (d["id"],))["n"]
           for d in room["countries"]]
    assert got == list(SIZES)


def test_every_student_on_a_country_gets_every_tab_and_sees_who_they_share_it_with(app, room):
    sid = room["sid"]
    for d in room["countries"]:
        for st in room["people"][d["id"]]:
            c = join_as(app, st)
            for tab in TABS:
                r = c.get(f"/live/{sid}?tab={tab}")
                assert r.status_code == 200, (d["iso3"], st, tab)
            page = c.get(f"/live/{sid}").text
            assert f"You are <strong>{d['name']}</strong>" in page
            others = [room["names"][o] for o in room["people"][d["id"]] if o != st]
            if others:
                assert all(n in page.split("You are")[1][:400] for n in others), (d["iso3"], others)
            else:
                assert f"You are <strong>{d['name']}</strong>." in page or f"You are <strong>{d['name']}</strong> (head" in page
            assert c.get(f"/me/committees/{room['com']}/prepare").status_code == 200


def test_messages_name_the_sender_and_the_whole_country_sees_them(app, room):
    sid, (_, two, four, five) = room["sid"], room["countries"]
    sender, mate = room["people"][four["id"]][1], room["people"][four["id"]][0]
    join_as(app, sender).post(f"/live/{sid}/messages", {"to_delegation_id": str(five["id"]), "body": "Join our amendment?"})
    label = by(room, sender, four)
    assert f"You ({label})" in join_as(app, sender).get(f"/live/{sid}?tab=messages").text
    assert f"{label} → {five['name']}" in join_as(app, mate).get(f"/live/{sid}?tab=messages").text   # co-delegate: not "You"
    for st in room["people"][five["id"]]:
        assert f"{label} → {five['name']} (your country)" in join_as(app, st).get(f"/live/{sid}?tab=messages").text
    assert "Join our amendment?" not in join_as(app, room["people"][two["id"]][0]).get(f"/live/{sid}?tab=messages").text


def test_points_speakers_and_motions_name_the_student(app, coord, room):
    sid, (_, two, four, five) = room["sid"], room["countries"]
    p_by, s_by, m_by = room["people"][five["id"]][2], room["people"][five["id"]][1], room["people"][four["id"]][3]
    join_as(app, p_by).post(f"/live/{sid}/points", {"kind": "order", "note": "Time"})
    join_as(app, s_by).post(f"/live/{sid}/speak", {})
    join_as(app, m_by).post(f"/live/{sid}/unmod", {"minutes": "5"})
    chair = coord.get(f"/chair/{sid}").text
    for who in (by(room, p_by, five), by(room, s_by, five), by(room, m_by, four)):
        assert who in chair, who
    mate = join_as(app, room["people"][five["id"]][0])
    assert f"{room['names'][p_by]}'s point of order is waiting" in mate.get(f"/live/{sid}?tab=points").text
    assert f"Proposed by {by(room, m_by, four)}" in mate.get(f"/live/{sid}?tab=motions").text


def test_the_head_of_delegation_casts_the_vote_unless_away(app, room):
    """D-088: the head decides the country's vote. If the head isn't here, a co-delegate who is can cast it."""
    sid, five = room["sid"], room["countries"][3]
    with app.state.db.write(SYSTEM) as w:
        did = C.open_division(w, sid, "Procedural test", "motion", None, procedural=True)
    head, a, b = room["people"][five["id"]][0], room["people"][five["id"]][3], room["people"][five["id"]][4]
    h = join_as(app, head)
    page = h.get(f"/live/{sid}").text                                         # the head is here now
    assert 'name="vote" value="yes"' in page
    mate = join_as(app, a)
    page = mate.get(f"/live/{sid}").text
    assert f"{room['names'][head]} is head of delegation and casts {five['name']}'s vote" in page
    assert 'name="vote" value="yes"' not in page
    r = mate.post(f"/live/{sid}/vote", {"vote": "yes"})
    assert r.status_code == 403 and "is head of delegation" in r.text
    h.post(f"/live/{sid}/vote", {"vote": "yes"})
    assert f"voted <strong>yes</strong> (cast by {by(room, head, five)})" in mate.get(f"/live/{sid}").text
    # The head leaves: after two minutes unseen, a co-delegate who is here can change the vote.
    with app.state.db.write(SYSTEM) as w:
        w.conn.execute("UPDATE session_participant SET last_seen = last_seen - 600 WHERE session_id = ? AND student_id = ?", (sid, head))
    other = join_as(app, b)
    assert "isn't here, so you can cast" in other.get(f"/live/{sid}").text
    other.post(f"/live/{sid}/vote", {"vote": "no"})
    votes = db_rows(app, "SELECT * FROM division_vote WHERE division_id = ? AND iso3 = ?", (did, five["iso3"]))
    assert len(votes) == 1 and votes[0]["vote"] == "no" and votes[0]["cast_by"] == by(room, b, five)


def test_a_country_without_a_head_is_voted_by_any_holder(app, room):
    sid, two = room["sid"], room["countries"][1]
    with app.state.db.write(SYSTEM) as w:
        w.conn.execute("UPDATE delegation_member SET role = 'delegate' WHERE delegation_id = ?", (two["id"],))
        did = C.open_division(w, sid, "Procedural test", "motion", None, procedural=True)
    for st, vote in zip(room["people"][two["id"]], ("yes", "no")):
        join_as(app, st).post(f"/live/{sid}/vote", {"vote": vote})
    v = db_one(app, "SELECT * FROM division_vote WHERE division_id = ? AND iso3 = ?", (did, two["iso3"]))
    assert v["vote"] == "no"


def test_whip_predictions_stay_individual_for_co_delegates(app, room):
    """Everyone on a country gets their own whip-count predictions and score (D-061), not one per country."""
    from app.modules.sim import service as SIM
    sid, four = room["sid"], room["countries"][2]
    with app.state.db.write(SYSTEM) as w:
        s = C.get_session(w.conn, sid)
        res = db_one(app, "SELECT id FROM resolution WHERE committee_id = ? LIMIT 1", (room["com"],))
        rid = SIM.start_whip(w, s, "resolution", res["id"], "Whole resolution", per_student=3)
    per = {st: db_one(app, "SELECT COUNT(*) AS n FROM whip_prediction WHERE round_id = ? AND student_id = ?", (rid, st))["n"]
           for st in room["people"][four["id"]]}
    assert all(n == 3 for n in per.values()) and len(per) == 4


def test_co_delegates_read_each_others_drafts_but_cannot_change_them(app, room):
    sid, com, (_, two, four, five) = room["sid"], room["com"], room["countries"]
    writer, mate, outsider = room["people"][four["id"]][2], room["people"][four["id"]][3], room["people"][five["id"]][0]
    join_as(app, writer).post(f"/me/committees/{com}/speeches", {"kind": "speech", "title": "Finance caucus",
                                                                 "body": "We will fund adaptation first.", "next": f"/live/{sid}?tab=speech"})
    d = db_one(app, "SELECT id FROM speech_draft WHERE student_id = ? ORDER BY id DESC LIMIT 1", (writer,))
    page = join_as(app, mate).get(f"/live/{sid}?tab=speech").text
    assert f"{by(room, writer, four)}: Finance caucus" in page and "We will fund adaptation first." in page
    assert "We will fund adaptation first." in join_as(app, mate).get(f"/me/committees/{com}/prepare").text
    assert "We will fund adaptation first." not in join_as(app, outsider).get(f"/live/{sid}?tab=speech").text
    r = join_as(app, mate).post(f"/me/committees/{com}/speeches", {"draft_id": str(d["id"]), "kind": "speech", "title": "Mine now",
                                                                    "body": "changed", "next": f"/live/{sid}?tab=speech"})
    assert r.status_code == 403
    assert db_one(app, "SELECT body FROM speech_draft WHERE id = ?", (d["id"],))["body"] == "We will fund adaptation first."


def test_signatures_on_amendments_name_the_student(app, room):
    sid, com, (_, two, four, five) = room["sid"], room["com"], room["countries"]
    sponsor, signer = room["people"][two["id"]][1], room["people"][five["id"]][4]
    para = db_one(app, "SELECT p.id, v.text FROM paragraph p JOIN resolution r ON r.id = p.resolution_id JOIN paragraph_version v "
                       "ON v.id = p.current_version_id WHERE r.committee_id = ? AND p.kind = 'operative' ORDER BY p.position LIMIT 1", (com,))
    s = join_as(app, sponsor)
    s.post(f"/mun/committees/{com}/amendments", {"paragraph_id": str(para["id"]), "kind": "replace",
                                                 "proposed_text": para["text"] + " With a review.", "rationale": ""})
    aid = db_one(app, "SELECT id FROM amendment ORDER BY id DESC LIMIT 1")["id"]
    s.post(f"/mun/amendments/{aid}/act", {"action": "submit"})
    join_as(app, signer).post(f"/mun/amendments/{aid}/act", {"action": "sign"})
    board = join_as(app, room["people"][four["id"]][0]).get(f"/mun/committees/{com}/amendments").text
    assert f"Sponsor: {by(room, sponsor, two)}" in board and f"Signed by {by(room, signer, five)}" in board


def test_minutes_name_who_spoke_and_proposed(app, coord, room):
    sid, four = room["sid"], room["countries"][2]
    st = room["people"][four["id"]][0]
    join_as(app, st).post(f"/live/{sid}/unmod", {"minutes": "3"})
    assert f"proposed by {by(room, st, four)}" in coord.get(f"/chair/{sid}/minutes").text
