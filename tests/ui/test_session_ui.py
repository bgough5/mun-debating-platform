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


def test_a_guest_makes_moves_on_the_board(browser, live):
    """Phase 3: lobby from the map, read a file, propose a clause in your own words, amend one, predict a vote."""
    ctx = browser.new_context(viewport={"width": 1600, "height": 900})
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(live.url + "/session/new")
    page.click('[data-pick="pack"][data-value="comet_halcyon"]')
    page.click('[data-step="1"] [data-next]')
    page.wait_for_selector("#s-seats-box .s-seat")
    page.click('.s-seat[data-value="NZL"]')
    for n in (2, 3, 4, 5):
        page.click(f'[data-step="{n}"] [data-next]')
    page.click("#s-begin")
    page.wait_for_selector("#s-chapter-card:not([hidden])")
    page.click("#s-chapter-card [data-close]")
    infl = int(page.inner_text("#m-influence b"))
    ap = page.locator("#s-ap i.on").count()            # 2 to 4: the opening news can change it
    ap_is = lambda k: page.wait_for_function(f"document.querySelectorAll('#s-ap i.on').length === {k}")
    # Lobby from the map: the delegate answers, and an action point and some Influence are spent
    page.click('#b-map .b-token[data-iso="IND"]')
    assert page.get_attribute("#t-dele", "aria-selected") == "true"
    page.wait_for_selector("#c-country h3:has-text('India')")
    page.click("#c-country button:has-text('Lobby')")
    page.wait_for_selector("#c-heard:not([hidden]) blockquote")
    ap_is(ap - 1)
    assert "India" in page.inner_text("#c-heard")
    assert int(page.inner_text("#m-influence b")) < infl
    page.click("#c-country button:has-text('Read the file')")
    page.wait_for_selector("#s-file:not([hidden]) table")
    assert "India" in page.inner_text("#s-file-h") and "invented for practice" in page.inner_text("#s-file-body")   # a fictional scenario says so
    assert not axe(page, "session_file")
    page.click("#s-file [data-close]")
    ap_is(ap - 2)
    if ap > 2:
        page.click("#c-country .s-predict button:has-text('yes')")
        ap_is(ap - 3)
    assert not axe(page, "session_delegations")
    page.click("#s-end-turn")
    page.wait_for_function("document.getElementById('s-where').textContent.indexOf('turn 2') >= 0")
    # The draft: propose a clause in your own words, then amend another
    page.click("#t-draft")
    ap = page.locator("#s-ap i.on").count()
    n = page.locator("#c-clauses > li").count()
    first = page.locator("#c-cards > li").first
    first.locator("summary").click()
    first.locator("textarea").fill("Calls on every observatory to publish its comet data within a day.")
    first.locator("button:has-text('Propose')").click()
    page.wait_for_function(f"document.querySelectorAll('#c-clauses > li').length === {n + 1}")
    assert "publish its comet data within a day" in page.inner_text("#c-clauses")
    assert not axe(page, "session_draft")
    page.locator("#c-clauses > li").first.locator("button:has-text('Amend')").click()
    page.locator("#c-clauses .s-amend input:not(:checked)").first.check()
    page.click("#c-clauses .s-amend button")
    ap_is(ap - 2)
    page.click("#t-record")
    assert "You proposed a clause" in page.inner_text("#c-log")
    page.click("#s-skills-btn")
    assert page.is_visible("#s-tree .s-branch") and page.locator("#s-tree .s-skill").count() == 8
    assert not axe(page, "session_skills")
    assert not errors, errors
    ctx.close()


def test_a_quick_session_reaches_the_summit_and_ends_with_medals(browser, live):
    """Phase 4: the summit, clause by clause, then the whole resolution, then the results."""
    ctx = browser.new_context(viewport={"width": 1600, "height": 900})
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(live.url + "/session/new")
    page.click('[data-pick="pack"][data-value="comet_halcyon"]')
    page.click('[data-step="1"] [data-next]')
    page.wait_for_selector("#s-seats-box .s-seat")
    page.click('.s-seat[data-value="NZL"]')
    page.click('[data-step="2"] [data-next]')
    page.click('[data-pick="length"][data-value="quick"]')
    for n in (3, 4, 5):
        page.click(f'[data-step="{n}"] [data-next]')
    page.click("#s-begin")
    page.wait_for_selector("#s-chapter-card:not([hidden])")
    page.click("#s-chapter-card [data-close]")
    for turn in range(2, 5):
        page.click("#s-end-turn")
        page.wait_for_function(f"document.getElementById('s-where').textContent.indexOf('turn {turn}') >= 0")
    page.click("#s-end-turn")
    page.wait_for_selector("#s-chapter-card:not([hidden])")
    assert page.inner_text("#s-cc-h") == "The Summit"
    page.click("#s-chapter-card [data-close]")
    assert page.get_attribute("#t-summit", "aria-selected") == "true" and page.is_hidden("#t-draft")
    page.click(".s-stance:has-text('Open')")
    page.wait_for_selector("#c-summit .s-votes")
    assert not axe(page, "session_summit_clause")
    seen = 0
    while page.locator("#c-summit h2:has-text('Clause')").count():
        seen += 1
        page.click("#c-summit .s-votes button:has-text('Yes')")
        page.wait_for_function(f"document.querySelectorAll('#c-result-list li').length === {seen}")
    assert seen >= 1 and page.locator("#s-verdict").count() == 1
    page.wait_for_selector("#c-summit h2:has-text('The resolution as a whole')")
    page.click("#c-summit .s-votes button:has-text('Yes')")
    page.wait_for_selector("#s-result:not([hidden])", timeout=15000)
    assert page.locator("#s-result .s-medal").count() == 4                     # the four paths as medals (phase 6)
    assert any(m in page.inner_text("#s-result-h") for m in ("Gold", "Silver", "Bronze", "No medal"))
    assert not axe(page, "session_result")
    page.click("#s-result [data-close]")
    assert page.is_visible("#c-summit button:has-text('See your results')")
    assert not errors, errors
    ctx.close()


def test_the_almanac_and_the_debrief_in_the_browser(browser, live):
    """Phase 6: the Almanac reads cleanly; a finished Quick session opens its dossier at the top, with no tip over it."""
    ctx = browser.new_context(viewport={"width": 1600, "height": 900})
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(live.url + "/session/almanac/ga_migration")
    page.wait_for_selector("#a-countries details")
    assert not axe(page, "session_almanac")
    page.evaluate("localStorage.setItem('soc-session-settings', JSON.stringify({timer: false, tips: true}))")
    page.goto(live.url + "/session/new")
    page.click('[data-pick="pack"][data-value="comet_halcyon"]')
    page.click('[data-step="1"] [data-next]')
    page.wait_for_selector("#s-seats-box .s-seat")
    page.click('.s-seat[data-value="NZL"]')
    page.click('[data-step="2"] [data-next]')
    page.click('[data-pick="length"][data-value="quick"]')
    for n in (3, 4, 5):
        page.click(f'[data-step="{n}"] [data-next]')
    page.click("#s-begin")
    page.wait_for_selector("#s-chapter-card:not([hidden])")
    page.click("#s-chapter-card [data-close]")
    page.wait_for_selector(".s-tip")                                          # tips on: the first one appears
    assert "Your instructions" in page.inner_text(".s-tip")
    page.click(".s-tip button:has-text('No more tips')")
    for _ in range(4):
        page.click("#s-end-turn")
        page.wait_for_timeout(600)
    page.wait_for_selector("#s-chapter-card:not([hidden])")
    page.click("#s-chapter-card [data-close]")
    page.click(".s-stance:has-text('Open')")
    page.wait_for_selector("#c-summit .s-votes")
    while page.locator("#c-summit h2:has-text('Clause')").count():
        n = page.locator("#c-result-list li").count()
        page.click("#c-summit .s-votes button:has-text('Yes')")
        page.wait_for_function(f"document.querySelectorAll('#c-result-list li').length === {n + 1}")
    page.click("#c-summit .s-votes button:has-text('Yes')")
    page.wait_for_selector("#s-result:not([hidden]) .s-plaque", timeout=15000)
    assert page.locator(".s-tip").count() == 0
    assert page.evaluate("document.querySelector('#s-result .s-final').scrollTop") == 0
    assert page.locator("#s-result .s-medal").count() == 4 and page.locator("#s-result .s-deed").count() >= 1
    assert "What to try next time" in page.inner_text("#s-result")
    page.wait_for_timeout(2500)                                               # let the deeds and medals land
    assert not axe(page, "session_debrief")
    assert not errors, errors
    ctx.close()
