"""Smoothness (D-078): saving a form, sending a message or a live update never throws the page back to the top, and
never takes away a box someone is typing in. Measured as scroll position and focus before and after."""
import re
import time

import pytest

from app.db import Actor
from tests.ui.conftest import login
from tests.ui.test_phase2_ui import ga_member, join, q

pytestmark = pytest.mark.ui
CHAIR = Actor("coordinator", None, "Coordinator")


def _scroll_to(pg, selector):
    pg.locator(selector).scroll_into_view_if_needed()
    pg.evaluate("sel => { const el = document.querySelector(sel); window.scrollTo(0, el.getBoundingClientRect().top + scrollY - 200); }", selector)
    time.sleep(0.2)
    return pg.evaluate("scrollY")


def test_saving_far_down_a_page_keeps_your_place(browser, live):
    sid = q(live, "SELECT id FROM student WHERE class_id = (SELECT id FROM class WHERE name LIKE 'Year 9%') ORDER BY id LIMIT 1")[0]["id"]
    ctx = browser.new_context(viewport={"width": 1366, "height": 768})
    pg = ctx.new_page()
    join(pg, live, sid)
    pg.goto(live.url + "/me/prep")
    pg.select_option("#mid", label="That zoos do more harm than good")
    pg.click("button:has-text('Start the case')")
    pg.wait_for_url(re.compile(r"/me/prep/cases/\d+"))
    pg.locator("details summary:has-text('Write a rebuttal')").nth(2).click()
    box = pg.locator("details[open] textarea[name='part_flaw']").last
    y0 = _scroll_to(pg, "details[open] textarea[name='part_flaw']")
    assert y0 > 600
    box.click()
    box.type("Most animals in zoos aren't endangered at all")
    pg.locator("details[open] button:has-text('Save my rebuttal')").last.click()
    pg.wait_for_function("document.querySelector('.flash, .toast')")
    time.sleep(0.4)
    y1 = pg.evaluate("scrollY")
    assert abs(y1 - y0) < 400, (y0, y1)                     # still where you were, not back at the top
    assert "Saved" in pg.inner_text("body")
    ctx.close()


def test_sending_a_message_keeps_your_place_and_a_refresh_never_steals_the_box(browser, live):
    from app.modules.chair import service as C
    m = ga_member(live, 4)
    with live.app.state.db.write(CHAIR) as w:
        sess = C.open_session(w, m["committee_id"])
    ctx = browser.new_context(viewport={"width": 1366, "height": 600})
    pg = ctx.new_page()
    join(pg, live, m["student_id"])
    pg.goto(live.url + f"/live/{sess}?tab=messages")
    pg.wait_for_function("document.getElementById('live-status') && /Live/.test(document.getElementById('live-status').textContent)")
    y0 = _scroll_to(pg, "#mbody")
    pg.click("#mbody")
    # A live update for the whole committee arrives while the student is in the box (nothing typed yet).
    with live.app.state.db.write(CHAIR) as w:
        C.add_speaker(w, sess, q(live, "SELECT id FROM delegation WHERE committee_id = ? AND id != ? LIMIT 1",
                                 (m["committee_id"], m["delegation_id"]))[0]["id"])
    time.sleep(1.2)
    assert pg.evaluate("document.activeElement && document.activeElement.id") == "mbody"
    pg.keyboard.type("Would you sign our amendment on reporting?")
    with live.app.state.db.write(CHAIR) as w:
        C.next_speaker(w, sess)
    time.sleep(1.2)
    assert pg.input_value("#mbody") == "Would you sign our amendment on reporting?"
    assert abs(pg.evaluate("scrollY") - y0) < 50
    y1 = pg.evaluate("scrollY")
    pg.click("#live-messages button:has-text('Send')")
    pg.wait_for_function("document.body.innerText.includes('Would you sign our amendment on reporting?') && !document.querySelector('#mbody').value")
    time.sleep(0.5)
    assert abs(pg.evaluate("scrollY") - y1) < 400, (y1, pg.evaluate("scrollY"))
    ctx.close()


def test_switching_pages_still_starts_at_the_top(browser, live):
    ctx = browser.new_context(viewport={"width": 1366, "height": 600})
    pg = ctx.new_page()
    login(pg, live)
    pg.goto(live.url + "/debating")
    pg.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    pg.click("a:has-text('New speaking round')")
    pg.wait_for_url(re.compile(r"/debating/runs/new"))
    time.sleep(0.3)
    assert pg.evaluate("scrollY") < 50
    ctx.close()


def test_a_refresh_waits_while_someone_is_in_a_box_in_that_region(browser, live):
    """The points box sits in the committee's main region, which refreshes on every change: clicking into it must
    hold refreshes back until the student leaves it, even before they type."""
    from app.modules.chair import service as C
    m = ga_member(live, 5)
    with live.app.state.db.write(CHAIR) as w:
        sess = C.open_session(w, m["committee_id"])
    ctx = browser.new_context(viewport={"width": 1366, "height": 600})
    pg = ctx.new_page()
    join(pg, live, m["student_id"])
    pg.goto(live.url + f"/live/{sess}?tab=points")
    pg.wait_for_function("/Live/.test(document.getElementById('live-status').textContent)")
    pg.click("#pnote")
    y0 = pg.evaluate("scrollY")
    seq0 = int(pg.get_attribute("#live-main [data-view-seq]", "data-view-seq"))
    other = q(live, "SELECT id FROM delegation WHERE committee_id = ? AND id != ? LIMIT 1", (m["committee_id"], m["delegation_id"]))[0]["id"]
    with live.app.state.db.write(CHAIR) as w:
        C.add_speaker(w, sess, other)
    time.sleep(1.5)
    assert pg.evaluate("document.activeElement && document.activeElement.id") == "pnote"
    assert int(pg.get_attribute("#live-main [data-view-seq]", "data-view-seq")) == seq0      # held back
    assert abs(pg.evaluate("scrollY") - y0) < 5
    pg.locator("h1").click()                                # leaving the box lets the held-back update through
    pg.wait_for_function(f"+document.querySelector('#live-main [data-view-seq]').getAttribute('data-view-seq') > {seq0}", timeout=5000)
    assert abs(pg.evaluate("scrollY") - y0) < 5
    # Typing holds updates until the point is sent (unsaved words are never lost).
    pg.click("#pnote")
    pg.keyboard.type("Point of order on the time")
    with live.app.state.db.write(CHAIR) as w:
        C.next_speaker(w, sess)
    time.sleep(1.5)
    assert pg.input_value("#pnote") == "Point of order on the time"
    ctx.close()
