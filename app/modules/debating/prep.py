"""The prep studio (D-076, D-077): a student's own cases, rebuttals and speech drafts, and the scoring on them.

Two kinds of score are kept apart and labelled: the structure check (counted here: which parts have words in them,
nothing about quality) and rubric scores for quality, given by the student and by the teacher.
"""
from __future__ import annotations

import json
import random

from app.db import Writer, one, rows
from app.errors import UserError
from app.util import now_iso
from app.web.auth import can_run_class

SIDES = {"aff": "Affirmative", "neg": "Negative"}
OTHER = {"aff": "neg", "neg": "aff"}
# (key, label, prompt, words needed for the structure check)
ARG_PARTS = [("claim", "Claim", "Your point in one sentence a listener could repeat.", 4),
             ("reason", "Reasoning", "Why it's true: the steps of logic, one after another.", 8),
             ("evidence", "Example or evidence", "A real example, case or comparison. Say where it comes from.", 6),
             ("impact", "Impact", "Why it matters, and how it proves the motion.", 6)]
REB_PARTS = [("they_say", "They say", "Their argument, summarised fairly, at its strongest.", 4),
             ("flaw", "But", "What's wrong with it: a flaw, a missing step or a false assumption.", 6),
             ("support", "Because", "Your reason or example.", 6),
             ("impact", "So", "Why winning this point matters for your side.", 5)]
PARTS = {"argument": ARG_PARTS, "rebuttal": REB_PARTS}
RUBRIC = {"argument": "argument_written", "rebuttal": "rebuttal_written"}
MAX_POINTS = {"argument": 6, "rebuttal": 20}
PART_MAX = 1200
WPM = 130          # speaking rate for the estimated time (stated on the page)


def words(text: str) -> int:
    return len((text or "").split())


def structure(kind: str, parts: dict) -> dict:
    """The structure check: which parts have at least a few words. Says nothing about how good they are."""
    spec = PARTS[kind]
    done = [k for k, _, _, n in spec if words(parts.get(k, "")) >= n]
    return {"done": len(done), "total": len(spec), "complete": len(done) == len(spec),
            "missing": [label for k, label, _, _ in spec if k not in done]}


def rubric(conn, kind: str) -> dict | None:
    r = one(conn, "SELECT * FROM rubric WHERE code = ? AND deleted_at IS NULL", (RUBRIC[kind],))
    if not r:
        return None
    r["criteria"] = rows(conn, "SELECT * FROM rubric_criterion WHERE rubric_id = ? AND deleted_at IS NULL ORDER BY position", (r["id"],))
    for c in r["criteria"]:
        c["levels"] = rows(conn, "SELECT level, descriptor FROM rubric_descriptor WHERE criterion_id = ? AND deleted_at IS NULL "
                                 "ORDER BY level", (c["id"],))
    return r


def mean_score(scores: dict, rub: dict | None) -> float | None:
    """The mean of a point's rubric scores, as a fraction of each criterion's maximum (so 1.0 is full marks)."""
    if not rub:
        return None
    vals = []
    for c in rub["criteria"]:
        v = scores.get(c["code"])
        if v not in (None, ""):
            vals.append(float(v) / float(c["max_score"]))
    return sum(vals) / len(vals) if vals else None


# ---------- cases ----------

def can_see_student(conn, actor, student_id: int) -> bool:
    if actor is None:
        return False
    if actor.kind == "student":
        return actor.id == student_id
    st = one(conn, "SELECT class_id FROM student WHERE id = ?", (student_id,))
    return bool(st) and can_run_class(conn, actor, st["class_id"])


def get_case(conn, actor, case_id: int) -> dict:
    c = one(conn, "SELECT * FROM prep_case WHERE id = ? AND deleted_at IS NULL", (case_id,))
    if not c or not can_see_student(conn, actor, c["student_id"]):
        raise UserError("That case isn't yours to open.", 404 if not c else 403)
    return c


def create_case(w: Writer, student_id: int, motion_id: int | None, motion_text: str, side: str) -> int:
    if side not in SIDES:
        raise UserError("Choose a side: Affirmative or Negative.")
    if motion_id:
        m = one(w.conn, "SELECT * FROM motion_bank WHERE id = ? AND deleted_at IS NULL", (motion_id,))
        if not m:
            raise UserError("That motion isn't in the motion bank.")
        motion_text = m["motion"]
    motion_text = " ".join((motion_text or "").split())[:300]
    if len(motion_text) < 8:
        raise UserError("Choose a motion from the list, or type your own.")
    if not motion_id:
        m = one(w.conn, "SELECT id FROM motion_bank WHERE motion = ? AND deleted_at IS NULL", (motion_text,))
        motion_id = m["id"] if m else None
    t = now_iso()
    return w.insert("prep_case", {"student_id": student_id, "motion_id": motion_id, "motion": motion_text, "side": side,
                                  "created_at": t, "updated_at": t})


def _parts(form, kind: str) -> dict:
    out = {}
    for k, label, _, _ in PARTS[kind]:
        v = (form.get(f"part_{k}") or "").strip()
        if len(v) > PART_MAX:
            raise UserError(f"{label} is too long: keep it under {PART_MAX} characters. Speeches need short points.")
        out[k] = v
    return out


def _scores(form, rub: dict | None, prefix: str) -> dict:
    out = {}
    for c in (rub or {}).get("criteria", []):
        raw = form.get(f"{prefix}{c['code']}")
        if raw in (None, ""):
            continue
        try:
            v = float(raw)
        except ValueError:
            raise UserError(f"{c['name']}: choose a level.")
        if not c["min_score"] <= v <= c["max_score"]:
            raise UserError(f"{c['name']}: choose a level between {c['min_score']:g} and {c['max_score']:g}.")
        out[c["code"]] = v
    return out


SPEECH_MAX = 8000


def save_header(w: Writer, case: dict, form) -> None:
    """The team line and definition, or the written-out speech (D-087): each form sends only its own fields."""
    changes = {"updated_at": now_iso()}
    if "team_line" in form or "definition" in form:
        changes.update({"definition": (form.get("definition") or "").strip()[:PART_MAX], "team_line": (form.get("team_line") or "").strip()[:300]})
    if "speech_text" in form:
        text = (form.get("speech_text") or "").replace("\r\n", "\n").strip()
        if len(text) > SPEECH_MAX:
            raise UserError(f"Keep the speech under {SPEECH_MAX:,} characters.")
        changes["speech_text"] = text
    w.update("prep_case", case["id"], changes)


def save_point(w: Writer, case: dict, form) -> int:
    kind = form.get("kind")
    if kind not in PARTS:
        raise UserError("Unknown kind of point.")
    parts = _parts(form, kind)
    scores = _scores(form, rubric(w.conn, kind), "self_")
    speaker = form.get("speaker")
    speaker = int(speaker) if speaker in ("1", "2", "3", "4") else None
    pid = form.get("point_id")
    t = now_iso()
    if pid:
        p = one(w.conn, "SELECT * FROM prep_point WHERE id = ? AND case_id = ? AND deleted_at IS NULL", (int(pid), case["id"]))
        if not p:
            raise UserError("That point isn't in this case.", 404)
        w.update("prep_point", p["id"], {"parts": json.dumps(parts), "self_scores": json.dumps(scores), "speaker": speaker, "updated_at": t})
        out = p["id"]
    else:
        n = one(w.conn, "SELECT COUNT(*) AS n, COALESCE(MAX(position), 0) AS top FROM prep_point WHERE case_id = ? AND kind = ? "
                        "AND deleted_at IS NULL", (case["id"], kind))
        if n["n"] >= MAX_POINTS[kind]:
            raise UserError(f"A case holds up to {MAX_POINTS[kind]} {kind}s. Strengthen the ones you have, or remove one.")
        src = form.get("source_argument_id")
        src_id = None
        if src:
            a = one(w.conn, "SELECT * FROM motion_argument WHERE id = ? AND deleted_at IS NULL", (int(src),))
            if not a or a["motion_id"] != case["motion_id"] or a["side"] != OTHER[case["side"]]:
                raise UserError("That argument isn't one of the other side's for this motion.")
            if one(w.conn, "SELECT 1 FROM prep_point WHERE case_id = ? AND source_argument_id = ? AND deleted_at IS NULL", (case["id"], a["id"])):
                raise UserError("You've already written a rebuttal to that argument. Edit it instead.")
            src_id = a["id"]
        if not any(parts.values()):
            raise UserError("Write at least one part before saving.")
        out = w.insert("prep_point", {"case_id": case["id"], "kind": kind, "position": n["top"] + 1, "speaker": speaker,
                                      "source_argument_id": src_id, "parts": json.dumps(parts), "self_scores": json.dumps(scores),
                                      "updated_at": t})
    w.update("prep_case", case["id"], {"updated_at": t})
    return out


def delete_point(w: Writer, case: dict, point_id: int) -> None:
    p = one(w.conn, "SELECT id FROM prep_point WHERE id = ? AND case_id = ? AND deleted_at IS NULL", (point_id, case["id"]))
    if not p:
        raise UserError("That point isn't in this case.", 404)
    w.soft_delete("prep_point", p["id"])


def staff_score(w: Writer, case: dict, form) -> None:
    for p in rows(w.conn, "SELECT * FROM prep_point WHERE case_id = ? AND deleted_at IS NULL", (case["id"],)):
        scores = _scores(form, rubric(w.conn, p["kind"]), f"st_{p['id']}_")
        w.update("prep_point", p["id"], {"staff_scores": json.dumps(scores)})
    w.update("prep_case", case["id"], {"staff_comment": (form.get("staff_comment") or "").strip()[:2000]})


def case_view(conn, case: dict) -> dict:
    rubs = {k: rubric(conn, k) for k in PARTS}
    pts = rows(conn, "SELECT * FROM prep_point WHERE case_id = ? AND deleted_at IS NULL ORDER BY kind, position", (case["id"],))
    for p in pts:
        p["parts_d"] = json.loads(p["parts"] or "{}")
        p["self_d"] = json.loads(p["self_scores"] or "{}")
        p["staff_d"] = json.loads(p["staff_scores"] or "{}")
        p["check"] = structure(p["kind"], p["parts_d"])
        p["self_mean"] = mean_score(p["self_d"], rubs[p["kind"]])
        p["staff_mean"] = mean_score(p["staff_d"], rubs[p["kind"]])
    arguments = [p for p in pts if p["kind"] == "argument"]
    rebuttals = [p for p in pts if p["kind"] == "rebuttal"]
    by_source = {p["source_argument_id"]: p for p in rebuttals if p["source_argument_id"]}
    opposition = rows(conn, "SELECT * FROM motion_argument WHERE motion_id = ? AND side = ? AND deleted_at IS NULL ORDER BY position",
                      (case["motion_id"] or 0, OTHER[case["side"]]))
    for a in opposition:
        a["rebuttal"] = by_source.get(a["id"])
    custom = [p for p in rebuttals if not p["source_argument_id"]]
    summary = summarise(case, arguments, rebuttals, opposition)
    return {"case": case, "side_label": SIDES[case["side"]], "other_label": SIDES[OTHER[case["side"]]], "arguments": arguments,
            "opposition": opposition, "custom": custom, "rubrics": rubs, "arg_parts": ARG_PARTS, "reb_parts": REB_PARTS,
            "summary": summary, "max_points": MAX_POINTS}


def summarise(case: dict, arguments: list, rebuttals: list, opposition: list) -> dict:
    to_rebut = len(opposition) + sum(1 for p in rebuttals if not p["source_argument_id"])
    means = lambda key: [p[key] for p in arguments + rebuttals if p[key] is not None]
    sm, tm = means("self_mean"), means("staff_mean")
    return {"arguments_done": sum(1 for p in arguments if p["check"]["complete"]), "arguments": len(arguments),
            "rebuttals_done": sum(1 for p in rebuttals if p["check"]["complete"]), "to_rebut": to_rebut,
            "team_line": words(case["team_line"]) >= 5, "definition": words(case["definition"]) >= 8,
            "self": sum(sm) / len(sm) if sm else None, "staff": sum(tm) / len(tm) if tm else None}


def cases_for(conn, student_id: int) -> list[dict]:
    out = rows(conn, "SELECT * FROM prep_case WHERE student_id = ? AND deleted_at IS NULL ORDER BY updated_at DESC", (student_id,))
    for c in out:
        v = case_view(conn, c)
        c["summary"] = v["summary"]
        c["side_label"] = SIDES[c["side"]]
    return out


# ---------- speech drafts ----------

def templates(conn, kind: str | None = None) -> list[dict]:
    ts = rows(conn, "SELECT * FROM speech_template WHERE deleted_at IS NULL" + (" AND kind = ?" if kind else "") + " ORDER BY position, id",
              (kind,) if kind else ())
    for t in ts:
        try:
            t["sections_l"] = json.loads(t["sections"] or "[]")
        except ValueError:
            t["sections_l"] = []
    return ts


def get_speech(conn, actor, speech_id: int) -> dict:
    s = one(conn, "SELECT * FROM prep_speech WHERE id = ? AND deleted_at IS NULL", (speech_id,))
    if not s or not can_see_student(conn, actor, s["student_id"]):
        raise UserError("That speech isn't yours to open.", 404 if not s else 403)
    return s


def create_speech(w: Writer, student_id: int, template_code: str, title: str) -> int:
    t = one(w.conn, "SELECT * FROM speech_template WHERE code = ? AND kind = 'prepared' AND deleted_at IS NULL", (template_code,))
    if not t:
        raise UserError("Choose a speech template.")
    title = " ".join((title or "").split())[:120] or t["name"]
    n = now_iso()
    return w.insert("prep_speech", {"student_id": student_id, "template_code": t["code"], "title": title, "sections": "{}",
                                    "target_seconds": 180, "created_at": n, "updated_at": n})


def save_speech(w: Writer, sp: dict, form) -> None:
    view = speech_view(w.conn, sp)
    sections = {}
    for sec in view["sections"]:
        v = (form.get(f"sec_{sec['key']}") or "").strip()
        limit = SPEECH_MAX if len(view["sections"]) == 1 else 4000       # "Write it your way" is one box for the whole speech
        if len(v) > limit:
            raise UserError(f"{sec['label']} is too long (over {limit:,} characters).")
        sections[sec["key"]] = v
    try:
        target = max(30, min(int(form.get("target_seconds") or sp["target_seconds"]), 900))
    except ValueError:
        target = sp["target_seconds"]
    w.update("prep_speech", sp["id"], {"sections": json.dumps(sections), "target_seconds": target,
                                       "title": " ".join((form.get("title") or sp["title"]).split())[:120] or sp["title"],
                                       "updated_at": now_iso()})


def speech_view(conn, sp: dict) -> dict:
    t = one(conn, "SELECT * FROM speech_template WHERE code = ?", (sp["template_code"],))
    secs = json.loads(t["sections"] or "[]") if t else []
    text = json.loads(sp["sections"] or "{}")
    # Sections a template no longer has stay visible, so nothing a student wrote is hidden by a template edit.
    keys = {s["key"] for s in secs}
    secs = secs + [{"key": k, "label": k.replace("_", " ").capitalize(), "prompt": ""} for k in text if k not in keys]
    for s in secs:
        s["text"] = text.get(s["key"], "")
        s["words"] = words(s["text"])
    total = sum(s["words"] for s in secs)
    return {"speech": sp, "template": t, "sections": secs, "words": total, "seconds": round(total / WPM * 60), "wpm": WPM}


def speeches_for(conn, student_id: int) -> list[dict]:
    out = rows(conn, "SELECT * FROM prep_speech WHERE student_id = ? AND deleted_at IS NULL ORDER BY updated_at DESC", (student_id,))
    for s in out:
        v = speech_view(conn, s)
        s["words"], s["seconds"] = v["words"], v["seconds"]
    return out


# ---------- practice material ----------

def practice_material(conn, student_id: int, level: str | None = None) -> dict:
    """Topics for the practice page: impromptu topics, the student's own speech drafts, and a sample of the
    other side's likely arguments for rebuttal drills."""
    imp = [{"text": t["topic"], "level": t["level"]} for t in rows(conn, "SELECT topic, level FROM impromptu_topic WHERE deleted_at IS NULL")]
    own = [{"text": s["title"], "seconds": s["target_seconds"], "id": s["id"]} for s in speeches_for(conn, student_id)]
    args = rows(conn, "SELECT a.argument, a.side, m.motion, m.level FROM motion_argument a JOIN motion_bank m ON m.id = a.motion_id "
                      "WHERE a.deleted_at IS NULL AND m.deleted_at IS NULL")
    random.shuffle(args)
    drill = [{"text": a["argument"], "level": a["level"],
              "context": f"Motion: {a['motion']}. The {SIDES[a['side']]} might argue this; you rebut it."} for a in args[:60]]
    return {"impromptu": imp, "prepared": own, "rebuttal": drill}


def class_overview(conn, class_id: int) -> list[dict]:
    students = rows(conn, "SELECT id, first_name, last_initial FROM student WHERE class_id = ? AND deleted_at IS NULL AND active = 1 "
                          "ORDER BY first_name, last_initial", (class_id,))
    return overview(conn, students)


def overview(conn, students: list[dict]) -> list[dict]:
    """Each student's cases (with how much of the speech is written), speeches, practice and when they last saved."""
    for s in students:
        s["cases"] = cases_for(conn, s["id"])
        s["speeches"] = speeches_for(conn, s["id"])
        s["practice"] = one(conn, "SELECT COUNT(*) AS n FROM practice_speech WHERE student_id = ? AND deleted_at IS NULL", (s["id"],))["n"]
        for c in s["cases"]:
            c["speech_words"] = words(c["speech_text"])
        s["last_saved"] = max([x["updated_at"] for x in s["cases"] + s["speeches"]], default=None)
    return students
