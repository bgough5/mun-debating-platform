"""D-094: how countries are given out. The Chair starts an activity with countries at random, chosen by the students,
or given out by the Chair; students on today's list can open the session before they have one; choosing can be
opened and closed during the session, and closing it seats anyone still waiting at random."""
import pytest

from app.db import SYSTEM
from app.errors import UserError
from app.modules.mun import choice as CH
from tests.api.helpers import join_as
from tests.conftest import db_one, db_rows


def start(app, coord, mode, n=6):
    ids = [r["id"] for r in db_rows(app, "SELECT id FROM student WHERE active = 1 ORDER BY id LIMIT ?", (n,))]
    r = coord.post("/start", {"op": "start", "kind": "evatt", "country_mode": mode, "student_id": [str(i) for i in ids]},
                   follow_redirects=False)
    sid = int(r.headers["location"].rsplit("/", 1)[1])
    com = db_one(app, "SELECT committee_id FROM live_session WHERE id = ?", (sid,))["committee_id"]
    return sid, com, ids


def seated(app, com):
    return {r["student_id"]: r for r in db_rows(app, "SELECT dm.student_id, dm.role, d.id AS did, d.iso3 FROM delegation_member dm "
                                                     "JOIN delegation d ON d.id = dm.delegation_id WHERE d.committee_id = ? "
                                                     "AND dm.deleted_at IS NULL", (com,))}


def test_start_offers_the_three_ways(app, coord):
    page = coord.get("/start").text
    assert 'name="country_mode"' in page and "Students choose" in page and "At random" in page and "The Chair assigns them" in page


def test_random_seats_everyone_one_per_country_first(app, coord):
    sid, com, ids = start(app, coord, "random")
    s = seated(app, com)
    assert set(s) == set(ids) and len({x["did"] for x in s.values()}) == len(ids)      # 6 students, 15 seats: one each
    assert all(x["role"] == "head" for x in s.values())
    assert db_one(app, "SELECT country_mode FROM committee WHERE id = ?", (com,))["country_mode"] == "random"


def test_students_choose_change_and_the_chair_closes(app, coord):
    sid, com, ids = start(app, coord, "choose")
    assert seated(app, com) == {}
    a, b = join_as(app, ids[0]), join_as(app, ids[1])
    page = a.get(f"/live/{sid}").text                                              # on today's list: may open it with no country
    assert "Choose your country" in page and "No one yet" in page and "/live/%d/country" % sid in page
    assert f"/live/{sid}" in a.get("/me").text
    console = coord.get(f"/chair/{sid}").text
    assert "Countries: Students choose" in console and "Still without a country (6 of 6)" in console and ".." not in console.split("Still without")[1].split("</p>")[0]
    dels = {r["iso3"]: r["id"] for r in db_rows(app, "SELECT id, iso3 FROM delegation WHERE committee_id = ?", (com,))}
    a.post(f"/live/{sid}/country", {"delegation_id": str(dels["FRA"])})
    b.post(f"/live/{sid}/country", {"delegation_id": str(dels["FRA"])})
    s = seated(app, com)
    assert s[ids[0]]["iso3"] == "FRA" and s[ids[0]]["role"] == "head" and s[ids[1]]["role"] == "delegate"
    assert "Change your country" in a.get(f"/live/{sid}").text
    a.post(f"/live/{sid}/country", {"delegation_id": str(dels["CHN"])})               # the head moves: the other leads France
    s = seated(app, com)
    assert s[ids[0]]["iso3"] == "CHN" and s[ids[1]]["role"] == "head"
    coord.post(f"/chair/{sid}/countries", {"op": "close"})
    s = seated(app, com)
    assert set(s) == set(ids)                                                      # the four who hadn't chosen were seated
    r = b.post(f"/live/{sid}/country", {"delegation_id": str(dels["USA"])})
    assert r.status_code == 409 and seated(app, com)[ids[1]]["iso3"] == "FRA"      # closed: no more changes
    assert "Choose your country" not in a.get(f"/live/{sid}").text


def test_a_country_holds_at_most_four(app, coord):
    sid, com, ids = start(app, coord, "choose", n=6)
    did = db_one(app, "SELECT id FROM delegation WHERE committee_id = ? AND iso3 = 'USA'", (com,))["id"]
    for i in ids[:4]:
        join_as(app, i).post(f"/live/{sid}/country", {"delegation_id": str(did)})
    r = join_as(app, ids[4]).post(f"/live/{sid}/country", {"delegation_id": str(did)})
    assert r.status_code == 409 and ids[4] not in seated(app, com)


def test_chair_assigns_and_can_switch_ways(app, coord):
    sid, com, ids = start(app, coord, "chair")
    assert seated(app, com) == {}
    a = join_as(app, ids[0])
    page = a.get(f"/live/{sid}").text
    assert "Your teacher will give you one" in page and "Choose your country" not in page
    assert any(f'value="{i}"' in coord.get(f"/mun/committees/{com}").text for i in ids)   # today's students can be seated there
    coord.post(f"/chair/{sid}/countries", {"op": "open"})
    assert "Choose your country" in a.get(f"/live/{sid}").text
    coord.post(f"/chair/{sid}/countries", {"op": "random"})
    assert set(seated(app, com)) == set(ids)


def test_only_todays_students_and_only_this_committee(app, coord):
    sid, com, ids = start(app, coord, "choose", n=3)
    other = db_one(app, "SELECT id FROM student WHERE active = 1 AND id NOT IN (%s) AND class_id != (SELECT class_id FROM committee "
                        "WHERE id = ?) ORDER BY id LIMIT 1" % ",".join(map(str, ids)), (com,))
    if other:
        assert join_as(app, other["id"]).get(f"/live/{sid}").status_code == 403
    with pytest.raises(UserError):
        with app.state.db.write(SYSTEM) as w:
            CH.choose(w, com, ids[0], 999999)


def test_erasing_a_student_removes_them_from_the_list(app, coord):
    sid, com, ids = start(app, coord, "choose", n=2)
    from app.retention import erase_student
    with app.state.db.write(SYSTEM) as w:
        erase_student(w, ids[0])
    assert not db_one(app, "SELECT 1 AS x FROM committee_roster WHERE student_id = ?", (ids[0],))


def test_my_country_panel_is_on_every_tab(app, coord):
    """D-095: a student's country, its alignments (with who else in the room shares them) and its likely leanings, in a
    panel above the tabs that the student opens and closes at will."""
    sid, com, ids = start(app, coord, "choose", n=2)
    a = join_as(app, ids[0])
    assert 'id="my-country"' not in a.get(f"/live/{sid}").text                    # no country yet: nothing to show
    fra = db_one(app, "SELECT id FROM delegation WHERE committee_id = ? AND iso3 = 'FRA'", (com,))["id"]
    a.post(f"/live/{sid}/country", {"delegation_id": str(fra)})
    for tab in ("floor", "messages", "speech", "friends"):
        page = a.get(f"/live/{sid}?tab={tab}").text
        assert 'id="my-country"' in page and 'data-remember="my-country"' in page and "My country: France" in page
    assert "permanent member" in page and "NATO" in page and "Also in this room:" in page
    assert "United Kingdom" in page.split('id="my-country"')[1].split("</details>")[0]   # a NATO partner in this committee
    assert "estimate" in page and "entered from memory" in page
    assert f"/me/committees/{com}/prepare" in page
