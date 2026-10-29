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
