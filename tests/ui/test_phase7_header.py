"""Phase 7 items 5 and 6: the header fits one row on a 1366 px laptop, and on a phone the nav sits behind an
accessible Menu button (at most 130 px tall at 390×844). Without JavaScript the list simply shows."""
import pytest

from tests.ui.conftest import axe, login
from tests.ui.test_phase2_ui import ga_member, join

pytestmark = pytest.mark.ui

HEADER_H = "() => document.querySelector('header.site').getBoundingClientRect().height"
ONE_ROW = """() => {
  const tops = ['.brand', 'nav.main li:last-child', '.who'].map(s => document.querySelector(s).getBoundingClientRect());
  return tops.every(r => r.top < tops[0].bottom && r.bottom > tops[0].top);
}"""


def _staff(browser, w, h, js=True):
    pg = browser.new_context(viewport={"width": w, "height": h}, java_script_enabled=js).new_page()
    return pg


def _student(browser, live, w, h, n=7):
    pg = browser.new_context(viewport={"width": w, "height": h}).new_page()
    join(pg, live, ga_member(live, n)["student_id"])
    pg.wait_for_selector("button.menu-toggle" if w <= 700 else "nav.main")
    return pg


def test_laptop_header_is_one_row(browser, live):
    pg = _staff(browser, 1366, 768)
    login(pg, live)
    pg.goto(live.url + "/mun")
    assert pg.evaluate(ONE_ROW), pg.evaluate(HEADER_H)
    assert not pg.locator(".menu-toggle").is_visible()
    st = _student(browser, live, 1366, 768)
    assert st.evaluate(ONE_ROW), st.evaluate(HEADER_H)


def test_phone_menu_button(browser, live):
    pg = _staff(browser, 390, 844)
    login(pg, live)
    pg.goto(live.url + "/mun")
    h = pg.evaluate(HEADER_H)
    assert h <= 130, h
    btn = pg.locator("button.menu-toggle")
    assert btn.is_visible() and btn.get_attribute("aria-expanded") == "false"
    assert not pg.locator("nav.main a[href='/debating']").is_visible()
    # Keyboard: Tab from the skip link reaches the button; Enter opens; links are reachable; Escape closes and returns focus.
    pg.focus("a.brand")
    pg.keyboard.press("Tab")
    assert pg.evaluate("() => document.activeElement.classList.contains('menu-toggle')")
    pg.keyboard.press("Enter")
    assert btn.get_attribute("aria-expanded") == "true"
    assert pg.locator("nav.main a[href='/debating']").is_visible()
    pg.keyboard.press("Tab")
    assert pg.evaluate("() => document.activeElement.closest('nav.main') !== null")
    bad = axe(pg, "p7_phone_menu_open")
    assert bad == [], [(v["id"], v["impact"]) for v in bad]
    pg.keyboard.press("Escape")
    assert btn.get_attribute("aria-expanded") == "false"
    assert pg.evaluate("() => document.activeElement.classList.contains('menu-toggle')")
    bad = axe(pg, "p7_phone_menu_closed")
    assert bad == [], [(v["id"], v["impact"]) for v in bad]
    # The menu survives an htmx-boosted navigation.
    btn.click()
    pg.click("nav.main a[href='/debating']")
    pg.wait_for_selector("h1:has-text('Debating')")
    assert pg.locator("button.menu-toggle").get_attribute("aria-expanded") == "false"
    pg.click("button.menu-toggle")
    assert pg.locator("nav.main a[href='/people']").is_visible()
    # Students get the same.
    st = _student(browser, live, 390, 844, n=8)
    assert st.evaluate(HEADER_H) <= 130
    assert st.locator("button.menu-toggle").is_visible()


def test_phone_without_javascript_shows_the_list(browser, live):
    pg = _staff(browser, 390, 844, js=False)
    pg.goto(live.url + "/login")
    assert not pg.locator("button.menu-toggle").is_visible()
    assert pg.locator("a:has-text('Staff sign in')").is_visible()
