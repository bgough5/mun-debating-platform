"""D-088: rehearse from cue cards, teacher comments on each debate team, and a prep overview by saved group or year."""
import re

from app.fakedata import DEMO_STAFF_PASSPHRASE
from tests.api.helpers import join_as
from tests.api.test_speech_cards import _case, _debate, free_speech, students
from tests.conftest import Client, db_one, db_rows, login_staff


def test_rehearse_from_the_cue_cards_one_at_a_time(app):
    st = join_as(app, students(app, 1)[0])
    sid = free_speech(st)
    st.post(f"/me/cards/speech/{sid}", {"op": "save", "mode": "dots", "h_0": "Open", "b_0": "Greet the room\nState the case",
                                        "h_1": "Close", "b_1": "Thank them"})
    page = st.get(f"/me/cards/speech/{sid}/rehearse?mode=dots").text
    assert "<title>Rehearse: Uniforms" in page and "Card 1 of 2" in page
    assert "Greet the room" in page and "Thank them" in page and "data-rehearse" in page and "data-practice" in page
    assert 'value="120"' in page                                              # the speech's own target time
    assert f'href="/me/cards/speech/{sid}/rehearse?mode=dots"' in st.get(f"/me/cards/speech/{sid}?mode=dots").text
    assert join_as(app, students(app, 2)[1]).get(f"/me/cards/speech/{sid}/rehearse").status_code in (403, 404)


def test_rehearse_time_comes_from_the_speech_length_for_cases():
    from app.modules.debating.cuecards import target_seconds
    words = " ".join(["word"] * 260)                                          # 2 minutes at 130 words a minute
    assert target_seconds(None, "case", 0, [("", words)]) == 120
    assert target_seconds(None, "mun", 0, [("", "Short.")]) == 60


def test_teacher_comments_on_each_team_and_only_that_team_sees_it(app, coord):
    run, sides = _debate(app, coord)
    aff = [s for s, side in sides.items() if side == "aff"]
    neg = [s for s, side in sides.items() if side == "neg"]
    _case(app, join_as(app, aff[0]), run, "aff", "Uniforms cut the cost of school for families")
    page = coord.get(f"/debating/runs/{run['id']}/teams").text
    assert "Teams' preparation" in page and "Uniforms cut the cost of school for families" in page
    assert f'href="/debating/runs/{run["id"]}/teams"' in coord.get(f"/debating/runs/{run['id']}").text
    coord.post(f"/debating/runs/{run['id']}/teams", {"side": "aff", "comment": "Strong start. Split cost and community between you."})
    assert "Split cost and community" in join_as(app, aff[1]).get(f"/me/team/{run['id']}").text
    assert "Split cost and community" not in join_as(app, neg[0]).get(f"/me/team/{run['id']}").text
    assert coord.post(f"/debating/runs/{run['id']}/teams", {"side": "both", "comment": "x"}).status_code == 400
    assert join_as(app, aff[0]).get(f"/debating/runs/{run['id']}/teams", follow_redirects=False).status_code in (303, 401, 403)


def test_staff_comment_on_teams_only_for_runs_they_can_open(app, coord):
    run, _ = _debate(app, coord)
    staff_id = db_one(app, "SELECT id FROM staff WHERE name = 'Demo Chair'")["id"]
    club = db_one(app, "SELECT id FROM class WHERE code = 'DEMO3C'")["id"]
    with app.state.db.write(None) as w:
        w.conn.execute("DELETE FROM staff_class WHERE staff_id = ? AND class_id != ?", (staff_id, club))
    t = login_staff(Client(app, base_url="http://testserver").__enter__(), staff_id, DEMO_STAFF_PASSPHRASE)
    assert t.get(f"/debating/runs/{run['id']}/teams").status_code == 403
    assert t.post(f"/debating/runs/{run['id']}/teams", {"side": "aff", "comment": "x"}).status_code == 403


def test_prep_overview_for_a_saved_group_or_a_year(app, coord):
    ids = students(app, 3)
    st = join_as(app, ids[0])
    free_speech(st)
    r = coord.post("/people/groups", {"op": "create", "group_name": "Debating Jr BGO", "student_id": [str(i) for i in ids]},
                   follow_redirects=False)
    gid = int(r.headers["location"].rsplit("/", 1)[1])
    home = coord.get("/debating").text
    assert f'value="group:{gid}"' in home and 'value="year:' in home
    page = coord.get(f"/debating/prep?who=group:{gid}").text
    assert "<title>Student preparation: Debating Jr BGO" in page
    rows_ = re.findall(r'<th scope="row">', page)
    assert len(rows_) == 3 and "Uniforms" in page and "Last saved" in page
    y = db_one(app, "SELECT year_level FROM student WHERE id = ?", (ids[0],))["year_level"]
    n = db_one(app, "SELECT COUNT(*) AS n FROM student WHERE year_level = ? AND active = 1 AND deleted_at IS NULL", (y,))["n"]
    assert len(re.findall(r'<th scope="row">', coord.get(f"/debating/prep?who=year:{y}").text)) == n
    assert coord.get("/debating/prep", follow_redirects=False).status_code == 303
    assert coord.get("/debating/prep?who=group:99999").status_code == 404


def test_case_speech_shows_in_the_overview(app, coord):
    run, sides = _debate(app, coord, 2)
    me = next(iter(sides))
    _case(app, join_as(app, me), run, sides[me], "Uniforms make mornings easier", "One two three four five.")
    y = db_one(app, "SELECT year_level FROM student WHERE id = ?", (me,))["year_level"]
    assert "speech 5 words" in coord.get(f"/debating/prep?who=year:{y}").text
