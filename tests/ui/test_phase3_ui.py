"""Phase 3 in a browser: axe on debating screens, ballot entry on a phone-sized screen, projector."""
import re

import pytest

from tests.ui.conftest import axe, login
from tests.ui.test_phase2_ui import join, q

pytestmark = pytest.mark.ui


def test_axe_debating_pages(page, live):
    ev = q(live, "SELECT * FROM debate_event WHERE name LIKE 'Year 8 class debates%'")[0]
    rnd = q(live, "SELECT * FROM debate_round WHERE event_id = ?", (ev["id"],))[0]
    pairing = q(live, "SELECT id FROM pairing WHERE round_id = ? AND neg_team_id IS NOT NULL LIMIT 1", (rnd["id"],))[0]["id"]
    login(page, live)
    failures = {}
    for url in ("/debating", f"/debating/events/{ev['id']}", f"/debating/events/{ev['id']}/setup", f"/debating/rounds/{rnd['id']}",
                f"/debating/pairings/{pairing}/ballot", f"/debating/events/{ev['id']}/results",
                f"/debating/events/{ev['id']}/documents/run_sheet", f"/debating/events/{ev['id']}/documents/mc_script",
                "/debating/practice?class_id=" + str(ev["class_id"]), f"/debating/practice-speeches?class_id={ev['class_id']}",
                f"/debating/projector/{ev['projector_token']}"):
        page.goto(live.url + url)
        bad = axe(page, "p3" + re.sub(r"[^a-z0-9]+", "_", url.lower())[:80])
        if bad:
            failures[url] = [(v["id"], v["impact"], v.get("targets")) for v in bad]
    assert failures == {}


def test_student_pages_axe(browser, live):
    sid = q(live, "SELECT bs.speaker_student_id AS s FROM ballot_score bs WHERE bs.speaker_student_id IS NOT NULL LIMIT 1")[0]["s"]
    pg = browser.new_context().new_page()
    join(pg, live, sid)
    failures = {}
    for url in ("/me", "/me/practice"):
        pg.goto(live.url + url)
        bad = axe(pg, "p3_student" + re.sub(r"[^a-z0-9]+", "_", url))
        if bad:
            failures[url] = [(v["id"], v["impact"], v.get("targets")) for v in bad]
    assert failures == {}
    pg.context.close()


def test_ballot_on_a_phone(browser, live):
    ev = q(live, "SELECT * FROM debate_event WHERE name LIKE 'Year 8 class debates%'")[0]
    p = q(live, "SELECT p.* FROM pairing p JOIN debate_round r ON r.id = p.round_id WHERE r.event_id = ? AND p.neg_team_id IS NOT NULL "
                "ORDER BY p.id DESC LIMIT 1", (ev["id"],))[0]
    ctx = browser.new_context(viewport={"width": 360, "height": 740}, is_mobile=True, has_touch=True)
    pg = ctx.new_page()
    login(pg, live)
    pg.goto(f"{live.url}/debating/pairings/{p['id']}/ballot")
    assert pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 1
    inputs = pg.locator("input[type=number]")
    for i in range(inputs.count()):
        name = inputs.nth(i).get_attribute("name")
        is_aff = f"s_{p['aff_team_id']}_" in name
        mx = float(inputs.nth(i).get_attribute("max"))
        inputs.nth(i).fill(str(int(mx * (0.8 if is_aff else 0.7))))
    pg.click("button:has-text('Submit ballot')")
    pg.wait_for_selector(".flash:has-text('Ballot saved')")
    ctx.close()
