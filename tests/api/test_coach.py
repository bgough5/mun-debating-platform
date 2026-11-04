"""D-100: the speech coach beside every speech box. Its techniques are word patterns (checked here against their own
examples, in Python's re, which reads them the way the browser does); its phrase bank fills in the student's country;
teachers get the same panel read-only, with no phrases to add."""
import json
import re

import pytest

from app.web import coach as C
from tests.api.helpers import ga, join_as, member_of
from tests.api.test_speech_cards import free_speech
from tests.conftest import db_one, db_rows

# A sentence that should be spotted for each technique, and one that shouldn't.
CASES = {
    "question": ("Who will speak for them?", "We will speak for them."),
    "three": ("It is cheaper, fairer and faster.", "It is cheaper and faster."),
    "inclusive": ("This is our school.", "This is the school."),
    "direct": ("You have felt this too.", "Everyone has felt this."),
    "numbers": ("One in four students skips breakfast, about 25% of us.", "Some students skip breakfast."),
    "source": ("According to the Bureau, rain is falling.", "Rain is falling."),
    "emotive": ("It was a devastating loss.", "It was a loss."),
    "story": ("Imagine walking into class on day one.", "Walk into class."),
    "contrast": ("Not a cost, but an investment.", "A cost and an investment."),
    "action": ("Today, I urge you to vote yes.", "Today is Tuesday."),
    "signpost": ("My second argument is simple.", "The second bus is late."),
    "rebuttal": ("Our opponents told you that zoos protect animals.", "Zoos protect animals."),
    "diplomatic": ("Honourable Chair, distinguished delegates.", "Hello everyone."),
    "clauses": ("Operative clause 3 must go further.", "It must go further."),
}


def pattern(code):
    return next(t[4] for t in C.TECHNIQUES if t[0] == code)


@pytest.mark.parametrize("code", sorted(CASES))
def test_each_technique_spots_its_example_and_not_a_plain_sentence(code):
    yes, no = CASES[code]
    rx = re.compile(pattern(code), re.I)
    assert rx.search(yes), (code, yes)
    assert not rx.search(no), (code, no)


def test_every_pattern_compiles_and_every_example_is_spotted():
    for code, name, what, example, pat, kinds in C.TECHNIQUES:
        assert set(kinds) <= set(C.KINDS) and name and what
        if pat:
            assert re.compile(pat, re.I).search(example), (code, example)      # the example on the card shows the pattern


def test_config_per_kind_fills_the_country_and_drops_phrases_for_teachers():
    mun = C.coach_config("mun", country="Kenya")
    lines = [p for g in mun["phrases"] for p in g["lines"]]
    assert any(p.startswith("The delegation of Kenya") for p in lines) and not any("{country}" in p for p in lines)
    assert any("Point of information" in p for p in lines) and mun["first_person"]
    assert {t["code"] for t in mun["techniques"]} >= {"diplomatic", "clauses"} and "rebuttal" not in {t["code"] for t in mun["techniques"]}
    debate = C.coach_config("debate", team_line="Zoos are prisons")
    assert debate["team_line"] == "Zoos are prisons" and "rebuttal" in {t["code"] for t in debate["techniques"]}
    assert C.coach_config("speech", readonly=True)["phrases"] == []
    assert C.coach_config("nonsense")["kind"] == "speech"
    assert C.DEFAULT_AIM["mun"] == 90 and 130 in dict(C.PACES)


def _panel(html):
    m = re.search(r'<script type="application/json" data-coach-config>(.*?)</script>', html, re.S)
    assert m, "no speech coach on the page"
    return json.loads(m.group(1))


def test_the_coach_sits_beside_a_prepared_speech_and_a_debate_speech(app, coord):
    st = db_rows(app, "SELECT id FROM student WHERE active = 1 ORDER BY id LIMIT 1")[0]["id"]
    c = join_as(app, st)
    sid = free_speech(c)
    page = c.get(f"/me/prep/speeches/{sid}").text
    cfg = _panel(page)
    assert cfg["kind"] == "speech" and not cfg["readonly"] and 'data-coach-text' in page and "Speech coach" in page
    assert "<select data-c-aim>" not in page                    # the speech has its own target length; the coach reads it
    staff = coord.get(f"/debating/prep/speeches/{sid}").text
    assert _panel(staff)["readonly"] and 'class="coach-read" data-coach-text' in staff and "data-c-insert" not in staff
    mid = db_one(app, "SELECT id FROM motion_bank WHERE motion LIKE 'That zoos%'")["id"]
    c.post("/me/prep/cases", {"motion_id": mid, "side": "aff"})
    case = db_one(app, "SELECT id FROM prep_case WHERE student_id = ? ORDER BY id DESC LIMIT 1", (st,))["id"]
    c.post(f"/me/prep/cases/{case}", {"team_line": "Zoos are prisons", "definition": ""})
    c.post(f"/me/prep/cases/{case}", {"speech_text": "Our opponents told you that zoos are safe."})
    page = c.get(f"/me/prep/cases/{case}").text
    cfg = _panel(page)
    assert cfg["kind"] == "debate" and cfg["team_line"] == "Zoos are prisons" and "Our opponents told you that … But …" in page
    staff = coord.get(f"/debating/prep/cases/{case}").text
    assert _panel(staff)["readonly"] and "Our opponents told you that zoos are safe." in staff


def test_the_coach_sits_beside_model_un_speeches_with_the_countrys_name(app, coord):
    com = ga(app)
    m = member_of(app, com["id"])[0]
    name = db_one(app, "SELECT name FROM country WHERE iso3 = ?", (m["iso3"],))["name"]
    a = join_as(app, m["student_id"])
    page = a.get(f"/me/committees/{com['id']}/prepare").text
    cfg = _panel(page)
    assert cfg["kind"] == "mun" and cfg["aim"] == 90
    assert f"The delegation of {name} thanks the Chair" in page
