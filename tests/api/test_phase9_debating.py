"""Debating and public speaking as a classroom and preparation tool (D-074 to D-077): the classroom runner, the prep
studio, speaking practice, and the privacy rules for typed names and student writing."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from app.db import SYSTEM
from app.modules.debating import classroom as R
from app.modules.debating import prep as P
from app.web.ws import channel_allowed
from tests.api.helpers import join_as
from tests.conftest import db_one, db_rows, login_staff, new_client


def _class(app):
    cls = db_one(app, "SELECT * FROM class WHERE name LIKE 'Year 9%'")
    students = db_rows(app, "SELECT * FROM student WHERE class_id = ? AND deleted_at IS NULL ORDER BY id", (cls["id"],))
    return cls, students


def _unique_first(students, n):
    """Students whose first name is unique in the class, so a typed first name links to them."""
    counts = {}
    for s in students:
        counts[s["first_name"]] = counts.get(s["first_name"], 0) + 1
    return [s for s in students if counts[s["first_name"]] == 1][:n]


def _debate(coord, app, **extra):
    cls, students = _class(app)
    six = _unique_first(students, 6)
    data = {"kind": "debate", "class_id": cls["id"], "motion": "That zoos do more harm than good", "speakers_per_side": 3,
            "speech_seconds": 240, "warning_seconds": 60, "prep_minutes": 0, "reply": "1", "reply_seconds": 120}
    for i, s in enumerate(six[:3], 1):
        data[f"aff_{i}"] = s["first_name"]
    for i, s in enumerate(six[3:], 1):
        data[f"neg_{i}"] = s["first_name"]
    data.update(extra)
    r = coord.post("/debating/runs", data)
    assert r.status_code == 200, r.text[:300]
    run = db_one(app, "SELECT * FROM class_run ORDER BY id DESC LIMIT 1")
    return run, six


def _act(c, run_id, action, arg=None):
    data = {"action": action}
    if arg is not None:
        data["arg"] = arg
    r = c.post(f"/debating/runs/{run_id}/act", data, headers={"X-Run-Control": "1"}, follow_redirects=False)
    assert r.status_code == 204, r.text[:300]


def _run(app, rid):
    return db_one(app, "SELECT * FROM class_run WHERE id = ?", (rid,))


# ---------- content ----------

def test_every_motion_has_three_likely_arguments_a_side_and_the_new_content_is_seeded(app):
    counts = db_rows(app, "SELECT m.id, SUM(a.side = 'aff') AS aff, SUM(a.side = 'neg') AS neg FROM motion_bank m "
                          "LEFT JOIN motion_argument a ON a.motion_id = m.id AND a.deleted_at IS NULL WHERE m.deleted_at IS NULL GROUP BY m.id")
    assert len(counts) >= 120 and all(c["aff"] == 3 and c["neg"] == 3 for c in counts)
    assert db_one(app, "SELECT COUNT(*) AS n FROM impromptu_topic")["n"] >= 100
    kinds = {t["code"]: t["kind"] for t in db_rows(app, "SELECT code, kind FROM speech_template")}
    assert sum(k == "impromptu" for k in kinds.values()) == 4 and sum(k == "prepared" for k in kinds.values()) == 4
    for code in ("argument_written", "rebuttal_written"):
        assert db_one(app, "SELECT COUNT(*) AS n FROM rubric_criterion rc JOIN rubric r ON r.id = rc.rubric_id WHERE r.code = ?", (code,))["n"] == 4


def test_reseeding_adds_nothing_twice_and_keeps_a_teachers_edits(app):
    from app.db.seed import seed_content_updates
    before = db_one(app, "SELECT COUNT(*) AS n FROM motion_argument")["n"]
    a = db_one(app, "SELECT * FROM motion_argument ORDER BY id LIMIT 1")
    with app.state.db.write(SYSTEM) as w:
        w.update("motion_argument", a["id"], {"argument": "A teacher's own wording"})
        w.conn.execute("DELETE FROM rubric_descriptor WHERE criterion_id IN (SELECT rc.id FROM rubric_criterion rc JOIN rubric r ON r.id = rc.rubric_id WHERE r.code = 'rebuttal_written')")
        w.conn.execute("DELETE FROM rubric_criterion WHERE rubric_id = (SELECT id FROM rubric WHERE code = 'rebuttal_written')")
        w.conn.execute("DELETE FROM rubric WHERE code = 'rebuttal_written'")
        seed_content_updates(w.conn)
    assert db_one(app, "SELECT COUNT(*) AS n FROM motion_argument")["n"] == before
    assert db_one(app, "SELECT argument FROM motion_argument WHERE id = ?", (a["id"],))["argument"] == "A teacher's own wording"
    assert db_one(app, "SELECT COUNT(*) AS n FROM rubric WHERE code = 'rebuttal_written'")["n"] == 1


# ---------- the classroom runner ----------

def test_class_debate_runs_in_order_and_records_each_speakers_time(coord, app, monkeypatch):
    run, six = _debate(coord, app)
    spk = db_rows(app, "SELECT * FROM class_run_speaker WHERE run_id = ?", (run["id"],))
    assert sorted(s["student_id"] for s in spk) == sorted(s["id"] for s in six)          # typed first names link to the roster
    steps = R.steps(run, spk)
    assert [s["key"] for s in steps] == ["aff1", "neg1", "aff2", "neg2", "aff3", "neg3", "negR", "affR"]

    clock = [1000.0]
    monkeypatch.setattr(R, "now", lambda: clock[0])
    _act(coord, run["id"], "start")
    clock[0] += 200
    page = coord.get(f"/debating/runs/{run['id']}/f").text
    assert 'data-state="running"' in page and "Speaking" in page
    clock[0] += 50                      # 250 s: past the 240 s limit
    _act(coord, run["id"], "next")
    r = _run(app, run["id"])
    assert r["step"] == 1 and r["timer_state"] == "idle" and json.loads(r["step_seconds"]) == {"aff1": 250.0}
    _act(coord, run["id"], "start")
    clock[0] += 100
    _act(coord, run["id"], "pause")
    clock[0] += 500                     # paused time doesn't count
    _act(coord, run["id"], "next")
    assert json.loads(_run(app, run["id"])["step_seconds"])["neg1"] == 100.0
    view = R.view(app.state.db.connect(), _run(app, run["id"]))
    times = {(s["side"], s["position"]): (s["seconds"], s["timing"]) for s in view["speakers"]}
    assert times[("aff", 1)] == (250.0, "on time") and times[("neg", 1)] == (100.0, "short")
    for _ in range(6):
        _act(coord, run["id"], "next")
    assert _run(app, run["id"])["status"] == "finished"


def test_the_timer_shows_the_bells_as_phases(app, coord, monkeypatch):
    run, _ = _debate(coord, app)
    clock = [0.0]
    monkeypatch.setattr(R, "now", lambda: clock[0])
    _act(coord, run["id"], "start")
    conn = app.state.db.connect()
    phase = lambda: R.view(conn, _run(app, run["id"]))["phase"]
    clock[0] = 10
    assert phase() == "go"
    clock[0] = 181                      # 59 s left: after the one-minute warning bell
    assert phase() == "warn"
    clock[0] = 241
    assert phase() == "over"
    assert "+0:01" in coord.get(f"/debating/runs/{run['id']}/f").text


def test_names_are_first_names_only(coord, app):
    for bad in ("mia@school.vic.edu.au", "Mia 0412 345 678", "Mia Kowalski-Smith-Jones Esq", "<script>"):
        r = coord.post("/debating/runs", {"kind": "speeches", "names": bad})
        assert r.status_code == 400, bad
    assert R.clean_name("  Mia   K ") == "Mia K"
    r = coord.post("/debating/runs", {"kind": "speeches", "names": "Mia\nSam - Why we need more trees"})
    assert r.status_code == 200
    spk = db_rows(app, "SELECT * FROM class_run_speaker WHERE run_id = (SELECT MAX(id) FROM class_run) ORDER BY position")
    assert [(s["name"], s["topic"], s["student_id"]) for s in spk] == [("Mia", "", None), ("Sam", "Why we need more trees", None)]


def test_impromptu_topics_are_drawn_when_each_turn_starts_and_hidden_before(coord, app):
    cls, students = _class(app)
    names = "\n".join(s["first_name"] for s in _unique_first(students, 3))
    coord.post("/debating/runs", {"kind": "speeches", "class_id": cls["id"], "names": names, "topic_mode": "impromptu",
                                  "think_seconds": "30", "speech_seconds": "60", "level": "junior"})
    run = db_one(app, "SELECT * FROM class_run ORDER BY id DESC LIMIT 1")
    topics = lambda: [s["topic"] for s in db_rows(app, "SELECT topic FROM class_run_speaker WHERE run_id = ? ORDER BY position", (run["id"],))]
    assert topics() == ["", "", ""]
    _act(coord, run["id"], "start")                         # first speaker's thinking time
    first = topics()[0]
    assert first and topics()[1:] == ["", ""]
    proj = coord.get(f"/debating/present/{run['projector_token']}").text
    assert first.replace("'", "&#39;") in proj
    _act(coord, run["id"], "next")                          # speech
    _act(coord, run["id"], "next")                          # second speaker thinks
    assert topics()[1] and topics()[1] != first and topics()[2] == ""
    level_ok = {t["topic"] for t in db_rows(app, "SELECT topic FROM impromptu_topic WHERE level IN ('junior', 'any')")}
    assert set(t for t in topics() if t) <= level_ok


def test_projector_needs_the_token_and_only_staff_run_it(coord, app):
    run, six = _debate(coord, app)
    assert coord.get(f"/debating/present/{run['projector_token']}").status_code == 200
    with new_client(app) as anon:
        assert anon.get(f"/debating/present/{run['projector_token']}").status_code == 200
        assert anon.get("/debating/present/not-the-token").status_code == 404
        assert anon.get(f"/debating/runs/{run['id']}", follow_redirects=False).status_code in (303, 401, 403)
    pupil = join_as(app, six[0]["id"])
    for u in (f"/debating/runs/{run['id']}", f"/debating/runs/{run['id']}/results"):
        assert pupil.get(u, follow_redirects=False).status_code in (403, 303)
    assert pupil.post(f"/debating/runs/{run['id']}/act", {"action": "start"}, follow_redirects=False).status_code in (403, 303)
    conn = app.state.db.connect()
    assert channel_allowed(conn, None, f"run:{run['id']}", run["projector_token"], 25)[0]
    assert not channel_allowed(conn, None, f"run:{run['id']}", "wrong", 25)[0]
    from app.db import Actor
    assert not channel_allowed(conn, Actor("student", six[0]["id"], "x", six[0]["class_id"]), f"run:{run['id']}", None, 25)[0]
    assert channel_allowed(conn, Actor("coordinator", None, "c"), f"run:{run['id']}", None, 25)[0]


def test_other_staff_cannot_open_a_run_for_a_class_they_dont_teach(coord, app):
    run, _ = _debate(coord, app)
    coord.post("/people/staff", {"action": "create", "name": "Mr Elsewhere", "passphrase": "elsewhere passphrase"})
    other = db_one(app, "SELECT id FROM staff WHERE name = 'Mr Elsewhere'")["id"]
    small = db_one(app, "SELECT id FROM class WHERE name LIKE 'Lunchtime%'")["id"]
    coord.post("/people/staff", {"action": "classes", "staff_id": other, "class_id": [str(small)]})
    with new_client(app) as t:
        login_staff(t, other, "elsewhere passphrase")
        assert t.get(f"/debating/runs/{run['id']}").status_code == 403
        assert t.post(f"/debating/runs/{run['id']}/act", {"action": "start"}).status_code == 403
        assert run["title"] not in t.get("/debating").text
        # Their own run with no class is theirs alone.
        assert t.post("/debating/runs", {"kind": "speeches", "names": "Ana"}).status_code == 200
        mine = db_one(app, "SELECT * FROM class_run ORDER BY id DESC LIMIT 1")
        assert mine["staff_id"] == other and t.get(f"/debating/runs/{mine['id']}").status_code == 200


def test_scores_reach_the_student_and_no_one_else(coord, app):
    run, six = _debate(coord, app)
    crit = db_rows(app, "SELECT rc.* FROM rubric_criterion rc JOIN rubric r ON r.id = rc.rubric_id WHERE r.code = 'debate_speaker' ORDER BY position")
    spk = {s["student_id"]: s for s in db_rows(app, "SELECT * FROM class_run_speaker WHERE run_id = ?", (run["id"],))}
    me = spk[six[0]["id"]]
    data = {f"sc_{me['id']}_{c['id']}": str(c["max_score"] * 0.75) for c in crit}
    data.update({f"cm_{me['id']}": "Strong rebuttal of their second point", "winner": "aff"})
    assert coord.post(f"/debating/runs/{run['id']}/results", data).status_code == 200
    assert coord.post(f"/debating/runs/{run['id']}/results", {f"sc_{me['id']}_{crit[0]['id']}": "999"}).status_code == 400
    page = join_as(app, six[0]["id"]).get("/me/prep").text
    assert "Strong rebuttal of their second point" in page and "your team won" in page
    other = join_as(app, six[3]["id"]).get("/me/prep").text
    assert "Strong rebuttal of their second point" not in other and "your team lost" in other


def test_editing_names_keeps_scores_for_unchanged_speakers(coord, app):
    run, six = _debate(coord, app)
    s1 = db_one(app, "SELECT * FROM class_run_speaker WHERE run_id = ? AND side = 'aff' AND position = 1", (run["id"],))
    with app.state.db.write(SYSTEM) as w:
        w.update("class_run_speaker", s1["id"], {"scores": json.dumps({"1": 30}), "comment": "keep"})
    data = {"speakers_per_side": 2, "speech_seconds": 180, "warning_seconds": 30, "aff_1": six[0]["first_name"], "aff_2": "Zed",
            "neg_1": six[3]["first_name"], "neg_2": six[4]["first_name"], "motion": run["motion"]}
    assert coord.post(f"/debating/runs/{run['id']}/edit", data).status_code == 200
    rows = db_rows(app, "SELECT * FROM class_run_speaker WHERE run_id = ? AND deleted_at IS NULL ORDER BY side, position", (run["id"],))
    assert len(rows) == 4
    kept = next(r for r in rows if r["side"] == "aff" and r["position"] == 1)
    assert kept["comment"] == "keep" and json.loads(kept["scores"]) == {"1": 30}
    renamed = next(r for r in rows if r["side"] == "aff" and r["position"] == 2)
    assert renamed["name"] == "Zed" and renamed["student_id"] is None and renamed["scores"] == "{}"
    assert len(R.steps(_run(app, run["id"]), rows)) == 4


# ---------- the prep studio ----------

def _case(app, student, side="aff"):
    c = join_as(app, student["id"])
    mid = db_one(app, "SELECT id FROM motion_bank WHERE motion LIKE 'That zoos%'")["id"]
    r = c.post("/me/prep/cases", {"motion_id": mid, "side": side})
    assert r.status_code == 200
    return c, db_one(app, "SELECT * FROM prep_case WHERE student_id = ? ORDER BY id DESC LIMIT 1", (student["id"],)), mid


def test_a_case_shows_the_other_sides_likely_arguments_to_rebut(app):
    _, students = _class(app)
    c, case, mid = _case(app, students[0], "aff")
    page = c.get(f"/me/prep/cases/{case['id']}").text
    for a in db_rows(app, "SELECT argument, side FROM motion_argument WHERE motion_id = ?", (mid,)):
        shown = a["argument"].replace("'", "&#39;") in page
        assert shown == (a["side"] == "neg"), a          # the Negative's arguments, not the student's own side's
    assert "not the only arguments and not evidence" in page


def test_structure_check_counts_parts_and_rubric_scores_stay_separate(app):
    _, students = _class(app)
    c, case, mid = _case(app, students[0], "neg")
    aff_arg = db_one(app, "SELECT * FROM motion_argument WHERE motion_id = ? AND side = 'aff' ORDER BY position LIMIT 1", (mid,))
    neg_arg = db_one(app, "SELECT * FROM motion_argument WHERE motion_id = ? AND side = 'neg' LIMIT 1", (mid,))
    r = c.post(f"/me/prep/cases/{case['id']}/points", {"kind": "rebuttal", "source_argument_id": aff_arg["id"],
               "part_they_say": "Enclosures are smaller than their range", "part_flaw": "Size alone doesn't measure welfare for every species",
               "part_support": "Modern zoos design habitats around behaviour, not just area", "part_impact": "", "self_clash": "4"})
    assert r.status_code == 200
    assert c.post(f"/me/prep/cases/{case['id']}/points", {"kind": "rebuttal", "source_argument_id": neg_arg["id"], "part_flaw": "x"}).status_code == 400
    assert c.post(f"/me/prep/cases/{case['id']}/points", {"kind": "rebuttal", "source_argument_id": aff_arg["id"], "part_flaw": "again"}).status_code == 400
    p = db_one(app, "SELECT * FROM prep_point WHERE case_id = ?", (case["id"],))
    assert P.structure("rebuttal", json.loads(p["parts"])) == {"done": 3, "total": 4, "complete": False, "missing": ["So"]}
    assert json.loads(p["self_scores"]) == {"clash": 4.0} and json.loads(p["staff_scores"]) == {}
    assert "Structure: 3 of 4 parts" in c.get(f"/me/prep/cases/{case['id']}").text
    for n in range(6):
        c.post(f"/me/prep/cases/{case['id']}/points", {"kind": "argument", "part_claim": f"Point number {n} here"})
    assert db_one(app, "SELECT COUNT(*) AS n FROM prep_point WHERE case_id = ? AND kind = 'argument'", (case["id"],))["n"] == P.MAX_POINTS["argument"]


def test_cases_are_private_to_the_student_and_their_teachers(coord, app):
    _, students = _class(app)
    c, case, _ = _case(app, students[0])
    c.post(f"/me/prep/cases/{case['id']}/points", {"kind": "argument", "part_claim": "Captivity harms wild animals badly"})
    pid = db_one(app, "SELECT id FROM prep_point WHERE case_id = ?", (case["id"],))["id"]
    other = join_as(app, students[1]["id"])
    assert other.get(f"/me/prep/cases/{case['id']}").status_code == 403
    assert other.post(f"/me/prep/cases/{case['id']}/points", {"kind": "argument", "part_claim": "sneaky edit here"}).status_code == 403
    assert other.post(f"/me/prep/cases/{case['id']}/delete").status_code == 403
    coord.post("/people/staff", {"action": "create", "name": "Ms Nearby", "passphrase": "nearby passphrase"})
    st = db_one(app, "SELECT id FROM staff WHERE name = 'Ms Nearby'")["id"]
    small = db_one(app, "SELECT id FROM class WHERE name LIKE 'Lunchtime%'")["id"]
    coord.post("/people/staff", {"action": "classes", "staff_id": st, "class_id": [str(small)]})
    with new_client(app) as t:
        login_staff(t, st, "nearby passphrase")
        assert t.get(f"/debating/prep/cases/{case['id']}").status_code == 403
        assert t.get(f"/debating/prep?class_id={students[0]['class_id']}").status_code == 403
    assert coord.post(f"/debating/prep/cases/{case['id']}", {f"st_{pid}_clarity": "5", "staff_comment": "Make the impact explicit"}).status_code == 200
    page = c.get(f"/me/prep/cases/{case['id']}").text
    assert "Make the impact explicit" in page and "your teacher 5.0" in page


def test_speech_writer_counts_words_and_estimates_time(app):
    _, students = _class(app)
    c = join_as(app, students[0]["id"])
    assert c.post("/me/prep/speeches", {"template_code": "prep", "title": "x"}).status_code == 400     # impromptu structures aren't drafts
    c.post("/me/prep/speeches", {"template_code": "persuasive", "title": "Why we need more trees"})
    sp = db_one(app, "SELECT * FROM prep_speech WHERE student_id = ?", (students[0]["id"],))
    text = " ".join(["word"] * 130)
    assert c.post(f"/me/prep/speeches/{sp['id']}", {"title": "Trees", "target_seconds": "120", "sec_hook": text}).status_code == 200
    view = P.speech_view(app.state.db.connect(), db_one(app, "SELECT * FROM prep_speech WHERE id = ?", (sp["id"],)))
    assert view["words"] == 130 and view["seconds"] == 60 and [s["key"] for s in view["sections"]][:2] == ["hook", "position"]
    for u in ("", "/rehearse", "/cards"):
        assert c.get(f"/me/prep/speeches/{sp['id']}{u}").status_code == 200
    assert join_as(app, students[1]["id"]).get(f"/me/prep/speeches/{sp['id']}").status_code == 403


def test_practice_modes_and_saved_topics(app):
    _, students = _class(app)
    c = join_as(app, students[0]["id"])
    for mode in ("impromptu", "prepared", "rebuttal"):
        page = c.get(f"/me/practice?mode={mode}").text
        assert 'id="practice-topics"' in page and "Practise a speech" in page
    material = P.practice_material(app.state.db.connect(), students[0]["id"])
    assert len(material["impromptu"]) >= 100 and len(material["rebuttal"]) == 60
    assert c.post("/me/practice", {"mode": "rebuttal", "topic": "Zoos breed endangered species", "target_seconds": "60",
                                   "actual_seconds": "58"}).status_code == 200
    assert db_one(app, "SELECT topic FROM practice_speech WHERE student_id = ?", (students[0]["id"],))["topic"] == \
        "Rebuttal drill: Zoos breed endangered species"


# ---------- privacy ----------

def test_erasing_a_student_removes_their_prep_and_their_name_from_runs(coord, app):
    from app.retention import erase_student
    run, six = _debate(coord, app)
    victim = six[0]
    c, case, _ = _case(app, victim)
    c.post(f"/me/prep/cases/{case['id']}/points", {"kind": "argument", "part_claim": "My own words about zoos"})
    c.post("/me/prep/speeches", {"template_code": "story", "title": "My grandmother's garden"})
    spk = db_one(app, "SELECT * FROM class_run_speaker WHERE run_id = ? AND student_id = ?", (run["id"], victim["id"]))
    with app.state.db.write(SYSTEM) as w:
        w.update("class_run_speaker", spk["id"], {"comment": "Lovely voice", "scores": json.dumps({"1": 30})})
        counts = erase_student(w, victim["id"])
    assert counts["prep_case"] == 1 and counts["prep_point"] == 1 and counts["prep_speech"] == 1
    for t in ("prep_case", "prep_speech"):
        assert db_one(app, f"SELECT COUNT(*) AS n FROM {t} WHERE student_id = ?", (victim["id"],))["n"] == 0
    after = db_one(app, "SELECT * FROM class_run_speaker WHERE id = ?", (spk["id"],))
    assert after["name"] == "Erased" and after["comment"] == "" and json.loads(after["scores"]) == {"1": 30}
    log = " ".join(r["j"] or "" for r in db_rows(app, "SELECT after_json AS j FROM event_log WHERE entity IN ('prep_point', 'prep_speech', 'class_run_speaker')"))
    assert "My own words about zoos" not in log and "grandmother" not in log and "Lovely voice" not in log


def test_typed_names_that_never_matched_the_roster_are_cleared_after_a_year(coord, app):
    from app.retention import purge
    coord.post("/debating/runs", {"kind": "speeches", "names": "Quinn\nRowan"})
    run = db_one(app, "SELECT * FROM class_run ORDER BY id DESC LIMIT 1")
    _, six = _debate(coord, app)
    linked = db_one(app, "SELECT run_id FROM class_run_speaker WHERE student_id IS NOT NULL ORDER BY id DESC LIMIT 1")["run_id"]
    old = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat(timespec="seconds")
    with app.state.db.write(SYSTEM) as w:
        w.conn.execute("UPDATE class_run SET created_at = ?", (old,))
    report = purge(app.state.db)
    assert report["run_names_cleared"] == 2
    assert [s["name"] for s in db_rows(app, "SELECT name FROM class_run_speaker WHERE run_id = ? ORDER BY position", (run["id"],))] == \
        ["Speaker 1", "Speaker 2"]
    assert all(s["name"] != "Speaker 1" for s in db_rows(app, "SELECT name FROM class_run_speaker WHERE run_id = ?", (linked,)))
