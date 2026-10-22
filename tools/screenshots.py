"""Screenshot gallery for design review (Phase 6 item 4).

  python tools/screenshots.py

Starts the platform on demo data (fake people only) in a temporary folder, sets up a realistic state (a live
session part-way through, a whip count, a closed vote with a debrief, a practice run), then captures each key
page at 1366×768 (laptop) and 390×844 (phone), and the projector views as they appear on a classroom screen.
Writes PNGs and docs/screens/index.md. Viewport-only captures, so each image shows what fits on one screen.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "docs" / "screens"
SIZES = {"laptop": (1366, 768), "phone": (390, 844)}
FALLBACK_CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"


def q(app, sql, params=()):
    with app.state.db.read() as conn:
        return [dict(r) for r in conn.execute(sql, params)]


def prepare(app) -> dict:
    """A realistic mid-lesson state, built through the same service functions the pages use."""
    from app.db import SYSTEM, Actor
    from app.modules.chair import service as C
    from app.modules.sim import service as SIM
    com = q(app, "SELECT * FROM committee WHERE name LIKE 'United Nations General Assembly%'")[0]
    para = q(app, "SELECT p.id FROM paragraph p JOIN resolution r ON r.id = p.resolution_id WHERE r.committee_id = ? "
                  "AND p.kind = 'operative' ORDER BY p.position LIMIT 1", (com["id"],))[0]["id"]
    members = q(app, "SELECT dm.student_id, d.id AS delegation_id, d.iso3 FROM delegation_member dm JOIN delegation d ON d.id = dm.delegation_id "
                     "WHERE d.committee_id = ? AND dm.deleted_at IS NULL ORDER BY d.iso3", (com["id"],))
    from app.modules.mun.predict import run_prediction
    with app.state.db.read() as conn:
        pred = run_prediction(conn, "paragraph", para, with_swing=False)
    with app.state.db.write(Actor("coordinator", None, "Coordinator")) as w:
        sid = C.open_session(w, com["id"])
        s = C.get_session(w.conn, sid)
        for m in members:
            SIM.answer_roll(w, s, m["delegation_id"], "present")
        SIM.roll_computed(w, s)
        SIM.set_agenda(w, sid, "Climate finance for adaptation")
        for m in members[:4]:
            C.add_speaker(w, sid, m["delegation_id"], m["student_id"])
        C.next_speaker(w, sid)
        # A first vote, already closed, so there is a debrief to show.
        r1 = SIM.start_whip(w, s, "paragraph", para, "Operative paragraph 1", 4)
        for p in w.conn.execute("SELECT * FROM whip_prediction WHERE round_id = ?", (r1,)).fetchall():
            SIM.predict(w, r1, p["student_id"], p["delegation_id"], ["yes", "no", "abstain"][p["id"] % 3])
        did = C.open_division(w, sid, "Operative paragraph 1", "paragraph", para, pred=pred)
        SIM.lock_round(w, r1, did)
        for i, m in enumerate(members):
            C.cast_vote(w, did, m["delegation_id"], ["yes", "yes", "no", "abstain"][i % 4])
        C.close_division(w, did)
        # Now mid-way through voting procedure on a second whip count.
        SIM.set_stage(w, sid, "voting_procedure")
        r2 = SIM.start_whip(w, s, "resolution", q(app, "SELECT id FROM resolution WHERE committee_id = ?", (com["id"],))[0]["id"],
                            "Draft resolution as a whole", 4)
    tok = q(app, "SELECT projector_token FROM live_session WHERE id = ?", (sid,))[0]["projector_token"]
    ev = q(app, "SELECT * FROM debate_event WHERE projector_token IS NOT NULL ORDER BY id LIMIT 1")[0]
    rnd = q(app, "SELECT id FROM debate_round WHERE event_id = ? ORDER BY number LIMIT 1", (ev["id"],))[0]["id"]
    pairing = q(app, "SELECT id FROM pairing WHERE round_id = ? AND neg_team_id IS NOT NULL LIMIT 1", (rnd,))[0]["id"]
    cls = q(app, "SELECT id FROM class WHERE code = 'DEMO9M'")[0]["id"]
    res = q(app, "SELECT id FROM resolution WHERE committee_id = ?", (com["id"],))[0]["id"]
    evatt = q(app, "SELECT id FROM committee WHERE name LIKE 'Security Council: the situation in Veloria%'")
    evatt_para = q(app, "SELECT p.id FROM paragraph p JOIN resolution r ON r.id = p.resolution_id JOIN paragraph_version v ON v.id = p.current_version_id "
                        "WHERE r.committee_id = ? AND v.tags = 'sanctions'", (evatt[0]["id"],)) if evatt else []
    return {"evatt": evatt[0]["id"] if evatt else None, "evatt_para": evatt_para[0]["id"] if evatt_para else None,
            "sid": sid, "did": did, "tok": tok, "ev": ev, "rnd": rnd, "pairing": pairing, "cls": cls, "com": com["id"],
            "res": res, "para": para, "student": members[0]["student_id"]}


def main() -> None:
    from playwright.sync_api import sync_playwright

    from app.main import create_app
    from tests.conftest import COORD_PASS, make_settings
    from tests.ui.conftest import LiveServer, free_port
    tmp = Path(tempfile.mkdtemp(prefix="soc-shots-"))
    app = create_app(make_settings(tmp))
    srv = LiveServer(app, free_port()).start()
    st = prepare(app)
    staff_pages = [
        ("dashboard", "/", "Coordinator dashboard"),
        ("wizard", "/welcome", "Getting-started wizard"),
        ("chair-guide", f"/chair/{st['sid']}", "Chair console: the guide (stage, script, whip count)"),
        ("debrief", f"/chair/{st['sid']}/debrief/{st['did']}", "Debrief after a vote"),
        ("committee", f"/mun/committees/{st['com']}", "Committee page"),
        ("workspace", f"/mun/resolutions/{st['res']}", "Resolution workspace"),
        ("prediction", f"/mun/predict/paragraph/{st['para']}", "Prediction with swing list"),
        ("evidence", f"/mun/committees/{st['com']}/evidence", "Evidence entry"),
        ("class", f"/people/classes/{st['cls']}", "Class page with join code"),
        ("join-cards", f"/people/classes/{st['cls']}/join-cards", "Printable join cards with QR codes"),
        ("debating", "/debating", "Debating home"),
        ("event", f"/debating/events/{st['ev']['id']}", "Debating event"),
        ("draw", f"/debating/rounds/{st['rnd']}", "Round draw"),
        ("ballot", f"/debating/pairings/{st['pairing']}/ballot", "Ballot (rubric scoring)"),
        ("results", f"/debating/events/{st['ev']['id']}/results", "Ladder, speaker tab and house points"),
        ("admin", "/admin", "Admin home"),
        ("glossary", "/help/glossary", "Glossary"),
    ]
    if st["evatt"]:
        staff_pages += [("evatt-committee", f"/mun/committees/{st['evatt']}", "Evatt-style Security Council demo (fictional crisis)"),
                        ("evatt-prediction", f"/mun/predict/paragraph/{st['evatt_para']}", "Security Council prediction with vetoes")]
    student_pages = [
        ("student-live", f"/live/{st['sid']}", "Student live page: stage and whip count"),
        ("student-me", "/me", "Student home"),
        ("student-practice", "/me/sim", "Practice committee"),
    ]
    projector_pages = [
        ("projector-session", f"/projector/{st['tok']}", "Projector: live session"),
        ("projector-debating", f"/debating/projector/{st['ev']['projector_token']}", "Projector: debating event"),
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()
    shots = []
    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception:
            b = p.chromium.launch(executable_path=os.environ.get("PW_CHROMIUM", FALLBACK_CHROMIUM))
        for size, (wd, ht) in SIZES.items():
            staff = b.new_context(viewport={"width": wd, "height": ht}, device_scale_factor=1)
            pg = staff.new_page()
            pg.goto(srv.url + "/login")
            pg.select_option("#who", "coordinator")
            pg.fill("#pp", COORD_PASS)
            pg.click("button:has-text('Sign in')")
            pg.wait_for_load_state("networkidle")
            for key, url, caption in staff_pages + projector_pages:
                pg.goto(srv.url + url)
                pg.wait_for_load_state("networkidle")
                name = f"{key}-{size}.png"
                pg.screenshot(path=str(OUT / name))
                shots.append((key, size, name, caption, url))
            staff.close()
            # The laptop pass claimed this student's name; release it as a teacher would, so the phone can join.
            from app.db import Actor
            from app.web.auth import revoke_devices
            with app.state.db.write(Actor("coordinator", None, "Coordinator")) as w:
                revoke_devices(w.conn, "student_id = ?", (st["student"],))
            stu = b.new_context(viewport={"width": wd, "height": ht}, device_scale_factor=1)
            sp = stu.new_page()
            code = q(app, "SELECT c.code FROM student st JOIN class c ON c.id = st.class_id WHERE st.id = ?", (st["student"],))[0]["code"]
            sp.goto(srv.url + f"/join?code={code}")
            sp.click("button:has-text('Next')")
            sp.wait_for_url(re.compile(r"/join/"))
            sp.screenshot(path=str(OUT / f"student-join-{size}.png"))
            shots.append(("student-join", size, f"student-join-{size}.png", "Student join: tap your name", "/join/{code}"))
            sp.locator(f"form[action='/join/{code}/{st['student']}'] button").click()
            sp.wait_for_url(re.compile(r"/me$"))
            for key, url, caption in student_pages:
                sp.goto(srv.url + url)
                sp.wait_for_load_state("networkidle")
                name = f"{key}-{size}.png"
                sp.screenshot(path=str(OUT / name))
                shots.append((key, size, name, caption, url))
            stu.close()
        b.close()
    srv.stop()
    by_key: dict[str, dict] = {}
    for key, size, name, caption, url in shots:
        by_key.setdefault(key, {"caption": caption, "url": re.sub(r"/[A-Za-z0-9_-]{14,}", "/{token}", url)})[size] = name
    lines = ["# Screenshot gallery", "",
             "Generated by `python tools/screenshots.py` on demo data (fake people only). Each page at 1366×768 (laptop) and "
             "390×844 (phone); projector views are what the classroom screen shows. Regenerate after design changes.", ""]
    for key, v in by_key.items():
        lines += [f"## {v['caption']}", "", f"`{v['url']}`", "",
                  "| Laptop (1366×768) | Phone (390×844) |", "|---|---|",
                  f"| ![{v['caption']}, laptop]({v.get('laptop', '')}) | ![{v['caption']}, phone]({v.get('phone', '')}) |", ""]
    (OUT / "index.md").write_text("\n".join(lines), encoding="utf-8")
    total = sum(f.stat().st_size for f in OUT.glob("*.png"))
    print(f"{len(shots)} screenshots, {total / 1e6:.1f} MB -> {OUT}")


if __name__ == "__main__":
    main()
