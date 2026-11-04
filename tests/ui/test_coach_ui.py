"""D-100 in a real browser: the speech coach counts and marks as the student types, its marks line up with the
writing, it can be hidden (and stays hidden), and Model UN phrases go in where the cursor is, with the country's name."""
import re

import pytest

from tests.ui.conftest import axe, login
from tests.ui.test_phase2_ui import ga_member, join, q

pytestmark = pytest.mark.ui

TEXT = ("Why should we care? Climate change is real and climate change is here. It is really very serious. "
        "Climate scientists agree, and according to research one in four farms has lost crops.\n\n"
        "We must act now, together, for our schools, our farms and our future.")


def new_speech(page, live, sid):
    join(page, live, sid)
    page.goto(live.url + "/me/prep")
    page.check("input[name=template_code][value=free]")
    page.fill("#stt", "Coach test")
    page.click("button:has-text('Start writing')")
    page.wait_for_url(re.compile(r"/me/prep/speeches/\d+$"), wait_until="commit")
    page.wait_for_selector("[data-coach-ready] [data-coach]")


def test_the_coach_counts_marks_and_hides(page, live):
    sid = q(live, "SELECT id FROM student WHERE active = 1 ORDER BY id DESC LIMIT 1")[0]["id"]
    new_speech(page, live, sid)
    box = page.locator("textarea[name=sec_speech]")
    box.fill(TEXT)
    words = len(TEXT.split())
    page.wait_for_function(f"document.querySelector('[data-c-stat=words]').textContent === '{words}'")
    assert page.inner_text("[data-c-time]") == "0:" + f"{round(words / 130 * 60):02d}"
    check = page.inner_text("[data-c-panel=check]")
    assert "climate" in check and "×3" in check and "really" in check          # repeats and fillers listed
    page.click("[data-c-tab=tech]")
    for code in ("question", "three", "inclusive", "numbers", "source", "action"):
        assert "used" in page.get_attribute(f"[data-c-tech={code}]", "class"), code
    assert "used" not in (page.get_attribute("[data-c-tech=contrast]", "class") or "")
    # Marks are drawn behind the text box, exactly over it.
    page.click("[data-c-mark=repeat]")
    page.wait_for_selector(".coach-back mark.cm-repeat")
    tb, bd = box.bounding_box(), page.locator(".coach-back").bounding_box()
    assert all(abs(tb[k] - bd[k]) < 1 for k in ("x", "y", "width", "height")), (tb, bd)
    first = page.locator(".coach-back mark.cm-repeat").first
    assert first.inner_text().lower() == "climate"
    # Clicking a technique shows only where it was used.
    page.click("[data-c-spot='tech:question']")
    page.wait_for_selector(".coach-back mark.cm-spot")
    assert page.locator(".coach-back mark.cm-spot").first.inner_text() == "Why should we care?"
    assert not axe(page, "coach_speech")
    # Hide it: the writing takes the full width, and it stays hidden after a reload.
    page.click("[data-coach-toggle]")
    assert page.locator("[data-coach-body]").is_hidden() and page.locator(".coach-back").count() == 0
    page.reload()
    page.wait_for_selector("[data-coach-ready]")
    assert page.locator("[data-coach-body]").is_hidden()
    page.click("[data-coach-toggle]")
    assert page.locator("[data-coach-body]").is_visible()


def test_model_un_phrases_go_in_at_the_cursor_with_the_country(page, live):
    m = ga_member(live)
    country = q(live, "SELECT name FROM country WHERE iso3 = ?", (m["iso3"],))[0]["name"]
    join(page, live, m["student_id"])
    page.goto(live.url + f"/me/committees/{m['committee_id']}/prepare")
    page.wait_for_selector("[data-coach-ready]")
    box = page.locator("#ob")
    box.fill("")
    page.click("[data-c-tab=phrases]")
    page.click("summary:has-text('Your position')")
    page.click(f"button.phrase:has-text('{country} firmly believes that')")
    page.keyboard.type("climate finance must come first.")
    assert box.input_value() == f"{country} firmly believes that climate finance must come first."
    box.press("Control+End")
    page.click("button.phrase:has-text('Honourable Chair, distinguished delegates,')")
    assert box.input_value().endswith("first. Honourable Chair, distinguished delegates, ")
    box.fill("I think my country should act.")
    page.click("[data-c-tab=check]")
    page.wait_for_selector("[data-c-panel=check]:has-text('Speaking for your country')")
    assert not axe(page, "coach_mun_prepare")


def test_teachers_see_the_marks_read_only(page, live):
    sid = q(live, "SELECT id FROM student WHERE active = 1 ORDER BY id DESC LIMIT 1 OFFSET 1")[0]["id"]
    new_speech(page, live, sid)
    page.fill("textarea[name=sec_speech]", TEXT)
    page.evaluate("window.socAutosaveNow()")
    page.wait_for_selector("[data-autosave-status]:has-text('Saved automatically')")
    speech = page.url.rsplit("/", 1)[1]
    page.context.clear_cookies()
    login(page, live)
    page.goto(live.url + f"/debating/prep/speeches/{speech}")
    page.wait_for_selector("[data-coach-ready]")
    assert page.locator("[data-c-tab=phrases]").count() == 0
    page.click("[data-c-mark=filler]")
    page.wait_for_selector(".coach-read mark.cm-filler")
    assert not axe(page, "coach_staff")
