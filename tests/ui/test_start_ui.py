"""Start an activity (D-084 stage 2) in a real browser: tick a whole year, the count keeps up, and Start opens the run."""
import re

import pytest

from tests.ui.conftest import axe, login

pytestmark = pytest.mark.ui


def test_tick_a_year_and_start_public_speaking(page, live):
    login(page, live)
    page.click("a.button:has-text('Start an activity')")
    page.wait_for_url(re.compile(r"/start$"))
    assert not axe(page, "start_activity")
    block = page.locator(".year-block").first
    n = block.locator("input[type=checkbox]").count()
    assert n > 0
    block.locator("[data-tick-all]").click()
    assert page.inner_text("[data-tick-count]") == f"{n} ticked"
    block.locator("input[type=checkbox]").first.uncheck()
    assert page.inner_text("[data-tick-count]") == f"{n - 1} ticked"
    # Find by name: only matching students show, and anyone already ticked stays ticked.
    name = page.locator(".year-block .checks label").nth(3).inner_text().strip()
    page.fill("#find-name", name)
    visible = [t.strip() for t in page.locator(".year-block .checks label:visible").all_inner_texts()]
    assert visible and all(name.lower() in t.lower() for t in visible)
    assert page.inner_text("[data-tick-count]") == f"{n - 1} ticked"
    page.fill("#find-name", "zzzz")
    assert page.is_visible("[data-find-none]")
    page.fill("#find-name", "")
    page.select_option("#find-year", "yr-9")
    assert page.locator(".year-block:visible").count() == 1
    assert page.get_attribute(".year-block:visible", "data-year") == "yr-9"
    page.select_option("#find-year", "")
    page.check("input[name=kind][value=speeches]")
    page.check("input[name=level][value=junior]")
    page.click("button[name=op][value=start]")
    page.wait_for_url(re.compile(r"/debating/runs/\d+$"), wait_until="commit")     # a boosted page fires no load event
    page.wait_for_selector("text=Public speaking ready")
    assert f"Public speaking ready: {n - 1} speaker(s), 1:30 each" in page.inner_text("body")


def test_resume_from_the_dashboard(page, live):
    login(page, live)
    page.goto(live.url + "/start")
    block = page.locator(".year-block").first
    block.locator("[data-tick-all]").click()
    page.check("input[name=kind][value=speeches]")
    page.click("button[name=op][value=start]")
    page.wait_for_url(re.compile(r"/debating/runs/\d+$"), wait_until="commit")
    page.wait_for_selector("text=Public speaking ready")
    page.goto(live.url + "/")
    page.locator("a.button:has-text('Resume')").first.click()
    page.wait_for_url(re.compile(r"/start/resume/run/\d+$"), wait_until="commit")
    page.wait_for_selector("h1:has-text(\"Who's here today?\")")
    assert not axe(page, "resume_activity")
    n = int(page.inner_text("[data-tick-count]").split()[0])
    page.locator("input[name=student_id]:checked").first.uncheck()
    page.click("button[name=op][value=resume]")
    page.wait_for_url(re.compile(r"/debating/runs/\d+$"), wait_until="commit")
    page.wait_for_selector("text=Welcome back")
    assert "1 away taken out of the order" in page.inner_text("body") and n > 1


def test_save_and_tick_a_group(page, live):
    login(page, live)
    page.goto(live.url + "/people/groups")
    page.wait_for_selector("h1:has-text('Groups')")
    assert not axe(page, "groups")
    page.fill("#ng", "Debating Jr BGO")
    boxes = page.locator(".year-block").first.locator("input[type=checkbox]")
    for i in range(3):
        boxes.nth(i).check()
    page.click("button[name=op][value=create]")
    page.wait_for_url(re.compile(r"/people/groups/\d+$"), wait_until="commit")
    page.wait_for_selector("h1:has-text('Debating Jr BGO')")
    assert not axe(page, "group")
    page.click("a.button:has-text('Start an activity with this group')")
    page.wait_for_url(re.compile(r"/start\?group=\d+$"), wait_until="commit")
    page.wait_for_selector("[data-tick-count]:has-text('3 ticked')")
    page.locator("input[name=student_id]:checked").first.uncheck()
    page.click("button[name=tick_group]:has-text('Debating Jr BGO')")
    page.wait_for_selector("text=Ticked Debating Jr BGO: 3 students.")
    assert page.locator("input[name=student_id]:checked").count() == 3
