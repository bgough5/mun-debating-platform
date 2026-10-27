"""Phase 9 in a real browser (D-075 to D-077): the classroom runner driven from the keyboard with the projector
following, the bell phases, the students' practice flow and prep pages, and axe on every new screen."""
import re
import time

import pytest

from tests.ui.conftest import axe, login
from tests.ui.test_phase2_ui import join, q

pytestmark = pytest.mark.ui


def _cls(live):
    cls = q(live, "SELECT id FROM class WHERE name LIKE 'Year 9%'")[0]["id"]
    return cls, q(live, "SELECT * FROM student WHERE class_id = ? ORDER BY id", (cls,))


def test_teacher_runs_a_class_debate_from_the_keyboard_and_the_projector_follows(browser, live):
    cls, _ = _cls(live)
    ctx = browser.new_context(viewport={"width": 1366, "height": 800})
    pg = ctx.new_page()
    login(pg, live)
    pg.goto(live.url + f"/debating/runs/new?kind=debate&class_id={cls}")
    pg.fill("#mo", "That zoos do more harm than good")
    pg.select_option("#speakers_per_side", "2")
    assert pg.locator("[data-slot='3']").first.is_hidden()           # only the places in use show
    pg.click("[data-fill-teams]")
    names = [pg.input_value(f"#{side}_{p}") for side in ("aff", "neg") for p in (1, 2)]
    assert all(names) and len(set(names)) == 4                         # four different students from the class list
    assert not axe(pg, "p9_run_setup")
    pg.click("button:has-text('Set it up')")
    pg.wait_for_url(re.compile(r"/debating/runs/\d+$"))
    run = q(live, "SELECT * FROM class_run ORDER BY id DESC LIMIT 1")[0]
    proj = ctx.new_page()
    proj.goto(live.url + f"/debating/present/{run['projector_token']}")
    proj.wait_for_function("document.getElementById('live-status').textContent.length > 0")
    assert proj.get_attribute(".run-stage", "data-phase") == "idle"

    pg.locator("body").click(position={"x": 5, "y": 400})
    pg.keyboard.press("Space")
    proj.wait_for_selector(".run-stage[data-phase='go']", timeout=5000)
    pg.wait_for_selector(".run-timer[data-state='running']", timeout=5000)
    assert not axe(pg, "p9_run_control")
    assert not axe(proj, "p9_run_projector")
    time.sleep(1.2)
    pg.keyboard.press("ArrowRight")
    proj.wait_for_function("document.querySelector('.run-step-label').textContent.includes('Negative')", timeout=5000)
    assert names[2] in proj.inner_text(".run-who")
    assert q(live, "SELECT step FROM class_run WHERE id = ?", (run["id"],))[0]["step"] == 1

    # The bells: the page's own clock moves the phase to the warning and then past time.
    pg.keyboard.press("Space")
    pg.wait_for_selector(".run-timer[data-state='running']", timeout=5000)
    # Wind the page's clock (the region may be re-rendered meanwhile, so set it until the phase and its words show).
    wind = """s => { const el = document.querySelector('.run-timer'); el._init = true; el._base = s; el._at = Date.now() / 1000;
                     const st = el.closest('.run-stage'); return st.dataset.phase + '|' + st.querySelector('.run-phase-text').textContent; }"""
    pg.wait_for_function(f"({wind})(30).startsWith('warn|Warning bell')", timeout=5000)      # 30 s left: past the 1-minute warning
    pg.wait_for_function(f"({wind})(-3).startsWith('over|Time')", timeout=5000)
    assert pg.inner_text(".run-timer").startswith("+0:0")
    pg.goto(live.url + f"/debating/runs/{run['id']}/results")
    assert not axe(pg, "p9_run_results")
    pg.goto(live.url + "/debating")
    assert not axe(pg, "p9_debating_home")
    ctx.close()


def test_student_practises_impromptu_from_topic_to_saved_review(browser, live):
    _, students = _cls(live)
    ctx = browser.new_context(viewport={"width": 1366, "height": 800})
    pg = ctx.new_page()
    join(pg, live, students[0]["id"])
    pg.goto(live.url + "/me/practice")
    topic = pg.input_value("[name=topic]")
    assert topic and topic == pg.inner_text("[data-practice] [data-topic-shown]")
    assert not axe(pg, "p9_practice_setup")
    pg.select_option("#th", "30")
    pg.select_option("#tg", "60")
    pg.click("[data-practice-go]")
    pg.wait_for_selector(".run-stage[data-phase='go']")
    assert "Thinking time" in pg.inner_text("[data-phase-label]") and pg.locator("[data-structure]").first.is_visible()
    pg.click("[data-practice-skip]")
    assert "Your speech" in pg.inner_text("[data-phase-label]")
    time.sleep(2.2)
    pg.click("[data-practice-stop]")
    assert pg.locator("#h-review").is_visible() and pg.inner_text("[data-spoken]") in ("0:02", "0:03")
    assert not axe(pg, "p9_practice_review")
    pg.select_option("select[name^='c_'] >> nth=0", "3")
    pg.fill("#rf", "Slow down at the start")
    pg.click("button:has-text('Save this practice')")
    pg.wait_for_url(re.compile(r"/me/practice\?mode=impromptu"))
    saved = q(live, "SELECT * FROM practice_speech WHERE student_id = ? ORDER BY id DESC LIMIT 1", (students[0]["id"],))[0]
    assert saved["topic"] == "Impromptu: " + topic and saved["target_seconds"] == 60 and saved["actual_seconds"] in (2, 3)
    pg.goto(live.url + "/me/practice?mode=rebuttal")
    assert "might argue this" in pg.inner_text("[data-topic-context]")
    assert not axe(pg, "p9_practice_rebuttal")
    ctx.close()


def test_student_prep_pages_are_accessible_and_the_word_count_is_live(browser, live):
    _, students = _cls(live)
    ctx = browser.new_context(viewport={"width": 1366, "height": 800})
    pg = ctx.new_page()
    join(pg, live, students[1]["id"])
    pg.goto(live.url + "/me/prep")
    assert not axe(pg, "p9_prep_home")
    pg.select_option("#mid", label="That zoos do more harm than good")
    pg.check("input[name=side][value=neg]")
    pg.click("button:has-text('Start the case')")
    pg.wait_for_url(re.compile(r"/me/prep/cases/\d+"))
    pg.locator("details summary:has-text('Write a rebuttal')").first.click()
    assert not axe(pg, "p9_prep_case")
    pg.goto(live.url + "/me/prep")
    pg.fill("#stt", "Why we need more trees")
    pg.click("button:has-text('Start writing')")
    pg.wait_for_url(re.compile(r"/me/prep/speeches/\d+$"))
    pg.fill("#sec-hook", " ".join(["tree"] * 65))
    assert pg.inner_text("[data-speech-total]").startswith("65 words · about 0:30")
    assert not axe(pg, "p9_prep_speech")
    pg.click("button:has-text('Save')")
    pg.click("a:has-text('Rehearse with the timer')")
    pg.wait_for_url(re.compile(r"/rehearse$"))
    pg.locator("body").click(position={"x": 5, "y": 300})
    pg.keyboard.press("ArrowRight")
    assert pg.inner_text("[data-card-pos]").startswith("Card 2 of")
    assert not axe(pg, "p9_prep_rehearse")
    ctx.close()
