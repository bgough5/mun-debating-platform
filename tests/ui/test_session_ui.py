"""D-101, phase 2, in a real browser: a guest goes from the title screen through the six setup steps to the table,
the session is kept in the browser and continues from the title screen, settings stick, and Escape pauses."""
import re

import pytest

from tests.ui.conftest import axe

pytestmark = pytest.mark.ui


def test_a_guest_sets_up_and_continues_a_session(browser, live):
    ctx = browser.new_context(viewport={"width": 1600, "height": 900})
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(live.url + "/session")
    page.wait_for_selector("h1:has-text('The Session')")
    assert not axe(page, "session_title")
    # settings: sound is off until turned on, and the choice sticks
    page.click("button:has-text('Settings')")
    assert page.get_attribute('[data-set="sound"][data-value="false"]', "aria-pressed") == "true"
    page.click('[data-set="text"][data-value="large"]')
    assert "s-large" in page.get_attribute("body", "class")
    page.click("#s-settings [data-close]")
    page.click("a:has-text('New session')")
    page.wait_for_url(re.compile(r"/session/new$"))
    assert "s-large" in page.get_attribute("body", "class")
    page.click('[data-pick="pack"][data-value="comet_halcyon"]')
    page.click('[data-step="1"] [data-next]')
    page.wait_for_selector("#s-seats-box .s-seat")
    assert page.is_disabled('[data-step="2"] [data-next]')
    page.click('#s-seats-box .b-token[data-iso="NZL"]')
    assert page.get_attribute('.s-seat[data-value="NZL"]', "aria-pressed") == "true"
    assert not axe(page, "session_setup_country")
    page.click('[data-step="2"] [data-next]')
    page.click('[data-pick="length"][data-value="quick"]')
    page.click('[data-step="3"] [data-next]')
    page.click('[data-step="4"] [data-next]')
    page.click('[data-pick="path"][data-value="consensus"]')
    page.click('[data-step="5"] [data-next]')
    assert page.inner_text('[data-show="iso3"]') == "New Zealand" and page.inner_text('[data-show="path"]') == "Consensus"
    page.click("#s-begin")
    page.wait_for_url(re.compile(r"/session/guest/comet_halcyon\?slot=0$"))
    page.wait_for_selector("#s-chapter-card:not([hidden])")
    assert "working session" in page.inner_text("#s-cc-eyebrow").lower()
    page.click("#s-chapter-card [data-close]")
    assert "New Zealand" in page.inner_text("#s-you") and page.locator("#c-instr-list li").count() == 3
    assert page.locator("#b-map .b-token.you").count() == 1
    assert not axe(page, "session_game")
    page.click("#s-end-turn")
    page.wait_for_function("document.getElementById('s-where').textContent.indexOf('turn 2') >= 0")
    page.keyboard.press("Escape")
    assert page.is_visible("#s-pause")
    page.click("#s-pause a:has-text('Save and leave')")
    page.wait_for_url(re.compile(r"/session$"))
    page.wait_for_selector("#s-guest-saves .s-save")
    assert "turn 2" in page.inner_text("#s-guest-saves")
    page.click("#s-guest-saves .s-save")
    page.wait_for_function("document.getElementById('s-where').textContent.indexOf('turn 2') >= 0")
    assert not errors, errors
    ctx.close()
