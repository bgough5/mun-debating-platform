"""D-087 in a real browser: a free-form speech saves itself while the student types, and becomes cue cards to print."""
import re

import pytest

from tests.ui.conftest import axe
from tests.ui.test_phase2_ui import join, q

pytestmark = pytest.mark.ui


def test_speech_autosaves_and_becomes_cue_cards(page, live):
    sid = q(live, "SELECT id FROM student WHERE active = 1 ORDER BY id DESC LIMIT 1")[0]["id"]
    join(page, live, sid)
    page.goto(live.url + "/me/prep")
    page.check("input[name=template_code][value=free]")
    page.fill("#stt", "Lunchtime speech")
    page.click("button:has-text('Start writing')")
    page.wait_for_url(re.compile(r"/me/prep/speeches/\d+$"), wait_until="commit")
    box = page.locator("textarea[name=sec_speech]")
    box.wait_for()
    box.fill("Firstly, I believe that homework should be optional. Students learn best when they choose.\n\n"
             "Finally, rest matters as much as study.")
    page.evaluate("window.socAutosaveNow()")
    page.wait_for_selector("[data-autosave-status]:has-text('Saved automatically')")
    page.reload()
    assert "Students learn best when they choose." in page.locator("textarea[name=sec_speech]").input_value()
    page.click("a:has-text('Cue cards: dot points')")
    page.wait_for_url(re.compile(r"/me/cards/speech/\d+\?mode=dots"), wait_until="commit")
    page.wait_for_selector("h1:has-text('Cue cards: Lunchtime speech')")
    assert "Homework should be optional" in page.locator("textarea[name=b_0]").input_value()
    assert not axe(page, "cue_cards_edit")
    page.click("a.button:has-text('Print')")
    page.wait_for_selector(".pc")
    assert page.locator(".pc").count() >= 1 and "1 /" in page.inner_text(".pc-top")
    assert not axe(page, "cue_cards_print")
    # Rehearse from the cards: the arrow keys (or a clicker) move card to card.
    page.goto(page.url.split("/print")[0].replace("/print", "") + "/rehearse?mode=dots")
    page.wait_for_selector("[data-card-pos]")
    assert page.inner_text("[data-card-pos]").startswith("Card 1 of")
    if page.locator("[data-card]").count() > 1:
        page.locator("body").click(position={"x": 5, "y": 300})
        page.keyboard.press("ArrowRight")
        assert page.inner_text("[data-card-pos]").startswith("Card 2 of")
    assert not axe(page, "cue_cards_rehearse")
