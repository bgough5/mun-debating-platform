"""D-101, phase 2, in a real browser: a guest goes from the title screen through the six setup steps to the table,
the session is kept in the browser and continues from the title screen, settings stick, and Escape pauses."""
import re

import pytest

from tests.ui.conftest import axe

pytestmark = pytest.mark.ui


def _close_card(page):
    """Close the stage card. In the chapters the stage's own panel then opens over the map (the Draft centre stage in
    the Working group); close it as a player would, to reach the tokens."""
    page.click("#s-chapter-card [data-close]")
    page.wait_for_timeout(450)
    _calm(page)                                                              # a stage's intro, the turn reel
    page.evaluate("document.getElementById('t-summit').hidden && window.socSessionPanel.close()")


def _calm(page):
    """Answer what comes between turns: the turn reel (skip the rest), a breakthrough (keep working) and advice."""
    page.wait_for_timeout(700)
    for _ in range(14):
        if page.is_visible("#s-walk"):
            page.click("#s-guide-skip" if page.is_visible("#s-guide-skip") else "#s-guide-next")
        elif page.is_visible("#s-proc"):                                     # the President's procedure question: answer, then thank him
            page.locator("#s-proc-opts button").first.click()
            page.wait_for_timeout(500)
            if page.is_visible("#s-proc"):
                page.locator("#s-proc-opts button").last.click()
        elif page.is_visible("#s-visit-skip"):                               # a line being spoken: skip ahead
            page.click("#s-visit-skip")
        elif page.is_visible("#s-visit"):                                    # a delegate's visit: the last (politest) answer
            page.locator("#s-visit-opts button:not([disabled])").last.click()
        elif page.is_visible("#s-reel"):
            page.click("#s-reel-skip" if page.is_visible("#s-reel-skip") else "#s-reel-next")
        elif page.is_visible("#s-breakthrough"):
            page.click("#s-bt-stay")
        elif page.is_visible("#s-advice"):
            page.click("#s-advice-ok")
        else:
            return
        page.wait_for_timeout(300)


def _through_the_summit(page, check=None):
    """The Summit as the UN runs it (D-102): statements, the draft read, a caucus, the amendments (debate, then vote),
    the final text, then the final vote. `check(name)` runs axe at each kind of step once."""
    seen = set()
    for _ in range(40):
        page.wait_for_timeout(400)
        if page.is_visible("#s-advice"):
            page.click("#s-advice-ok")
            continue
        head = page.inner_text("#c-summit h2") if page.locator("#c-summit h2").count() else ""
        line = head.splitlines()[0].strip() if head else ""
        if check and line and line not in seen:
            seen.add(line)
            check(line)
        if head.startswith("Position statements"):
            page.click(".s-stance:has-text('Open')")
        elif head.startswith("The draft, read"):
            page.click("#c-summit button:has-text('caucus')")
        elif head.startswith("Caucus"):
            page.click("#c-summit button:has-text('Move for a moderated caucus')")
        elif head.startswith("Amendment"):
            if page.locator("#c-summit .s-decide button:has-text('Stay silent')").count():
                page.click("#c-summit .s-decide button:has-text('Stay silent')")
            else:
                page.click("#c-summit .s-votes button:has-text('Abstain')")
                page.wait_for_timeout(1500)                      # the sweep
        elif head.startswith("The final text"):
            page.click("#c-summit button:has-text('final vote')")
        elif head.startswith("The final vote"):
            page.click("#c-summit .s-votes button:has-text('Yes')")
            return
    raise AssertionError("the Summit didn't reach the final vote")


def _end_turn(page, turn):
    page.click("#s-end-turn")
    page.wait_for_function(f"document.getElementById('s-where').textContent.indexOf('turn {turn}') >= 0")
    _calm(page)


def _to_the_summit(page):
    """End turns until the summit's card: four in a Quick session, or three if a crisis brought the deadline forward."""
    for _ in range(8):
        if page.is_visible("#s-chapter-card"):
            break
        _calm(page)
        if page.is_visible("#s-chapter-card"):
            break
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
    page.evaluate("localStorage.setItem('soc-session-settings', JSON.stringify({tips: false, talk: false}))")   # the walkthrough has its own test
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
    assert page.locator('[data-pick="path"]').count() == 0                 # no path to choose: graded on all four (9 Nov)
    assert page.locator('[data-pick="approach"]').count() == 4
    page.click('[data-step="5"] [data-next]')
    assert page.inner_text('[data-show="iso3"]') == "New Zealand" and page.inner_text('[data-show="approach"]') == "Career diplomat"
    page.click("#s-begin")
    page.wait_for_url(re.compile(r"/session/guest/comet_halcyon\?slot=0$"))
    page.wait_for_selector("#s-chapter-card:not([hidden])")
    assert "working session" in page.inner_text("#s-cc-eyebrow").lower()
    _close_card(page)
    assert "New Zealand" in page.inner_text("#s-you") and page.locator("#c-instr-list li").count() == 3
    assert page.locator("#b-map .b-token.you").count() == 1
    assert not axe(page, "session_game")
    page.click("#s-end-turn")
    page.wait_for_function("document.getElementById('s-where').textContent.indexOf('turn 2') >= 0")
    page.wait_for_selector("#s-reel:not([hidden])")                          # the turn reel: one card at a time (phase 12)
    assert page.inner_text("#s-reel-n").endswith(str(page.locator("#s-reel-n").inner_text().split(" of ")[-1]))
    assert not axe(page, "session_reel")
    _calm(page)
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
    page.evaluate("localStorage.setItem('soc-session-settings', JSON.stringify({tips: false, talk: false}))")   # the walkthrough has its own test
    page.click('[data-pick="pack"][data-value="comet_halcyon"]')
    page.click('[data-step="1"] [data-next]')
    page.wait_for_selector("#s-seats-box .s-seat")
    page.click('.s-seat[data-value="NZL"]')
    for n in (2, 3, 4, 5):
        page.click(f'[data-step="{n}"] [data-next]')
    page.click("#s-begin")
    page.wait_for_selector("#s-chapter-card:not([hidden])")
    _close_card(page)
    _calm(page)
    infl = int(page.inner_text("#m-influence b"))
    ap = page.locator("#s-ap i.on").count()            # 2 to 4: the opening news can change it
    ap_is = lambda k: page.wait_for_function(f"document.querySelectorAll('#s-ap i.on').length === {k}")
    # Talking from the map (6 Nov): open with an argument, they react, take it on; an action and some Influence are spent
    page.click('#b-map .b-token[data-iso="IND"]')
    assert page.get_attribute("#t-dele", "aria-selected") == "true"
    page.wait_for_selector("#c-country h3:has-text('India')")
    page.click("#c-country .s-talk-btn")
    page.locator("#s-visit .s-argcard").first.click()
    page.wait_for_function("document.getElementById('s-visit-h').textContent === 'They react'")
    ap_is(ap - 1)
    page.locator("#s-visit-opts button").nth(1).click()                      # turn to a second argument
    page.wait_for_function("document.getElementById('s-visit-h').textContent === 'Their answer'")
    page.click("#s-visit-opts button:has-text('Done')")
    page.wait_for_selector("#c-heard:not([hidden]) blockquote")
    assert "Your pitch:" in page.inner_text("#c-heard")
    assert "India" in page.inner_text("#c-heard")
    assert int(page.inner_text("#m-influence b")) < infl
    page.click("#c-country button:has-text('Read the file')")
    page.wait_for_selector("#s-file:not([hidden]) table")
    assert "India" in page.inner_text("#s-file-h") and "invented for practice" in page.inner_text("#s-file-body")   # a fictional scenario says so
    assert not axe(page, "session_file")
    page.click("#s-file [data-close]")
    ap_is(ap - 2)
    page.click("#c-country .s-predict button:has-text('yes')")              # the whip sheet is free (phase 13)
    page.wait_for_selector("#c-country .s-predict button[aria-pressed='true']")
    ap_is(ap - 2)
    assert not axe(page, "session_delegations")
    _end_turn(page, 2)
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
    page.wait_for_timeout(1300)
    if page.is_visible("#s-breakthrough"):                                   # the zero draft may already be agreed (phase 11)
        assert "Breakthrough" in page.inner_text("#s-breakthrough")
        page.click("#s-bt-stay")
    assert not axe(page, "session_draft")
    page.locator("#c-clauses > li").first.locator("button:has-text('Amend')").click()
    page.locator("#c-clauses .s-amend input:not(:checked)").first.check()
    page.click("#c-clauses .s-amend button")
    ap_is(ap - 2)
    page.click("#t-record")
    assert "You proposed a clause" in page.inner_text("#c-log")
    assert page.is_hidden("#t-staff")                                        # a quieter first stage: Staff opens in stage 2
    assert page.locator("#p-staff #s-tree .s-skill").count() == 7            # the skills live with the staff (phase 14)
    assert page.locator(".s-tabs [role=tab]:not([hidden])").count() == 5     # Brief, Draft, Delegates, Whip, Record
    assert not errors, errors
    ctx.close()


def test_a_quick_session_reaches_the_summit_and_ends_with_medals(browser, live):
    """Phase 4: the summit, clause by clause, then the whole resolution, then the results."""
    ctx = browser.new_context(viewport={"width": 1600, "height": 900})
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(live.url + "/session/new")
    page.evaluate("localStorage.setItem('soc-session-settings', JSON.stringify({tips: false, talk: false}))")   # the walkthrough has its own test
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
    _close_card(page)
    _to_the_summit(page)
    assert page.inner_text("#s-cc-h") == "The Summit"
    _close_card(page)
    assert page.get_attribute("#t-summit", "aria-selected") == "true" and page.is_hidden("#t-draft")
    steps = []
    def check(head):
        steps.append(head)
        assert not axe(page, "session_summit_" + "_".join(head.lower().replace(",", "").split()[:3])), head
    _through_the_summit(page, check)
    assert any(x.startswith("Position statements") for x in steps) and any(x.startswith("Caucus") for x in steps)
    assert any(x.startswith("The final vote") for x in steps) and page.locator("#s-verdict").count() == 1
    page.wait_for_selector("#s-result:not([hidden])", timeout=15000)
    assert page.locator("#s-result .s-medal").count() == 5                     # the four paths as medals (phase 6)
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
    page.evaluate("localStorage.setItem('soc-session-settings', JSON.stringify({timer: false, tips: true, talk: false}))")
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
    _close_card(page)
    _to_the_summit(page)
    _close_card(page)
    _through_the_summit(page)
    page.wait_for_selector("#s-result:not([hidden]) .s-plaque", timeout=15000)
    assert page.is_hidden("#s-advice") and page.locator("#s-result .s-chief-says svg").count() == 1   # the Chief's verdict, nothing over the dossier
    assert page.evaluate("document.querySelector('#s-result .s-final').scrollTop") == 0
    assert page.locator("#s-result .s-medal").count() == 5 and page.locator("#s-result .s-deed").count() >= 1
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
    assert 7 <= steps <= 12 and "Welcome" in page.inner_text("#s-guide-h")       # a short tour (phase 12)
    assert page.locator("#s-guide-face svg.g-face").count() == 1
    page.wait_for_timeout(800)
    assert not axe(page, "session_walkthrough")
    page.click("#s-guide-next")
    assert "New Zealand" in page.inner_text("#s-guide-h")
    spot = page.get_attribute("#s-spot", "style")
    for _ in range(6):                                                         # on to the instructions
        page.click("#s-guide-next")
        if "instructions" in page.inner_text("#s-guide-h").lower():
            break
    assert "instructions" in page.inner_text("#s-guide-h").lower()
    assert page.get_attribute("#s-guide-face svg", "data-expression") == "eyebrow"   # the face changes with what's said
    page.wait_for_function("s => document.getElementById('s-spot').getAttribute('style') !== s", arg=spot)   # the spotlight moved
    page.keyboard.press("ArrowLeft")
    assert "instructions" not in page.inner_text("#s-guide-h").lower()
    seen = set()
    for _ in range(steps):
        seen.add(page.inner_text("#s-guide-h").lower())
        if page.inner_text("#s-guide-next").lower() == "begin the session":
            break
        page.keyboard.press("ArrowRight")
    for title in ("the president of the committee", "your secret instructions", "talking with a delegation", "the draft"):
        assert title in seen, (title, seen)
    page.check("#s-guide-off")                                               # don't show the tutorial again
    page.click("#s-guide-next")
    page.wait_for_selector("#s-chapter-card:not([hidden])")
    assert page.is_hidden("#s-walk")
    assert page.evaluate("JSON.parse(localStorage.getItem('soc-session-settings')).tips") is False
    _close_card(page)
    page.click("button:has-text('Menu')")
    page.click("#s-replay-walk")                                             # replay from the Menu at any time
    page.wait_for_selector("#s-walk:not([hidden])")
    page.keyboard.press("Escape")
    assert page.is_hidden("#s-walk")
    page.evaluate("localStorage.setItem('soc-session-settings', JSON.stringify({tips: true, talk: false}))")
    page.click("#s-end-turn")                                                # the turn reel: the President, the Minister, advisers
    page.wait_for_selector("#s-reel:not([hidden])")
    assert page.inner_text("#s-reel-who") and page.locator("#s-reel-face svg").count() >= 1
    while page.is_visible("#s-reel"):
        page.click("#s-reel-next")
    assert page.is_hidden("#s-reel")
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
    page.evaluate("localStorage.setItem('soc-session-settings', JSON.stringify({tips: false, talk: false}))")
    page.click('[data-pick="pack"][data-value="comet_halcyon"]')
    page.click('[data-step="1"] [data-next]')
    page.wait_for_selector("#s-seats-box .s-seat")
    page.click('.s-seat[data-value="NZL"]')
    page.click('[data-step="2"] [data-next]')
    page.click('[data-pick="length"][data-value="quick"]')                   # every tool open from the start
    for n in (3, 4, 5):
        page.click(f'[data-step="{n}"] [data-next]')
    page.click("#s-begin")
    page.wait_for_selector("#s-chapter-card:not([hidden])")
    _close_card(page)
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
    _end_turn(page, 2)
    page.wait_for_function("document.querySelector('#c-staff-list .s-report .s-sure') !== null")   # the first report arrives
    assert not errors, errors
    ctx.close()



def test_the_deal_table_in_the_browser(browser, live):
    """Phases 9 and 12: a delegation's dossier; the deal table in rounds: choose what you ask for, open talks, hear
    their price and patience, hold out with a smaller offer; the table passes axe."""
    ctx = browser.new_context(viewport={"width": 1600, "height": 900})
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(live.url + "/session/new")
    page.evaluate("localStorage.setItem('soc-session-settings', JSON.stringify({tips: false, talk: false}))")
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
    _close_card(page)
    _calm(page)
    assert page.text_content("#m-respect b") == "4" and page.locator("#m-capital").count() == 0   # one Standing
    page.click("#t-staff")                                                   # staff and their skills, together
    assert page.is_visible("#s-tree .s-branch") and page.locator("#s-tree .s-skill").count() == 7
    assert not axe(page, "session_staff")
    page.evaluate("window.socSessionPanel.close()")
    page.click('#b-map .b-token[data-iso="IND"]', force=True)
    page.wait_for_selector("#c-country .s-dossier-box")
    assert "World Bank" in page.text_content("#c-country .s-dossier-box")
    page.click("#c-country .s-deal-btn")
    page.wait_for_selector("#s-deal:not([hidden]) .s-item")
    assert page.is_disabled("#s-deal-go")                                    # choose what you ask for first
    page.locator("#s-deal-get .s-item:not([disabled])").first.click()
    assert page.inner_text("#s-deal-go").startswith("OPEN TALKS") or page.text_content("#s-deal-go").startswith("Open talks")
    page.click("#s-deal-go")
    page.wait_for_selector("#s-deal-fuse i")                                   # they name their price; their patience shows
    assert page.locator("#s-deal-fuse i").count() == 5 and page.is_visible("#s-deal-accept") and page.is_visible("#s-deal-walk")
    page.wait_for_timeout(400)
    assert not axe(page, "session_deal_table")
    on = page.locator("#s-deal-give .s-item.on")
    if on.count() > 1:
        on.last.click()                                                      # hold out: offer less than they ask
    page.click("#s-deal-go")
    page.wait_for_function("document.getElementById('s-deal').hidden || /came down|insult|walked|Deal/.test(document.getElementById('s-deal-verdict').textContent + document.getElementById('p-msg').textContent)")
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
    page.evaluate("localStorage.setItem('soc-session-settings', JSON.stringify({tips: false, talk: false}))")
    assert page.is_disabled('[data-pick="pack"][data-value="ga_climate_transition"]')     # a guest's ladder starts locked
    gold = lambda pack: {"id": pack + ":1", "pack": pack, "iso3": "NZL", "path": "mandate", "difficulty": "standard",
                         "result": {"paths": {"mandate": 3}, "passed": True}}
    page.evaluate("r => localStorage.setItem('soc-session-record', JSON.stringify(r))", [gold("comet_halcyon"), gold("ga_autonomous_weapons")])
    page.reload()
    page.click('[data-pick="pack"][data-value="ga_climate_transition"]')
    page.click('[data-step="1"] [data-next]')
    page.wait_for_selector("#s-seats-box .s-seat")
    page.click('.s-seat[data-value="FJI"]')
    assert page.evaluate(inside, '[data-step="2"] [data-next]')                 # Next is in the window
    page.click('[data-step="2"] [data-next]')
    page.click('[data-pick="length"][data-value="quick"]')
    for n in (3, 4, 5):
        page.click(f'[data-step="{n}"] [data-next]')
    page.click("#s-begin")
    page.wait_for_selector("#s-chapter-card:not([hidden])")
    _close_card(page)
    assert page.evaluate("getComputedStyle(document.getElementById('b-stage')).transform") == "none"
    assert min(page.evaluate("[...document.querySelectorAll('#p-brief .b-card p')].map(e => parseFloat(getComputedStyle(e).fontSize))")) >= 16
    for sel in ("#t-brief", "#t-draft", "#t-dele", "#t-staff", "#t-record", "#s-end-turn", "#s-reserve", "#m-respect"):
        assert page.evaluate(inside, sel), sel
    page.click("#t-brief")
    assert "s-panel-open" in page.get_attribute("body", "class")
    assert page.evaluate("getComputedStyle(document.querySelector('#b-lands')).filter") != "none"   # the map dims behind the panel
    page.click("#p-brief .b-card")
    page.keyboard.press("Escape")
    assert page.is_hidden("#s-pause") and "s-panel-open" not in (page.get_attribute("body", "class") or "")
    page.click('#b-map .b-token[data-iso="NGA"]', force=True)
    page.wait_for_selector("#c-country .s-acts-grid")
    page.wait_for_timeout(400)
    assert page.evaluate(inside, "#c-country .s-acts-grid button")              # the first action is in view
    assert not axe(page, "session_real_size")
    assert not errors, errors
    ctx.close()


def test_talking_picking_and_signing(browser, live):
    """Ben's playtest, 6 Nov: talking is a conversation; picking another delegation clears the last one's words; a
    delegation signing your draft gets its own card."""
    ctx = browser.new_context(viewport={"width": 1536, "height": 753})
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(live.url + "/session/new")
    page.evaluate("localStorage.setItem('soc-session-settings', JSON.stringify({tips: false, talk: false}))")
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
    _close_card(page)
    first, second = "AUS", "JPN"
    page.click(f'#b-map .b-token[data-iso="{first}"]', force=True)
    page.wait_for_selector("#c-country .s-talk-btn")
    page.click("#c-country .s-talk-btn")
    page.wait_for_selector("#s-visit:not([hidden]) .s-argcard")
    assert not axe(page, "session_talk_open")
    page.locator("#s-visit .s-argcard").first.click()
    page.wait_for_function("document.getElementById('s-visit-h').textContent === 'They react'")
    page.locator("#s-visit-opts button").first.click()
    page.wait_for_function("document.getElementById('s-visit-h').textContent === 'Their answer'")
    assert not axe(page, "session_talk_answer")
    page.click("#s-visit-opts button:has-text('Done')")
    assert page.is_visible("#c-heard") and "Australia" in page.inner_text("#c-heard")
    page.evaluate("window.socSessionPanel.close()")
    page.click(f'#b-map .b-token[data-iso="{second}"]', force=True)
    page.wait_for_function("document.querySelector('#c-country h3') && document.querySelector('#c-country h3').textContent.startsWith('Japan')")
    assert page.is_hidden("#c-heard")                                        # the last delegation's words don't linger
    sign = page.locator("#c-country button:has-text('Ask to sign')")
    if sign.count() and sign.is_enabled():
        sign.click()
        page.wait_for_timeout(600)
        if page.is_visible("#s-signed"):
            assert "signatory" in page.inner_text("#s-signed") and not axe(page, "session_signed")
            page.click("#s-signed-row button")
    assert not errors, errors
    ctx.close()


def _fx_game(browser, live, motion):
    ctx = browser.new_context(viewport={"width": 1600, "height": 900})
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(live.url + "/session/new")
    page.evaluate("m => localStorage.setItem('soc-session-settings', JSON.stringify({tips: false, talk: false, motion: m}))", motion)
    page.reload()
    page.click('[data-pick="pack"][data-value="comet_halcyon"]')
    page.click('[data-step="1"] [data-next]')
    page.wait_for_selector("#s-seats-box .s-seat")
    page.click('.s-seat[data-value="NZL"]')
    for n in (2, 3, 4, 5):
        page.click(f'[data-step="{n}"] [data-next]')
    page.click("#s-begin")
    page.wait_for_selector("#s-chapter-card:not([hidden])")
    _close_card(page)
    page.click('#b-map .b-token[data-iso="IND"]')
    page.wait_for_selector("#c-country h3:has-text('India')")
    page.click("#c-country .s-talk-btn")
    page.locator("#s-visit .s-argcard").first.click()
    return ctx, page, errors


def test_the_room_moves_and_the_numbers_stay_true(browser, live):
    """Motion (Ben, 9 Nov): the light of the hour, a rolling counter whose real number readers always see, and a face
    that reacts to how an argument landed. With motion off, none of it plays."""
    ctx, page, errors = _fx_game(browser, live, "on")
    page.wait_for_selector("#m-influence .fx-odo", state="attached", timeout=3000)
    assert page.inner_text("#m-influence b").strip().isdigit()                       # the wheels are a copy, aria-hidden
    assert page.get_attribute("#m-influence .fx-odo", "aria-hidden") == "true"
    assert page.get_attribute("#fx-light", "data-light") == "morning"
    page.wait_for_function("document.getElementById('s-visit-h').textContent === 'They react'")
    page.wait_for_function("/fx-(nod|shake|brow|smile)/.test(document.querySelector('#s-visit-face svg.g-face').getAttribute('class'))", timeout=3000)
    assert not errors, errors
    ctx.close()
    ctx, page, errors = _fx_game(browser, live, "off")
    page.wait_for_function("document.getElementById('s-visit-h').textContent === 'They react'")
    page.wait_for_timeout(600)
    assert page.locator(".fx-odo").count() == 0 and "fx-" not in (page.get_attribute("#s-visit-face svg.g-face", "class") or "")
    assert page.evaluate("document.body.classList.contains('s-nomotion')")
    assert not errors, errors
    ctx.close()


def test_keyboard_shortcuts_and_full_screen(browser, live):
    """Ben, 10 Nov: ? lists the keys; number keys answer a conversation; the Settings have Full screen; a test
    browser is never taken full screen."""
    ctx = browser.new_context(viewport={"width": 1600, "height": 900})
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(live.url + "/session/new")
    page.evaluate("localStorage.setItem('soc-session-settings', JSON.stringify({tips: false, talk: false}))")
    page.click('[data-pick="pack"][data-value="comet_halcyon"]')
    page.click('[data-step="1"] [data-next]')
    page.wait_for_selector("#s-seats-box .s-seat")
    page.click('.s-seat[data-value="NZL"]')
    for n in (2, 3, 4, 5):
        page.click(f'[data-step="{n}"] [data-next]')
    page.click("#s-begin")
    page.wait_for_selector("#s-chapter-card:not([hidden])")
    _close_card(page)
    page.keyboard.press("?")
    page.wait_for_selector("#s-keys:not([hidden])")
    assert "Full screen" in page.inner_text("#s-keys") and "Y · A · N" in page.inner_text("#s-keys")
    page.keyboard.press("Escape")
    assert page.is_hidden("#s-keys")
    page.click('#b-map .b-token[data-iso="IND"]')
    page.wait_for_selector("#c-country h3:has-text('India')")
    page.click("#c-country .s-talk-btn")
    page.wait_for_selector("#s-visit .s-argcard")
    page.keyboard.press("1")                                                  # the first argument
    page.wait_for_function("document.getElementById('s-visit-h').textContent === 'They react'")
    assert page.evaluate("document.fullscreenElement") is None
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    _calm(page)
    for _ in range(3):                                                        # Escape closes the open panel first, then pauses
        if page.is_visible("#s-pause"):
            break
        page.keyboard.press("Escape")
        page.wait_for_timeout(250)
    page.wait_for_selector("#s-pause:not([hidden])")
    page.click("#s-pause [data-open='s-settings']")
    assert page.locator("[data-set='fullscreen']").count() == 2
    assert not errors, errors
    ctx.close()
