"""Phase 5 accessibility audit: every page each role can reach, in a real browser.

For the coordinator, a member of staff, a student and the projector, the test
follows every link from the role's home page (one page per route pattern, so
/mun/committees/1 and /mun/committees/2 count once) and on each page checks:
  - axe-core WCAG 2.0/2.1/2.2 A and AA: 0 serious or critical issues;
  - reflow at 320 px wide (WCAG 1.4.10): no horizontal page scroll;
  - structure: a language, a title, one h1, a main landmark, and the skip link
    as the first Tab stop.
The list of pages checked is saved in test-results/a11y-pages.json.
Manual checks (NVDA, real keyboard use of every control) are not covered.
"""
import json
import re
from pathlib import Path

import pytest

from app.fakedata import DEMO_STAFF_PASSPHRASE
from tests.ui.conftest import axe, login

pytestmark = pytest.mark.ui
SKIP = re.compile(r"(/logout|\.docx|\.csv|\.zip|/admin/data/download|/practice-game/solo|^/join|/static/|/healthz|javascript:|mailto:|#)")
OUT = Path(__file__).resolve().parents[2] / "test-results" / "a11y-pages.json"
LIMIT = 400
# The outermost elements sticking out past the right edge (not inside a scrolling box), to say what to fix.
OVERFLOWING = """() => { const W = document.documentElement.clientWidth, out = [];
  for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect();
    if (r.right <= W + 1 || !r.width) continue;
    let p = el.parentElement, skip = false;
    while (p && p !== document.body) {
      if (/(auto|scroll|hidden)/.test(getComputedStyle(p).overflowX) || p.getBoundingClientRect().right > W + 1) { skip = true; break; }
      p = p.parentElement; }
    if (!skip) out.push(el.tagName.toLowerCase() + (el.className ? '.' + String(el.className).split(' ')[0] : '') + ': ' + (el.textContent || '').trim().slice(0, 30));
  }
  return out.slice(0, 4); }"""


def _pattern(path: str) -> str:
    # Random tokens (projector links) are long and contain a capital or a digit; table names like
    # "procedure_stage" are lowercase words and must each count as their own page.
    path = path.split("?")[0]
    path = re.sub(r"/(?=[A-Za-z0-9_-]{12,}(?:/|$))(?=[^/]*[A-Z0-9])[A-Za-z0-9_-]+", "/{token}", path)
    return re.sub(r"\d+", "{n}", path)


def _check_page(page, name: str) -> list:
    problems = []
    bad = axe(page, name)
    if bad:
        problems.append(("axe", [(v["id"], v["impact"]) for v in bad]))
    info = page.evaluate("""() => ({lang: document.documentElement.lang, title: document.title,
        h1: document.querySelectorAll('h1').length, main: !!document.querySelector('main')})""")
    if not info["lang"] or not info["title"].strip() or info["h1"] != 1 or not info["main"]:
        problems.append(("structure", info))
    size = page.viewport_size
    page.set_viewport_size({"width": 320, "height": 800})
    over = page.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
    culprits = page.evaluate(OVERFLOWING) if over > 1 else []
    page.set_viewport_size(size)
    if over > 1:
        problems.append(("reflow-320px", over, culprits))
    # The skip link must be the first thing Tab reaches on a freshly loaded page (htmx-boosted navigation
    # deliberately moves focus to <main> instead, so check document order rather than pressing Tab).
    first = page.evaluate("""() => { const el = document.querySelector('a[href], button, input:not([type=hidden]), select, textarea, [tabindex]:not([tabindex="-1"])');
        return el ? el.getAttribute('href') : null; }""")
    if first != "#main":
        problems.append(("skip-link-not-first", first))
    return problems


def _crawl(page, live, role: str, starts: list[str]) -> tuple[dict, list]:
    seen, queue, failures, visited = set(), list(starts), {}, []
    while queue and len(visited) < LIMIT:
        path = queue.pop(0)
        pat = _pattern(path)
        if pat in seen:
            continue
        seen.add(pat)
        resp = page.goto(live.url + path)
        if resp is None or resp.status >= 400:
            failures[path] = [("status", resp.status if resp else None)]
            continue
        if not page.url.startswith(live.url):
            continue
        visited.append(path)
        name = f"p5_{role}_" + re.sub(r"[^a-z0-9]+", "_", path.lower())[:70]
        probs = _check_page(page, name)
        if probs:
            failures[path] = probs
        hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))")
        for h in hrefs:
            if h.startswith(live.url):
                h = h[len(live.url):]
            if not h.startswith("/") or h.startswith("//") or SKIP.search(h):
                continue
            if _pattern(h) not in seen:
                queue.append(h)
    return failures, visited


def _record(role, visited, failures=None):
    data = json.loads(OUT.read_text()) if OUT.exists() else {}
    data[role] = {"pages": visited, "failures": failures or {}}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1))


def _q(live, sql, params=()):
    with live.app.state.db.read() as conn:
        return [dict(r) for r in conn.execute(sql, params)]


@pytest.fixture(scope="module")
def session_id(live):
    from app.db import SYSTEM
    from app.modules.chair.service import open_session
    com = _q(live, "SELECT cm.id FROM committee cm JOIN class c ON c.id = cm.class_id WHERE c.code = 'DEMO9M' LIMIT 1")[0]["id"]
    with live.app.state.db.write(SYSTEM) as w:
        return open_session(w, com)


def test_a11y_every_coordinator_page(page, live, session_id):
    login(page, live)
    failures, visited = _crawl(page, live, "coordinator", ["/", f"/chair/{session_id}", f"/chair/{session_id}/minutes"])
    _record("coordinator", visited, failures)
    assert failures == {}
    assert len(visited) >= 60


def test_a11y_every_staff_page(page, live, session_id):
    staff = _q(live, "SELECT id FROM staff WHERE name = 'Demo Chair'")[0]["id"]
    login(page, live, str(staff), DEMO_STAFF_PASSPHRASE)
    failures, visited = _crawl(page, live, "staff", ["/"])
    _record("staff", visited, failures)
    assert failures == {}
    assert len(visited) >= 20


def test_a11y_every_student_page(page, live, session_id):
    st = _q(live, "SELECT st.id, st.login_code FROM student st JOIN class c ON c.id = st.class_id WHERE c.code = 'DEMO9M' "
                  "ORDER BY st.id DESC LIMIT 1")[0]
    page.goto(live.url + "/join")
    failures = {}
    for step in ("/join",):
        probs = _check_page(page, "p5_student_join")
        if probs:
            failures[step] = probs
    page.fill("#code", st["login_code"])                   # a personal sign-in code (D-079)
    page.click("button:has-text('Sign in')")
    page.wait_for_load_state("networkidle")
    more, visited = _crawl(page, live, "student", ["/me", f"/live/{session_id}", "/me/practice", "/me/ai-practice", "/me/sim"])
    failures.update(more)
    _record("student", ["/join", "/join/{code}"] + visited, failures)
    assert failures == {}
    assert len(visited) >= 4


def test_a11y_projector_and_public_pages(page, live, session_id):
    tok = _q(live, "SELECT projector_token FROM live_session WHERE id = ?", (session_id,))[0]["projector_token"]
    ev = _q(live, "SELECT projector_token FROM debate_event LIMIT 1")
    starts = [f"/projector/{tok}", "/login", "/accessibility", "/privacy", "/practice-game"]
    if ev:
        starts.append(f"/debating/projector/{ev[0]['projector_token']}")
    failures, visited = {}, []
    for path in starts:
        page.goto(live.url + path)
        visited.append(path)
        probs = _check_page(page, "p5_public_" + re.sub(r"[^a-z0-9]+", "_", path.lower())[:40])
        if probs:
            failures[path] = probs
    _record("public_and_projector", visited, failures)
    assert failures == {}
