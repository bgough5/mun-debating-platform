"""Phase 2 in a real browser: live updates, paragraph lock seen by others, chair crash recovery, axe on new screens."""
import re
import time

import pytest

from tests.conftest import COORD_PASS
from tests.ui.conftest import axe, login

pytestmark = pytest.mark.ui


def q(live, sql, params=()):
    with live.app.state.db.read() as conn:
        return [dict(r) for r in conn.execute(sql, params)]


def join(page, live, student_id):
    """Sign in as the student with their own link, as on their sign-in card (D-079)."""
    code = q(live, "SELECT login_code FROM student WHERE id = ?", (student_id,))[0]["login_code"]
    page.goto(live.url + f"/s/{code}")
    page.wait_for_url(re.compile(r"/me$"))


def ga_member(live, n=0):
    return q(live, "SELECT dm.student_id, d.id AS delegation_id, d.iso3, d.committee_id FROM delegation_member dm "
                   "JOIN delegation d ON d.id = dm.delegation_id JOIN committee cm ON cm.id = d.committee_id "
                   "WHERE cm.name LIKE 'United Nations General Assembly%' AND dm.deleted_at IS NULL ORDER BY d.iso3, dm.id")[n]


def open_session(page, live, committee_id):
    login(page, live)
    page.goto(f"{live.url}/chair")
    btn = page.locator(f"form[action='/chair/committee/{committee_id}/open'] button")
    if btn.count():
        btn.click()
    else:
        page.goto(f"{live.url}/chair/committee/{committee_id}")
    page.wait_for_url(re.compile(r"/chair/\d+$"))
    return int(page.url.rsplit("/", 1)[1])


def test_live_update_reaches_student_without_reload(browser, live):
    chair = browser.new_context().new_page()
    student = browser.new_context().new_page()
    m = ga_member(live)
    sid = open_session(chair, live, m["committee_id"])
    join(student, live, m["student_id"])
    student.goto(f"{live.url}/live/{sid}")
    student.wait_for_selector("#live-status:has-text('Live')")
    chair.select_option("#sd", label=q(live, "SELECT name FROM country WHERE iso3 = ?", (m["iso3"],))[0]["name"])
    t0 = time.time()
    chair.click("#floor button:has-text('Add')")
    student.wait_for_selector("text=You are number 1", timeout=5000)
    latency = time.time() - t0
    assert latency < 2.0, latency
    # the chair calls them; the student's page shows them speaking and a timer
    chair.click("button:has-text('Next speaker')")
    student.wait_for_selector("#live-main .timer", timeout=5000)
    chair.context.close()
    student.context.close()


def test_chair_browser_killed_recovers_same_state(browser, live):
    from playwright.sync_api import sync_playwright  # noqa: F401
    m = ga_member(live, 2)
    ctx = browser.new_context()
    chair = ctx.new_page()
    sid = open_session(chair, live, m["committee_id"])
    dels = q(live, "SELECT d.id, c.name FROM delegation d JOIN country c ON c.iso3 = d.iso3 WHERE d.committee_id = ? ORDER BY c.name LIMIT 3",
             (m["committee_id"],))
    for i, d in enumerate(dels, 1):
        chair.select_option("#sd", value=str(d["id"]))
        chair.click("#floor button:has-text('Add')")
        chair.wait_for_selector(f"#floor h3:has-text('Speakers list ({i})')")
    chair.click("button:has-text('Next speaker')")
    # Wait until Next speaker has landed (three added, one called: two waiting). Waiting only for "a timer"
    # passed at once when an earlier test in this module had left a timer for the same country (Australia),
    # so Start went to that old, finished timer and the test timed out in full runs (it passed alone).
    chair.wait_for_selector("#floor h3:has-text('Speakers list (2)')")
    chair.wait_for_selector("#floor .timer")
    chair.locator("#floor form:has(input[value='start']) button").first.click()
    chair.wait_for_selector("#floor .timer[data-state='running']")
    before = chair.inner_text("#floor")
    ctx.close()                         # the chair's browser is gone mid-session
    time.sleep(1.5)
    ctx2 = browser.new_context()        # a fresh browser: no cookies, no local state
    chair2 = ctx2.new_page()
    login(chair2, live)
    chair2.goto(f"{live.url}/chair")
    chair2.click("a:has-text('Resume session')")
    chair2.wait_for_url(re.compile(rf"/chair/{sid}$"))
    after = chair2.inner_text("#floor")
    # same speaker, same queue, timer still running and about 1.5 s further on
    assert dels[0]["name"] in after.split("Speakers list")[0]
    assert [l for l in before.split("Speakers list")[1].splitlines() if l.strip()][:3] == \
           [l for l in after.split("Speakers list")[1].splitlines() if l.strip()][:3]
    assert "running" in after
    ctx2.close()


def test_paragraph_lock_visible_to_others(browser, live):
    m = ga_member(live, 4)
    with live.app.state.db.read() as conn:
        res = conn.execute("SELECT id FROM resolution WHERE committee_id = ?", (m["committee_id"],)).fetchone()[0]
        pid = conn.execute("SELECT id FROM paragraph WHERE resolution_id = ? AND kind='operative' AND position = 9", (res,)).fetchone()[0]
        conn.execute("UPDATE paragraph SET owner_delegation_id = ? WHERE id = ?", (m["delegation_id"], pid))
        conn.commit()
    a = browser.new_context().new_page()
    b = browser.new_context().new_page()
    join(a, live, m["student_id"])
    login(b, live)
    b.goto(f"{live.url}/mun/resolutions/{res}")
    b.wait_for_selector("#live-status:has-text('Live')") if b.locator("#live-status").count() else None
    a.goto(f"{live.url}/mun/resolutions/{res}")
    a.locator(f"#p{pid} summary:has-text('Edit')").click()
    a.wait_for_selector(f"#p{pid} .lock-msg:has-text('You are editing')")
    b.wait_for_selector(f"#p{pid} .lockline:has-text('Being edited by')", timeout=5000)
    a.locator(f"#p{pid} summary:has-text('Edit')").click()     # close the editor: lock released
    b.wait_for_function(f"!document.querySelector('#p{pid} .lockline')", timeout=5000)
    a.context.close()
    b.context.close()


def test_axe_phase2_pages(browser, live):
    m = ga_member(live, 6)
    chair = browser.new_context().new_page()
    sid = open_session(chair, live, m["committee_id"])
    token = q(live, "SELECT projector_token FROM live_session WHERE id = ?", (sid,))[0]["projector_token"]
    failures = {}
    for url in (f"/chair/{sid}", "/chair", f"/chair/{sid}/minutes", f"/projector/{token}"):
        chair.goto(live.url + url)
        bad = axe(chair, "p2" + re.sub(r"[^a-z0-9]+", "_", url.lower()))
        if bad:
            failures[url] = [(v["id"], v["impact"], v["nodes"]) for v in bad]
    student = browser.new_context().new_page()
    student.goto(live.url + "/join")
    if axe(student, "p2_join"):
        failures["/join"] = axe(student, "p2_join")
    join(student, live, m["student_id"])
    for url in ("/me", f"/live/{sid}"):
        student.goto(live.url + url)
        bad = axe(student, "p2_student" + re.sub(r"[^a-z0-9]+", "_", url.lower()))
        if bad:
            failures[url] = [(v["id"], v["impact"], v["nodes"]) for v in bad]
    assert failures == {}
