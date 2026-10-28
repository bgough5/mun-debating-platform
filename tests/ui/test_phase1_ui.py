"""Phase 1 UI: axe on every Phase 1 screen (0 serious/critical), keyboard checks, W-1 clicked through in a browser."""
import re

import pytest

from tests.ui.conftest import axe, login

pytestmark = pytest.mark.ui


def _ids(live):
    with live.app.state.db.read() as conn:
        com = conn.execute("SELECT id FROM committee WHERE name LIKE 'United Nations General Assembly%'").fetchone()[0]
        res = conn.execute("SELECT id FROM resolution WHERE committee_id = ?", (com,)).fetchone()[0]
        para = conn.execute("SELECT id FROM paragraph WHERE resolution_id = ? AND kind='operative' AND position = 6", (res,)).fetchone()[0]
        am = conn.execute("SELECT id FROM amendment WHERE paragraph_id = ?", (para,)).fetchone()[0]
        cls = conn.execute("SELECT id FROM class LIMIT 1").fetchone()[0]
        st = conn.execute("SELECT id FROM student LIMIT 1").fetchone()[0]
    return com, res, para, am, cls, st


PHASE1_PAGES = [
    "/", "/mun", "/mun/conferences/1", "/mun/committees/{com}", "/mun/resolutions/{res}",
    "/mun/paragraphs/{para}/history", "/mun/paragraphs/{para}/compare", "/mun/predict/paragraph/{para}",
    "/mun/predict/amendment/{am}", "/mun/predict/resolution/{res}", "/mun/committees/{com}/evidence",
    "/mun/votes/paragraph/{para}", "/mun/calibration", "/mun/resolutions/{res}/print",
    "/people", "/people/classes/{cls}", "/people/students/{st}", "/people/staff",
    "/admin", "/admin/t/country", "/admin/t/country/AUS", "/admin/t/voting_rule", "/admin/t/rubric_descriptor",
    "/admin/log", "/admin/data", "/admin/model", "/admin/t/country/new",
    "/practice-game", "/accessibility", "/privacy",
]


def test_axe_phase1_pages(page, live):
    com, res, para, am, cls, st = _ids(live)
    login(page, live)
    failures = {}
    for path in PHASE1_PAGES:
        url = path.format(com=com, res=res, para=para, am=am, cls=cls, st=st)
        page.goto(live.url + url)
        name = "p1" + re.sub(r"[^a-z0-9]+", "_", url.lower())
        bad = axe(page, name)
        if bad:
            failures[url] = [(v["id"], v["impact"], len(v["nodes"])) for v in bad]
    assert failures == {}


def test_axe_anonymous_pages(page, live):
    failures = {}
    for url in ("/", "/login", "/practice-game"):
        page.goto(live.url + url)
        bad = axe(page, "anon" + re.sub(r"[^a-z0-9]+", "_", url))
        if bad:
            failures[url] = [(v["id"], v["impact"]) for v in bad]
    assert failures == {}


def test_skip_link_is_first_tab_stop(page, live):
    login(page, live)
    page.goto(live.url + "/mun")
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.textContent") == "Skip to main content"
    page.keyboard.press("Enter")
    assert page.evaluate("document.activeElement.id") == "main"


def test_keyboard_only_sign_in(page, live):
    page.goto(live.url + "/login")
    page.focus("#who")
    page.keyboard.press("Tab")
    page.keyboard.type("correct horse battery staple")
    page.keyboard.press("Enter")
    page.wait_for_load_state("networkidle")
    assert "Dashboard" in page.title()


def test_works_at_320px(page, live):
    login(page, live)
    page.set_viewport_size({"width": 320, "height": 800})
    com, res, para, am, cls, st = _ids(live)
    for url in ("/", f"/mun/resolutions/{res}", f"/mun/predict/paragraph/{para}"):
        page.goto(live.url + url)
        overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        assert overflow <= 1, (url, overflow)


def test_w1_in_browser(page, live):
    """W-1 clicked through by a browser (a stand-in for Ben's own run, which is still needed)."""
    com, res, para, am, cls, st = _ids(live)
    login(page, live)
    page.goto(f"{live.url}/mun/resolutions/{res}")
    article = page.locator(f"#p{para}")
    article.locator("summary:has-text('Table an amendment')").click()
    article.locator("textarea[name=proposed_text]").fill("Suggests all wealthy developed States increase support to the Green Climate Fund, reviewed every two years.")
    article.locator("button:has-text('Table amendment')").click()
    page.wait_for_load_state("networkidle")
    assert "tabled" in page.content()
    page.goto(f"{live.url}/mun/paragraphs/{para}/compare")
    assert page.locator("table tbody tr").count() >= 3
    page.locator("table tbody tr").nth(2).locator("a").click()
    page.wait_for_load_state("networkidle")
    assert "Who decides it" in page.content()
    page.click("button:has-text('Create lobbying tasks')")
    page.wait_for_load_state("networkidle")
    page.wait_for_selector(".flash, .error-box", timeout=10000)
    assert "Created 3 lobbying task" in page.content(), page.inner_text("main")[:600]
