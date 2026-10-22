"""Phase 6 in a real browser: the guided committee session end to end, the whip count, the debrief and practice v3.
axe (WCAG 2.2 AA) runs on every new screen; live updates carry the stage to the student without a reload."""
import re

import pytest

from tests.ui.conftest import axe
from tests.ui.test_phase2_ui import ga_member, join, open_session, q

pytestmark = pytest.mark.ui


def _no_bad(page, name):
    bad = axe(page, name)
    assert bad == [], [(v["id"], v["impact"], [n["target"] for n in v["nodes"][:3]]) for v in bad]


def _jump(chair, code):
    if not chair.locator("#jump").is_visible():
        chair.click("summary:has-text('Jump to a stage')")
    chair.select_option("#jump", code)
    chair.click("details:has(#jump) button:has-text('Go')")


def test_guided_session_whip_and_debrief(browser, live):
    m = ga_member(live, 0)
    chair = browser.new_context().new_page()
    sid = open_session(chair, live, m["committee_id"])
    _no_bad(chair, "p6_chair_guide_roll_call")
    student = browser.new_context().new_page()
    join(student, live, m["student_id"])
    student.goto(f"{live.url}/live/{sid}")
    student.wait_for_selector("text=What you can do now")
    _no_bad(student, "p6_student_roll_call")
    student.click("button:has-text('Present and voting')")
    student.wait_for_selector("text=You answered")
    chair.click("button:has-text('Answer for delegations without a student')")
    chair.wait_for_selector("text=computed")
    # Stage changes reach the student without a reload.
    chair.click("button:has-text('Next: Setting the agenda')")
    student.wait_for_selector("text=Now: Setting the agenda", timeout=10000)
    chair.fill("#ag", "Climate finance")
    chair.click("button:has-text('Set the agenda')")
    chair.wait_for_selector("text=Climate finance")
    _no_bad(chair, "p6_chair_guide_agenda")
    _jump(chair, "voting_procedure")
    chair.wait_for_selector("text=Start the whip count")
    chair.click("button:has-text('Start the whip count')")
    chair.wait_for_selector("text=predictions made")
    student.wait_for_selector("text=Whip count:", timeout=10000)
    _no_bad(student, "p6_student_whip")
    for btn in student.locator("#live-main form[action*='/whip/'] button:has-text('Yes')").all():
        btn.click()
        student.wait_for_load_state("networkidle")
    chair.click("button:has-text('Lock predictions and open the vote')")
    chair.wait_for_selector("text=Close voting and announce")
    student.wait_for_selector("#h-vote", timeout=10000)
    student.click("#live-main button[name='vote'][value='yes']")
    student.wait_for_selector("text=Your delegation voted")
    chair.click("button:has-text('Close voting and announce')")
    chair.wait_for_selector("text=Result:")
    _jump(chair, "debrief")
    chair.click("a:has-text('Show the debrief')")
    chair.wait_for_selector("h1:has-text('Debrief')")
    assert "How the engine did on this vote" in chair.content()
    _no_bad(chair, "p6_chair_debrief")
    student.wait_for_selector("a:has-text('See your debrief')", timeout=10000)
    student.click("a:has-text('See your debrief')")
    student.wait_for_selector("h1:has-text('Debrief')")
    assert "Whip count: your predictions" in student.content()
    _no_bad(student, "p6_student_debrief")
    # The projector shows the stage.
    tok = q(live, "SELECT projector_token FROM live_session WHERE id = ?", (sid,))[0]["projector_token"]
    chair.goto(f"{live.url}/projector/{tok}")
    assert "Results and debrief" in chair.content()
    _no_bad(chair, "p6_projector_stage")


def test_practice_committee_in_browser(browser, live):
    m = ga_member(live, 3)
    page = browser.new_context().new_page()
    join(page, live, m["student_id"])
    page.click("nav a:has-text('Practice committee')")
    page.wait_for_selector("h1:has-text('Practice committee')")
    _no_bad(page, "p6_practice_home")
    page.locator("form[action='/me/sim'] button:has-text('Start')").first.click()
    page.wait_for_selector("text=Lobby a delegation")
    page.click("button:has-text('Ask for their position')")
    page.wait_for_selector("blockquote.script")
    _no_bad(page, "p6_practice_lobbying")
    page.locator("button:has-text('Record my reading')").first.click()
    page.wait_for_selector("text=Update my reading")
    page.click("button:has-text('Call the vote')")
    page.wait_for_selector("text=How well you read the room")
    _no_bad(page, "p6_practice_result")
    # 320 px reflow on the practice result.
    page.set_viewport_size({"width": 320, "height": 800})
    assert page.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 1


def test_phone_stage_label_shows_the_real_stage_number(browser, live):
    """Regression: on phones only the current stage is shown, and CSS counters skip hidden items,
    so the label must come from the markup (it read "1 of 9" at stage 7)."""
    from app.db import SYSTEM
    from app.modules.chair.service import open_session as open_s
    from app.modules.sim import service as SIM
    m = ga_member(live, 5)
    with live.app.state.db.write(SYSTEM) as w:
        sid = open_s(w, m["committee_id"])
        SIM.set_stage(w, sid, "voting_procedure")
    page = browser.new_context(viewport={"width": 390, "height": 844}).new_page()
    join(page, live, m["student_id"])
    page.goto(f"{live.url}/live/{sid}")
    label = page.evaluate("() => getComputedStyle(document.querySelector('.stages li[aria-current]'), '::before').content")
    assert label == '"7 of 9:"'
