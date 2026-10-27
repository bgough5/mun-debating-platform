"""Committee flow v4 (D-068) in a real browser: the student tabs (keyboard and axe), messages arriving live,
the amendment board, friends and foes, and the prepare page. axe (WCAG 2.2 AA) runs on every new screen."""
import pytest

from tests.ui.conftest import axe, login
from tests.ui.test_phase2_ui import ga_member, join, q

pytestmark = pytest.mark.ui


def _no_bad(page, name):
    bad = axe(page, name)
    assert bad == [], [(v["id"], v["impact"], [n["target"] for n in v["nodes"][:3]]) for v in bad]


def _floor_session(live, committee_id):
    from app.db import SYSTEM
    from app.modules.chair.service import open_session
    from app.modules.sim import service as SIM
    with live.app.state.db.write(SYSTEM) as w:
        sid = open_session(w, committee_id)
        SIM.set_stage(w, sid, "floor")
    return sid


def test_student_tabs_keyboard_messages_and_axe(browser, live):
    m1 = ga_member(live, 10)
    m2 = next(ga_member(live, i) for i in range(11, 40) if ga_member(live, i)["delegation_id"] != m1["delegation_id"])
    sid = _floor_session(live, m1["committee_id"])
    a = browser.new_context().new_page()
    join(a, live, m1["student_id"])
    a.goto(f"{live.url}/live/{sid}")
    a.wait_for_selector("[role=tablist]")
    _no_bad(a, "p8_tab_floor")
    # Keyboard: arrow keys move between tabs; the panel follows; the address remembers the tab.
    a.focus("#tab-floor")
    a.keyboard.press("ArrowRight")
    assert a.evaluate("document.activeElement.id") == "tab-motions"
    assert a.is_visible("#p-motions") and not a.is_visible("#p-floor")
    assert "tab=motions" in a.url
    _no_bad(a, "p8_tab_motions")
    a.keyboard.press("End")
    assert a.evaluate("document.activeElement.id") == "tab-friends" and a.is_visible("#p-friends")
    for tab in ("points", "messages", "speech", "amendments"):
        a.click(f"#tab-{tab}")
        assert a.is_visible(f"#p-{tab}")
        _no_bad(a, f"p8_tab_{tab}")
    # A message from another delegation arrives without a reload, and the tab stays put through live refreshes.
    b = browser.new_context().new_page()
    join(b, live, m2["student_id"])
    b.goto(f"{live.url}/live/{sid}?tab=messages")
    b.select_option("#mto", str(m1["delegation_id"]))
    b.fill("#mbody", "Shall we co-sponsor an amendment to clause 2?")
    b.click("#p-messages button:has-text('Send')")
    a.click("#tab-messages")
    a.wait_for_selector("text=co-sponsor an amendment", timeout=10000)
    b.goto(f"{live.url}/live/{sid}?tab=points")
    b.click("#p-points button:has-text('Raise the point')")
    a.wait_for_timeout(1500)                     # the session channel refreshes #live-main
    assert a.is_visible("#p-messages") and not a.is_visible("#p-floor")


def test_amendment_board_friends_foes_and_prepare(browser, live):
    m = ga_member(live, 12)
    page = browser.new_context().new_page()
    join(page, live, m["student_id"])
    cid = m["committee_id"]
    page.goto(f"{live.url}/me/committees/{cid}/prepare")
    page.wait_for_selector("h1:has-text('Prepare')")
    _no_bad(page, "p8_prepare")
    page.fill("#ob", "Distinguished delegates, our delegation believes adaptation finance must reach the most vulnerable.")
    page.click("button:has-text('Save')")
    page.wait_for_selector("text=words: about")
    page.goto(f"{live.url}/mun/committees/{cid}/amendments")
    page.wait_for_selector("h1:has-text('Amendments')")
    _no_bad(page, "p8_board")
    page.fill("#ntx", "Calls upon all Member States to report every two years.")
    page.click("button:has-text('Submit now')")
    page.wait_for_selector("text=everyone can see it now")
    assert page.locator(".paragraph.diff ins").count() >= 1
    _no_bad(page, "p8_board_with_amendment")
    page.goto(f"{live.url}/me/committees/{cid}/friends-foes")
    page.wait_for_selector("h1:has-text('Friends and foes')")
    _no_bad(page, "p8_friends_foes")
    page.locator("table.ff input[value='friend']").first.check()
    page.click("button:has-text('Save my reading')")
    page.wait_for_selector("text=Saved your reading of 1")


def test_chair_floor_console_and_messages_axe(browser, live):
    m = ga_member(live, 13)
    sid = _floor_session(live, m["committee_id"])
    page = browser.new_context().new_page()
    login(page, live)
    page.goto(f"{live.url}/chair/{sid}")
    page.wait_for_selector("text=Are there any points or motions on the floor?")
    _no_bad(page, "p8_chair_floor")
    page.goto(f"{live.url}/chair/{sid}/messages")
    page.wait_for_selector("h1:has-text('Delegate messages')")
    _no_bad(page, "p8_chair_messages")
    tok = q(live, "SELECT projector_token FROM live_session WHERE id = ?", (sid,))[0]["projector_token"]
    page.goto(f"{live.url}/projector/{tok}")
    _no_bad(page, "p8_projector_floor")
