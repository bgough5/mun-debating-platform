"""D-101, phase 2, in a real browser: a guest goes from the title screen through the six setup steps to the table,
the session is kept in the browser and continues from the title screen, settings stick, and Escape pauses."""
import re

import pytest

from tests.ui.conftest import axe

pytestmark = pytest.mark.ui


def _to_the_summit(page):
    """End turns until the summit's card: four in a Quick session, or three if a crisis brought the deadline forward."""
    for _ in range(6):
        if page.is_visible("#s-chapter-card"):
            break
        while page.is_visible("#s-advice"):
            page.click("#s-advice-ok")
        page.click("#s-end-turn")
        page.wait_for_timeout(700)
    page.wait_for_selector("#s-chapter-card:not([hidden])")
    assert page.inner_text("#s-cc-h") == "The Summit"


def test_a_guest_sets_up_and_continues_a_session(browser, live):
    ctx = browser.new_context(viewport={"width": 1600, "height": 900})
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(live.url + "/session")
    page.evaluate("localStorage.setItem('soc-session-settings', JSON.stringify({tips: false}))")   # the walkthrough has its own test
    page.reload()
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
    page.click("#t-brief")                                                   # a panel is open: Escape closes it first
    page.keyboard.press("Escape")
    assert page.is_hidden("#s-pause")
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
    page.evaluate("localStorage.setItem('soc-session-settings', JSON.stringify({tips: false}))")   # the walkthrough has its own test
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
    page.evaluate("localStorage.setItem('soc-session-settings', JSON.stringify({tips: false}))")   # the walkthrough has its own test
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
    _to_the_summit(page)
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
    page.goto(live.url + "/session/new")
    page.evaluate("localStorage.setItem('soc-session-settings', JSON.stringify({timer: false, tips: true}))")
    page.click('[data-pick="pack"][data-value="comet_halcyon"]')
    page.click('[data-step="1"] [data-next]')
    page.wait_for_selector("#s-seats-box .s-seat")
    page.click('.s-seat[data-value="NZL"]')
    page.click('[data-step="2"] [data-next]')
    page.click('[data-pick="length"][data-value="quick"]')
    for n in (3, 4, 5):
        page.click(f'[data-step="{n}"] [data-next]')
    page.click("#s-begin")
    page.wait_for_selector("#s-walk:not([hidden])")                          # the guide on: the walkthrough comes first
    page.click("#s-guide-skip")
    page.wait_for_selector("#s-chapter-card:not([hidden])")
    page.click("#s-chapter-card [data-close]")
    _to_the_summit(page)
    page.click("#s-chapter-card [data-close]")
    page.click(".s-stance:has-text('Open')")
    page.wait_for_selector("#c-summit .s-votes")
    while page.locator("#c-summit h2:has-text('Clause')").count():
        n = page.locator("#c-result-list li").count()
        page.click("#c-summit .s-votes button:has-text('Yes')")
        page.wait_for_function(f"document.querySelectorAll('#c-result-list li').length === {n + 1}")
    page.click("#c-summit .s-votes button:has-text('Yes')")
    page.wait_for_selector("#s-result:not([hidden]) .s-plaque", timeout=15000)
    assert page.is_hidden("#s-advice") and page.locator("#s-result .s-chief-says svg").count() == 1   # the Chief's verdict, nothing over the dossier
    assert page.evaluate("document.querySelector('#s-result .s-final').scrollTop") == 0
    assert page.locator("#s-result .s-medal").count() == 4 and page.locator("#s-result .s-deed").count() >= 1
    assert "What to try next time" in page.inner_text("#s-result")
    page.wait_for_timeout(2500)                                               # let the deeds and medals land
    assert not axe(page, "session_debrief")
    assert not errors, errors
    ctx.close()


def test_the_chief_of_protocol_walks_a_new_player_through_the_session(browser, live):
    """Phase 7: a new session opens with the Chief of Protocol's walkthrough of the whole session, before the first
    chapter card. Next, Back and the arrow keys move between steps; the spotlight moves with them; the checkbox turns
    the guide off; the Menu replays the walkthrough; advice appears at key moments once the session is under way."""
    ctx = browser.new_context(viewport={"width": 1600, "height": 900})
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(live.url + "/session/new")
    page.evaluate("localStorage.removeItem('soc-session-settings')")
    page.click('[data-pick="pack"][data-value="comet_halcyon"]')
    page.click('[data-step="1"] [data-next]')
    page.wait_for_selector("#s-seats-box .s-seat")
    page.click('.s-seat[data-value="NZL"]')
    for n in (2, 3, 4, 5):
        page.click(f'[data-step="{n}"] [data-next]')
    assert page.is_checked("#s-tips-on")                                     # on unless the player turns it off
    page.click("#s-begin")
    page.wait_for_selector("#s-walk:not([hidden])")
    assert page.is_hidden("#s-chapter-card")                                 # the walkthrough comes before the session
    steps = page.locator("#s-guide-dots li").count()
    assert steps >= 15 and "Welcome" in page.inner_text("#s-guide-h")
    assert page.locator("#s-guide-face svg.g-face").count() == 1
    page.wait_for_timeout(800)
    assert not axe(page, "session_walkthrough")
    page.click("#s-guide-next")
    assert "New Zealand" in page.inner_text("#s-guide-h")
    spot = page.get_attribute("#s-spot", "style")
    page.click("#s-guide-next")
    page.click("#s-guide-next")
    assert "instructions" in page.inner_text("#s-guide-h").lower()
    assert page.get_attribute("#s-guide-face svg", "data-expression") == "eyebrow"   # the face changes with what's said
    page.wait_for_function("s => document.getElementById('s-spot').getAttribute('style') !== s", arg=spot)   # the spotlight moved
    page.keyboard.press("ArrowLeft")
    assert "hour" in page.inner_text("#s-guide-h").lower()
    seen = set()
    for _ in range(steps):
        seen.add(page.inner_text("#s-guide-h").lower())
        if page.inner_text("#s-guide-next").lower() == "begin the session":
            break
        page.keyboard.press("ArrowRight")
    for title in ("your rivals", "crises, news and offers", "then, the summit", "and the debrief", "the gavel is yours"):
        assert title in seen, (title, seen)
    page.check("#s-guide-off")                                               # don't show the tutorial again
    page.click("#s-guide-next")
    page.wait_for_selector("#s-chapter-card:not([hidden])")
    assert page.is_hidden("#s-walk")
    assert page.evaluate("JSON.parse(localStorage.getItem('soc-session-settings')).tips") is False
    page.click("#s-chapter-card [data-close]")
    page.click("button:has-text('Menu')")
    page.click("#s-replay-walk")                                             # replay from the Menu at any time
    page.wait_for_selector("#s-walk:not([hidden])")
    page.keyboard.press("Escape")
    assert page.is_hidden("#s-walk")
    page.evaluate("localStorage.setItem('soc-session-settings', JSON.stringify({tips: true}))")
    for _ in range(4):                                                       # the Chief speaks up at key moments
        page.click("#s-end-turn")
        try:
            page.wait_for_selector("#s-advice:not([hidden])", timeout=3000)
            break
        except Exception:
            if page.is_visible("#s-chapter-card"):
                page.click("#s-chapter-card [data-close]")
    assert page.is_visible("#s-advice") and page.inner_text("#s-advice-text")
    assert not axe(page, "session_advice")
    page.click("#s-advice-ok")
    assert page.is_hidden("#s-advice")
    assert not errors, errors
    ctx.close()



def test_staff_the_vote_bar_and_the_reserve_in_the_browser(browser, live):
    """Phase 8: the vote bar shows the projection; advisers are posted from the Staff tab and their pins appear on the
    map; holding an action in reserve; the Staff tab passes axe."""
    ctx = browser.new_context(viewport={"width": 1600, "height": 900})
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(live.url + "/session/new")
    page.evaluate("localStorage.setItem('soc-session-settings', JSON.stringify({tips: false}))")
    page.click('[data-pick="pack"][data-value="comet_halcyon"]')
    page.click('[data-step="1"] [data-next]')
    page.wait_for_selector("#s-seats-box .s-seat")
    page.click('.s-seat[data-value="NZL"]')
    for n in (2, 3, 4, 5):
        page.click(f'[data-step="{n}"] [data-next]')
    page.click("#s-begin")
    page.wait_for_selector("#s-chapter-card:not([hidden])")
    page.click("#s-chapter-card [data-close]")
    assert re.search(r"\d+ yes · \d+ abstain · \d+ no", page.inner_text("#s-tug-n"))
    assert page.text_content("#s-tug-stamp") in ("Would pass", "Would fail")
    page.click("#t-staff")
    page.wait_for_selector("#c-staff-list .s-adviser")
    first = page.locator("#c-staff-list select").first
    target = first.locator("option").nth(1).get_attribute("value")
    first.select_option(target)
    page.wait_for_selector("#b-tokens .s-pin")
    assert page.locator("#b-tokens .s-pin").count() == 1
    page.wait_for_timeout(400)
    assert not axe(page, "session_staff")
    ap = page.locator("#s-ap i.on").count()
    page.click("#s-reserve")
    page.wait_for_function("document.getElementById('s-reserve').textContent === 'Reserve ready'")
    assert page.locator("#s-ap i.on").count() == ap - 1 and page.is_disabled("#s-reserve")
    page.click("#s-end-turn")
    page.wait_for_function("document.getElementById('s-where').textContent.indexOf('turn 2') >= 0")
    page.wait_for_function("document.querySelector('#c-staff-list .s-report .s-sure') !== null")   # the first report arrives
    assert not errors, errors
    ctx.close()



def test_the_deal_table_in_the_browser(browser, live):
    """Phase 9: a delegation's dossier, the deal table's trays and meter, your capital's reaction, a proposal; the deal
    table passes axe."""
    ctx = browser.new_context(viewport={"width": 1600, "height": 900})
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(live.url + "/session/new")
    page.evaluate("localStorage.setItem('soc-session-settings', JSON.stringify({tips: false}))")
    page.click('[data-pick="pack"][data-value="comet_halcyon"]')
    page.click('[data-step="1"] [data-next]')
    page.wait_for_selector("#s-seats-box .s-seat")
    page.click('.s-seat[data-value="NZL"]')
    for n in (2, 3, 4, 5):
        page.click(f'[data-step="{n}"] [data-next]')
    page.click("#s-begin")
    page.wait_for_selector("#s-chapter-card:not([hidden])")
    page.click("#s-chapter-card [data-close]")
    assert page.text_content("#m-capital b") == "6/10"
    page.click('#b-map .b-token[data-iso="IND"]', force=True)
    page.wait_for_selector("#c-country .s-dossier-box")
    assert "World Bank" in page.text_content("#c-country .s-dossier-box")
    page.click("#c-country .s-deal-btn")
    page.wait_for_selector("#s-deal:not([hidden]) .s-item")
    assert page.is_disabled("#s-deal-go")                                    # nothing on the table yet
    page.locator("#s-deal-give .s-item:not([disabled])").first.click()
    page.locator("#s-deal-get .s-item:not([disabled])").first.click()
    assert page.inner_text("#s-deal-verdict").startswith("They")
    assert page.locator("#s-deal-capital p").count() == 1
    page.wait_for_timeout(400)
    assert not axe(page, "session_deal_table")
    page.click("#s-deal-go")
    page.wait_for_function("document.getElementById('s-deal').hidden || document.getElementById('s-deal-verdict').textContent.indexOf('turned it down') >= 0")
    assert not errors, errors
    ctx.close()


def test_the_session_is_drawn_at_real_size_on_a_small_laptop(browser, live):
    """Phase 10: on a 1366x768 laptop (a 1366x657 browser window) The Session is not a shrunk picture: panel text is
    at least 16 px, every command and the setup's Next button sit inside the window, the map dims behind an open
    panel, and Escape closes the panel and returns focus to its icon."""
    ctx = browser.new_context(viewport={"width": 1366, "height": 657})
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    inside = "s => { const r = document.querySelector(s).getBoundingClientRect(); return r.width > 0 && r.top >= 0 && r.left >= 0 && r.bottom <= innerHeight + 1 && r.right <= innerWidth + 1; }"
    page.goto(live.url + "/session/new")
    page.evaluate("localStorage.setItem('soc-session-settings', JSON.stringify({tips: false}))")
    page.click('[data-pick="pack"][data-value="ga_climate_transition"]')
    page.click('[data-step="1"] [data-next]')
    page.wait_for_selector("#s-seats-box .s-seat")
    page.click('.s-seat[data-value="FJI"]')
    assert page.evaluate(inside, '[data-step="2"] [data-next]')                 # Next is in the window
    for n in (2, 3, 4, 5):
        page.click(f'[data-step="{n}"] [data-next]')
    page.click("#s-begin")
    page.wait_for_selector("#s-chapter-card:not([hidden])")
    page.click("#s-chapter-card [data-close]")
    assert page.evaluate("getComputedStyle(document.getElementById('b-stage')).transform") == "none"
    assert min(page.evaluate("[...document.querySelectorAll('#p-brief .b-card p')].map(e => parseFloat(getComputedStyle(e).fontSize))")) >= 16
    for sel in ("#t-brief", "#t-draft", "#t-dele", "#t-staff", "#t-record", "#s-end-turn", "#s-reserve", "#m-capital"):
        assert page.evaluate(inside, sel), sel
    page.click("#t-brief")
    assert "s-panel-open" in page.get_attribute("body", "class")
    assert page.evaluate("getComputedStyle(document.querySelector('#b-lands')).filter") != "none"   # the map dims behind the panel
    page.click("#p-brief .b-card")
    page.keyboard.press("Escape")
    assert page.is_hidden("#s-pause") and "s-panel-open" not in (page.get_attribute("body", "class") or "")
    page.click('#b-map .b-token[data-iso="NGA"]', force=True)
    page.wait_for_selector("#c-country .s-acts-grid")
    assert page.evaluate(inside, "#c-country .s-acts-grid button")              # the first action is in view
    assert not axe(page, "session_real_size")
    assert not errors, errors
    ctx.close()
