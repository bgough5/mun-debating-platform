"""Screenshot gallery for design review (Phase 6 item 4).

  python tools/screenshots.py

Starts the platform on demo data (fake people only) in a temporary folder, sets up a realistic state (a live
session part-way through, a whip count, a closed vote with a debrief, a practice run), then captures each key
page at 1366×768 (laptop) and 1920×1080 (large screen), and the projector views as they appear on a classroom screen.
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
SIZES = {"laptop": (1366, 768), "large": (1920, 1080)}       # school laptops and the classroom screen; no phones (D-079)
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
    # The floor (D-068): an amendment with a suggested edit, a message, a point, the student's own drafts.
    from app.modules.floor import service as F
    from app.modules.mun import service as MS
    p2 = q(app, "SELECT p.id, v.text FROM paragraph p JOIN resolution r ON r.id = p.resolution_id JOIN paragraph_version v "
                "ON v.id = p.current_version_id WHERE r.committee_id = ? AND p.kind = 'operative' ORDER BY p.position LIMIT 1 OFFSET 1",
           (com["id"],))[0]
    with app.state.db.write(Actor("coordinator", None, "Coordinator")) as w:
        aid = MS.table_amendment(w, p2["id"], "replace", p2["text"].rstrip(".") + ", reporting progress every two years.", [],
                                 members[1]["delegation_id"], "Makes the commitment measurable")
        F.suggest(w, aid, members[2]["delegation_id"], members[2]["student_id"],
                  p2["text"].rstrip(".") + ", reporting progress every three years.", "Every two years is too often for small states")
        MS.support_amendment(w, aid, members[3]["delegation_id"], "signatory")
        SIM.set_stage(w, sid, "floor")
        F.raise_point(w, sid, members[3]["delegation_id"], members[3]["student_id"], "inquiry", "Can we extend the caucus?")
        F.send_message(w, sid, members[2]["delegation_id"], members[2]["student_id"], members[0]["delegation_id"],
                       "Would you sign our amendment on reporting? We can support your clause 3 in return.")
        SIM.set_stage(w, sid, "voting_procedure")
        F.save_draft(w, members[0]["student_id"], com["id"], "opening", "Opening statement",
                     "Honourable Chair, distinguished delegates. Our delegation comes to this committee because adaptation "
                     "finance decides whether the most exposed communities can plan ahead. (Demo text written for the screenshots.)")
        F.ff_save(w, members[0]["student_id"], para, com["id"], {members[1]["delegation_id"]: ("friend", "co-sponsor"),
                                                                  members[2]["delegation_id"]: ("undecided", "wants a softer verb")})
    # Phase 9: a class debate under way, an impromptu speaking round, and one student's case and speech (demo text).
    from app.modules.debating import classroom as RUN
    from app.modules.debating import prep as PREP
    cls9 = q(app, "SELECT id FROM class WHERE code = 'DEMO9M'")[0]["id"]
    names = [r["first_name"] for r in q(app, "SELECT first_name FROM student WHERE class_id = ? GROUP BY first_name HAVING COUNT(*) = 1 "
                                             "ORDER BY MIN(id) LIMIT 10", (cls9,))]
    with app.state.db.write(Actor("coordinator", None, "Coordinator")) as w:
        run = RUN.create_run(w, "debate", cls9, {"motion": "That zoos do more harm than good", "speakers_per_side": "3", "speech_seconds": "240",
                                                 "warning_seconds": "60", "reply": "1", "reply_seconds": "120",
                                                 **{f"aff_{i}": names[i - 1] for i in (1, 2, 3)}, **{f"neg_{i}": names[i + 2] for i in (1, 2, 3)}})
        RUN.act(w, RUN.get_run(w.conn, w.actor, run), "start")
        rnd9 = RUN.create_run(w, "speeches", cls9, {"names": "\n".join(names[6:10]), "topic_mode": "impromptu", "think_seconds": "60",
                                                     "speech_seconds": "120", "warning_seconds": "30", "level": "middle"})
        RUN.act(w, RUN.get_run(w.conn, w.actor, rnd9), "start")
    student9 = members[0]["student_id"]
    with app.state.db.write(Actor("student", student9, "student")) as w:
        mid = q(app, "SELECT id FROM motion_bank WHERE motion = 'That zoos do more harm than good'")[0]["id"]
        case = PREP.create_case(w, student9, mid, "", "neg")
        c = w.conn.execute("SELECT * FROM prep_case WHERE id = ?", (case,)).fetchone()  # not committed yet
        PREP.save_header(w, c, {"team_line": "Good zoos protect species and inspire people to care (demo text for the screenshots).", "definition": ""})
        PREP.save_point(w, c, {"kind": "argument", "part_claim": "Zoos save species from extinction.",
                               "part_reason": "Breeding programmes keep healthy populations when wild numbers collapse, then return animals to the wild.",
                               "part_evidence": "(Demo text: a real example and its source would go here.)", "part_impact": "", "speaker": "1",
                               "self_clarity": "4", "self_reasoning": "3"})
        speech = PREP.create_speech(w, student9, "persuasive", "Why every school needs a garden")
        sp = w.conn.execute("SELECT * FROM prep_speech WHERE id = ?", (speech,)).fetchone()
        PREP.save_speech(w, sp, {"target_seconds": "180", "sec_hook": "(Demo text for the screenshots.) When did you last eat something you grew?"})
    run_tok = q(app, "SELECT projector_token FROM class_run WHERE id = ?", (run,))[0]["projector_token"]
    rnd_tok = q(app, "SELECT projector_token FROM class_run WHERE id = ?", (rnd9,))[0]["projector_token"]
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
            "run": run, "run_tok": run_tok, "rnd_tok": rnd_tok, "case": case, "speech": speech, "cls9": cls9,
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
        ("class", f"/people/classes/{st['cls']}", "Class page: roster and sign-in codes"),
        ("join-cards", f"/people/classes/{st['cls']}/join-cards", "Printable sign-in cards, one per student"),
        ("amendment-board", f"/mun/committees/{st['com']}/amendments", "Amendment board: tracked changes, signatories, suggestions"),
        ("chair-messages", f"/chair/{st['sid']}/messages", "Chair: delegate messages"),
        ("debating", "/debating", "Debating and public speaking home"),
        ("run-setup", f"/debating/runs/new?kind=debate&class_id={st['cls9']}", "New class debate: names and times"),
        ("run-control", f"/debating/runs/{st['run']}", "Running a class debate: the teacher's page"),
        ("run-results", f"/debating/runs/{st['run']}/results", "Class debate: scores and result"),
        ("class-prep", f"/debating/prep?class_id={st['cls9']}", "Student preparation for a class"),
        ("class-prep-case", f"/debating/prep/cases/{st['case']}", "Scoring a student's case"),
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
        ("student-tab-motions", f"/live/{st['sid']}?tab=motions", "Student tab: motions and votes"),
        ("student-tab-messages", f"/live/{st['sid']}?tab=messages", "Student tab: messages between delegations"),
        ("student-tab-speech", f"/live/{st['sid']}?tab=speech", "Student tab: my speech (private drafts)"),
        ("student-prepare", f"/me/committees/{st['com']}/prepare", "Prepare: country brief, resolution, opening statement"),
        ("student-friends-foes", f"/me/committees/{st['com']}/friends-foes", "Friends and foes for an operative clause"),
        ("student-me", "/me", "Student home"),
        ("student-practice", "/me/sim", "Practice committee"),
        ("student-prep", "/me/prep", "Prep and practise"),
        ("student-case", f"/me/prep/cases/{st['case']}", "A debate case: arguments and rebuttals"),
        ("student-speech", f"/me/prep/speeches/{st['speech']}", "Speech writer"),
        ("student-speaking", "/me/practice", "Impromptu speaking practice"),
    ]
    projector_pages = [
        ("projector-session", f"/projector/{st['tok']}", "Projector: live session"),
        ("projector-debating", f"/debating/projector/{st['ev']['projector_token']}", "Projector: debating event"),
        ("projector-class-debate", f"/debating/present/{st['run_tok']}", "Projector: class debate timer"),
        ("projector-speaking-round", f"/debating/present/{st['rnd_tok']}", "Projector: impromptu speaking round"),
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
            stu = b.new_context(viewport={"width": wd, "height": ht}, device_scale_factor=1)
            sp = stu.new_page()
            code = q(app, "SELECT login_code FROM student WHERE id = ?", (st["student"],))[0]["login_code"]
            sp.goto(srv.url + "/join")
            sp.fill("#code", f"{code[:3]}-{code[3:]}")
            sp.screenshot(path=str(OUT / f"student-join-{size}.png"))
            shots.append(("student-join", size, f"student-join-{size}.png", "Student sign-in: the code from their card", "/join"))
            sp.click("button:has-text('Sign in')")
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
             "1920×1080 (a large monitor or the classroom screen); projector views are what the classroom screen shows. Regenerate after design changes.", ""]
    for key, v in by_key.items():
        lines += [f"## {v['caption']}", "", f"`{v['url']}`", "",
                  "| Laptop (1366×768) | Large screen (1920×1080) |", "|---|---|",
                  f"| ![{v['caption']}, laptop]({v.get('laptop', '')}) | ![{v['caption']}, large screen]({v.get('large', '')}) |", ""]
    (OUT / "index.md").write_text("\n".join(lines), encoding="utf-8")
    total = sum(f.stat().st_size for f in OUT.glob("*.png"))
    print(f"{len(shots)} screenshots, {total / 1e6:.1f} MB -> {OUT}")


if __name__ == "__main__":
    main()
