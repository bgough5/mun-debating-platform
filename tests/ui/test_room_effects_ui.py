"""D-089 in a real browser: the projector shows a title card when the stage changes, the vote reveal when a vote
closes, and breaking news; a student's raised placard fills their screen; nothing replays on a refresh."""
import os
import re
from pathlib import Path

import pytest

from app.db import SYSTEM
from app.modules.chair import service as C
from app.modules.sim import service as SIM
from tests.ui.conftest import axe, login
from tests.ui.test_phase2_ui import join, q

pytestmark = pytest.mark.ui
SHOTS = os.environ.get("FX_SHOTS")          # set to a folder to keep screenshots of each moment for design review


def shot(pg, name):
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        pg.screenshot(path=str(Path(SHOTS) / f"{name}.png"))


def test_projector_moments_and_the_students_placard(browser, live):
    chair = browser.new_context(viewport={"width": 1366, "height": 800}).new_page()
    login(chair, live)
    chair.goto(live.url + "/start")
    boxes = chair.locator(".year-block").first.locator("input[type=checkbox]")
    for i in range(min(4, boxes.count())):
        boxes.nth(i).check()
    chair.check("input[name=kind][value=mun]")          # Model UN; the Veloria scenario is chosen by default
    chair.click("button[name=op][value=start]")
    chair.wait_for_url(re.compile(r"/chair/\d+$"), wait_until="commit")
    sid = int(chair.url.rsplit("/", 1)[1])
    tok = q(live, "SELECT projector_token FROM live_session WHERE id = ?", (sid,))[0]["projector_token"]
    proj = browser.new_context(viewport={"width": 1280, "height": 720}).new_page()
    proj.goto(live.url + f"/projector/{tok}/plain")          # the plain projector keeps the D-089 effects
    proj.wait_for_selector("[data-fx]", state="attached")
    assert proj.locator(".fx-layer").count() == 0                 # opening the page plays nothing

    # A stage change: the title card drops onto the felt.
    with live.app.state.db.write(SYSTEM) as w:
        SIM.set_stage(w, sid, "opening_speeches")
    proj.wait_for_selector(".fx-layer .fx-title", timeout=10000)
    assert "Opening" in proj.inner_text(".fx-title")
    proj.wait_for_timeout(700)
    shot(proj, "1_title_card")
    assert not axe(proj, "fx_title_card")
    proj.click(".fx-skip")
    proj.wait_for_selector(".fx-layer", state="detached")

    # A vote: students vote, the chair closes it, the reveal plays.
    students = [r["student_id"] for r in q(live, "SELECT dm.student_id FROM delegation_member dm JOIN delegation d ON d.id = dm.delegation_id "
                                                  "JOIN live_session s ON s.committee_id = d.committee_id WHERE s.id = ? "
                                                  "AND dm.role = 'head' ORDER BY dm.id LIMIT 3", (sid,))]
    with live.app.state.db.write(SYSTEM) as w:
        did = C.open_division(w, sid, "Procedural vote: close debate", "custom", None, procedural=True)
    proj.wait_for_selector(".fx-layer .fx-title", timeout=10000)
    proj.click(".fx-skip")
    with live.app.state.db.write(SYSTEM) as w:
        for st in students:
            dl = q(live, "SELECT dm.delegation_id FROM delegation_member dm JOIN delegation d ON d.id = dm.delegation_id "
                         "JOIN live_session s ON s.committee_id = d.committee_id WHERE s.id = ? AND dm.student_id = ?", (sid, st))[0]
            C.cast_vote(w, did, dl["delegation_id"], "yes")
        C.close_division(w, did)
    proj.wait_for_selector(".fx-layer .fx-reveal", timeout=10000)
    proj.wait_for_selector(".fx-stamp.landed", timeout=15000)
    proj.wait_for_timeout(500)
    assert proj.locator(".fx-placard.flipped").count() >= 3
    shot(proj, "2_vote_reveal")
    proj.click(".fx-skip")

    # Breaking news on the projector and on a student's screen; a student raises their placard.
    st = browser.new_context(viewport={"width": 1280, "height": 760}).new_page()
    join(st, live, students[0])
    st.goto(live.url + f"/live/{sid}")
    st.wait_for_selector("[data-fx]", state="attached")
    chair.goto(live.url + f"/chair/{sid}")
    chair.click("button:has-text('Send it')")
    proj.wait_for_selector(".fx-layer .fx-news", timeout=10000)
    proj.wait_for_timeout(600)
    shot(proj, "3_breaking_news")
    st.wait_for_selector(".fx-layer .fx-news", timeout=10000)
    st.click(".fx-skip")
    assert st.locator(".news-banner").count() == 1
    st.click("button:has-text('Raise my placard')")
    st.wait_for_selector(".placard-up .deed")
    st.wait_for_timeout(600)
    shot(st, "4_placard")
    assert not axe(st, "fx_placard")
    proj.click(".fx-skip")
    proj.wait_for_selector(".fx-layer", state="detached")
    proj.wait_for_selector(".mini-placard", timeout=10000)
    shot(proj, "5_projector_with_placard_and_ticker")
    chair.reload()
    assert "Placards up (1)" in chair.inner_text("body")
    # "Now speaking": the next speaker's card slides up on the projector (D-091).
    with live.app.state.db.write(SYSTEM) as w:
        dl = q(live, "SELECT dm.delegation_id FROM delegation_member dm JOIN delegation d ON d.id = dm.delegation_id "
                     "JOIN live_session s ON s.committee_id = d.committee_id WHERE s.id = ? AND dm.student_id = ?", (sid, students[0]))[0]
        C.add_speaker(w, sid, dl["delegation_id"], students[0])
        C.next_speaker(w, sid)
    proj.wait_for_selector(".fx-lower", timeout=10000)
    assert "now speaking" in proj.inner_text(".fx-lower").lower() and ", " in proj.inner_text(".fx-lower-name")
    proj.wait_for_timeout(600)
    shot(proj, "8_now_speaking")
    # "Amendment adopted": old words struck, new words typed, the stamp (D-091).
    com_id = q(live, "SELECT committee_id FROM live_session WHERE id = ?", (sid,))[0]["committee_id"]
    para = q(live, "SELECT p.id FROM paragraph p JOIN resolution r ON r.id = p.resolution_id WHERE r.committee_id = ? "
                   "AND p.kind = 'operative' ORDER BY p.position LIMIT 1", (com_id,))[0]["id"]
    from app.modules.floor import service as F
    from app.modules.mun import service as M
    with live.app.state.db.write(SYSTEM) as w:
        aid = w.insert("amendment", {"paragraph_id": para, "base_version_id": q(live, "SELECT current_version_id FROM paragraph WHERE id = ?", (para,))[0]["current_version_id"],
                                     "kind": "replace", "proposed_text": "Demands an immediate ceasefire, monitored by regional observers;",
                                     "sponsor_delegation_id": dl["delegation_id"], "created_at": "2026-10-30T00:00:00+00:00",
                                     "submitted_at": "2026-10-30T00:00:00+00:00"})
    with live.app.state.db.write(SYSTEM) as w:
        F.accept_friendly(w, sid, aid)
    proj.wait_for_selector(".fx-layer .fx-adopt", timeout=10000)
    proj.wait_for_selector(".fx-adopt .fx-stamp.landed", timeout=15000)
    proj.wait_for_timeout(500)
    assert "monitored by regional observers" in proj.inner_text(".fx-adopt .fx-new")
    shot(proj, "9_amendment_adopted")
    proj.click(".fx-skip")
    # The whip-count map: predictions, the vote, then the reveal on the chair's map page.
    with live.app.state.db.write(SYSTEM) as w:
        SIM.set_stage(w, sid, "voting_procedure")
        s = C.get_session(w.conn, sid)
        res = q(live, "SELECT id FROM resolution WHERE committee_id = ? LIMIT 1", (s["committee_id"],))[0]["id"]
        rid = SIM.start_whip(w, s, "resolution", res, "Whole resolution", per_student=5)
    with live.app.state.db.write(SYSTEM) as w:                 # predictions after the round is saved
        for i, p in enumerate(q(live, "SELECT * FROM whip_prediction WHERE round_id = ?", (rid,))):
            SIM.predict(w, rid, p["student_id"], p["delegation_id"], ("yes", "no", "yes")[i % 3])
    with live.app.state.db.write(SYSTEM) as w:
        did2 = C.open_division(w, sid, "Whole resolution", "resolution", res)
        SIM.lock_round(w, rid, did2)
        C.close_division(w, did2)
    chair.goto(live.url + f"/chair/{sid}/whip-map")
    chair.wait_for_selector(".worldmap .wm-token")
    chair.wait_for_timeout(1500)
    shot(chair, "6_whip_map")
    assert chair.locator(".worldmap .wm-token").count() == 15
    assert chair.locator(".wm-token.wm-right, .wm-token.wm-wrong").count() > 0
    chair.goto(live.url + f"/mun/committees/{s['committee_id']}/map?view=NATO")
    chair.wait_for_selector(".worldmap .wm-token")
    shot(chair, "7_world_map_nato")
    assert not axe(chair, "world_map")
    assert not axe(chair, "fx_whip_map")
    # A refresh never replays a moment that has already been shown.
    proj.reload()
    proj.wait_for_selector("[data-fx]", state="attached")
    proj.wait_for_timeout(800)
    assert proj.locator(".fx-layer").count() == 0
