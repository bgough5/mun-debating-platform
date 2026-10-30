"""D-092 in a real browser: the board opens from the console in its own window and plays the session: the stage
scroll, countries lighting at roll call, the camera gliding to the speaker with the dial running, the vote sweep and
the seal, and the debrief map. FX_SHOTS=<folder> keeps screenshots for design review."""
import os
import re
from pathlib import Path

import pytest

from app.db import SYSTEM
from app.modules.chair import service as C
from app.modules.sim import service as SIM
from tests.ui.conftest import axe, login
from tests.ui.test_phase2_ui import q

pytestmark = pytest.mark.ui
SHOTS = os.environ.get("FX_SHOTS")


def shot(pg, name):
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        pg.screenshot(path=str(Path(SHOTS) / f"board_{name}.png"))


def test_the_board_plays_the_session(browser, live):
    ctx = browser.new_context(viewport={"width": 1366, "height": 800})
    chair = ctx.new_page()
    login(chair, live)
    chair.goto(live.url + "/start")
    boxes = chair.locator(".year-block").first.locator("input[type=checkbox]")
    for i in range(min(5, boxes.count())):
        boxes.nth(i).check()
    chair.check("input[name=kind][value=evatt]")
    chair.click("button[name=op][value=start]")
    chair.wait_for_url(re.compile(r"/chair/\d+$"), wait_until="commit")
    sid = int(chair.url.rsplit("/", 1)[1])
    with ctx.expect_page() as popup:
        chair.click("[data-board-open]")
    board = popup.value
    board.set_viewport_size({"width": 1600, "height": 900})
    board.wait_for_selector("#b-map .b-token", state="attached")
    assert board.locator(".b-moment").count() == 0                     # opening the board plays nothing
    assert not axe(board, "board_roll_call")
    shot(board, "1_roll_call_empty")

    heads = q(live, "SELECT dm.student_id, dm.delegation_id FROM delegation_member dm JOIN delegation d ON d.id = dm.delegation_id "
                    "JOIN live_session s ON s.committee_id = d.committee_id WHERE s.id = ? AND dm.role = 'head' ORDER BY dm.id", (sid,))
    s = q(live, "SELECT * FROM live_session WHERE id = ?", (sid,))[0]
    from app.modules.sim.service import answer_roll
    with live.app.state.db.write(SYSTEM) as w:
        for i, hd in enumerate(heads):
            answer_roll(w, s, hd["delegation_id"], "present_and_voting" if i % 2 else "present")
    board.wait_for_selector(".b-token.lit", timeout=10000)
    board.wait_for_timeout(900)
    shot(board, "2_roll_call_lit")

    with live.app.state.db.write(SYSTEM) as w:
        SIM.set_stage(w, sid, "opening_speeches")
    board.wait_for_selector(".b-moment .b-scroll", timeout=10000)
    board.wait_for_timeout(900)
    shot(board, "3_stage_scroll")
    board.wait_for_selector(".b-moment", state="detached", timeout=15000)

    with live.app.state.db.write(SYSTEM) as w:
        C.add_speaker(w, sid, heads[0]["delegation_id"], heads[0]["student_id"])
        C.next_speaker(w, sid)
    t = q(live, "SELECT id FROM timer WHERE session_id = ? AND kind = 'speaker' ORDER BY id DESC LIMIT 1", (sid,))[0]["id"]
    with live.app.state.db.write(SYSTEM) as w:
        C.timer_action(w, t, "start")
    board.wait_for_selector(".b-token.speaking", timeout=10000)
    board.wait_for_selector("#b-speaker:not([hidden])")
    board.wait_for_timeout(2200)
    vb = board.get_attribute("#b-map", "viewBox").split()
    assert float(vb[2]) < 900                                           # the camera has zoomed in on the speaker
    assert re.match(r"\d+:\d\d", board.inner_text("#b-time"))
    shot(board, "4_speaker_zoom")

    with live.app.state.db.write(SYSTEM) as w:
        SIM.set_stage(w, sid, "voting_procedure")
    board.wait_for_selector(".b-moment", state="detached", timeout=15000)
    com = q(live, "SELECT committee_id FROM live_session WHERE id = ?", (sid,))[0]["committee_id"]
    res = q(live, "SELECT id FROM resolution WHERE committee_id = ? LIMIT 1", (com,))[0]["id"]
    with live.app.state.db.write(SYSTEM) as w:
        did = C.open_division(w, sid, "The whole resolution", "resolution", res)
    board.wait_for_selector(".b-moment", state="detached", timeout=15000)
    with live.app.state.db.write(SYSTEM) as w:
        for i, hd in enumerate(heads):
            C.cast_vote(w, did, hd["delegation_id"], ("yes", "no", "yes")[i % 3])
    board.wait_for_selector(".b-token.cast", timeout=10000)
    shot(board, "5_votes_coming_in")
    with live.app.state.db.write(SYSTEM) as w:
        C.close_division(w, did)
    board.wait_for_selector(".b-sealbox", timeout=15000)
    board.wait_for_timeout(900)
    shot(board, "6_vote_sealed")
    assert board.locator(".b-land.v-yes, .b-land.v-no").count() > 0

    with live.app.state.db.write(SYSTEM) as w:
        SIM.set_stage(w, sid, "debrief")
    board.wait_for_selector(".b-moment", state="detached", timeout=15000)
    board.wait_for_timeout(600)
    shot(board, "7_debrief")
    assert "How the room voted" in board.inner_text("#b-rail")
    assert not axe(board, "board_debrief")
    # A reload shows the room as it is and plays nothing.
    board.reload()
    board.wait_for_selector("#b-map .b-token", state="attached")
    board.wait_for_timeout(800)
    assert board.locator(".b-moment").count() == 0
    ctx.close()
