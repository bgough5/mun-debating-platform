"""The classroom runner (D-075): a class debate or a speaking round, run by a teacher with one timer and projected.

A run's order of speakers is computed from its settings, never stored: change the number of speakers or switch
reply speeches on and the order follows. The timer's state lives on the run, so a refresh, a second screen or the
projector all show the same thing.
"""
from __future__ import annotations

import json
import random
import re
import secrets

from app.db import Writer, one, rows, scalar
from app.errors import UserError
from app.util import display_name, now, now_iso
from app.web.auth import can_run_class

SIDES = {"aff": "Affirmative", "neg": "Negative"}
ORDINAL = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}
RUBRIC = {"debate": "debate_speaker", "speeches": "speech_practice"}
MAX_SPEAKERS = 30
NAME_MAX = 24
_BAD_NAME = re.compile(r"[0-9@/\\<>{}:;=_|#$%^&*+~`\"]")


def ch(run_id: int) -> str:
    return f"run:{run_id}"


def clean_name(raw: str) -> str:
    """First names only, plus a last initial if two students share one (D-075). Rejects what looks like an email,
    a number or a full name, so nothing more than a first name is stored by accident."""
    name = " ".join((raw or "").split())
    if not name:
        return ""
    if len(name) > NAME_MAX or _BAD_NAME.search(name) or len(name.split(" ")) > 3:
        raise UserError(f"Use first names only, with a last initial if two students share a name (for example “Mia K”): "
                        f"“{name[:30]}” can't be used.")
    return name


def run_access(conn, actor, run: dict) -> bool:
    """Who may run a class run: the coordinator, the teacher who made it, and staff assigned to its class."""
    if actor is None or not actor.is_staff:
        return False
    if actor.is_coordinator:
        return True
    return run["staff_id"] == actor.id or (run["class_id"] is not None and can_run_class(conn, actor, run["class_id"]))


def get_run(conn, actor, run_id: int) -> dict:
    r = one(conn, "SELECT * FROM class_run WHERE id = ? AND deleted_at IS NULL", (run_id,))
    if not r:
        raise UserError("That class run doesn't exist.", 404)
    if not run_access(conn, actor, r):
        raise UserError("Only the teacher running this class can open it.", 403)
    return r


def speakers(conn, run_id: int) -> list[dict]:
    return rows(conn, "SELECT * FROM class_run_speaker WHERE run_id = ? AND deleted_at IS NULL ORDER BY side, position", (run_id,))


def roster(conn, class_id: int | None) -> list[dict]:
    if not class_id:
        return []
    out = rows(conn, "SELECT id, first_name, last_initial FROM student WHERE class_id = ? AND deleted_at IS NULL AND active = 1 "
                     "ORDER BY first_name, last_initial", (class_id,))
    for s in out:
        s["name"] = display_name(s["first_name"], s["last_initial"])
    return out


def match_student(students: list[dict], name: str) -> int | None:
    """The roster student a typed name refers to: an exact display name ("Mia K."), or a first name that only one
    student in the class has."""
    key = name.lower().rstrip(".")
    exact = [s for s in students if s["name"].lower().rstrip(".") == key]
    if len(exact) == 1:
        return exact[0]["id"]
    firsts = [s for s in students if s["first_name"].lower() == key]
    return firsts[0]["id"] if len(firsts) == 1 else None


# ---------- the run order ----------

def steps(run: dict, spk: list[dict]) -> list[dict]:
    """The run of show. Debates: preparation, then Aff 1, Neg 1, Aff 2 ... then the Negative reply before the
    Affirmative reply (Australian schools). Speaking rounds: each speaker in turn, with thinking time first when
    the topics are impromptu."""
    out = []
    by_slot = {(s["side"], s["position"]): s for s in spk}
    if run["kind"] == "debate":
        if run["prep_seconds"]:
            out.append({"key": "prep", "kind": "prep", "label": "Preparation", "who": "", "seconds": run["prep_seconds"],
                        "speaker": None, "warn": 60 if run["prep_seconds"] >= 300 else 0})
        for p in range(1, run["speakers_per_side"] + 1):
            for side in ("aff", "neg"):
                s = by_slot.get((side, p))
                out.append({"key": f"{side}{p}", "kind": "speech", "side": side,
                            "label": f"{run[side + '_name']}: {ORDINAL[p]} speaker", "who": s["name"] if s else "",
                            "seconds": run["speech_seconds"], "speaker": s, "warn": _warn(run["warning_seconds"], run["speech_seconds"])})
        if run["reply"]:
            for side in ("neg", "aff"):
                out.append({"key": f"{side}R", "kind": "reply", "side": side, "label": f"{run[side + '_name']}: reply",
                            "who": "", "seconds": run["reply_seconds"], "speaker": None,
                            "warn": _warn(min(run["warning_seconds"], 30), run["reply_seconds"])})
    else:
        for s in sorted(spk, key=lambda x: x["position"]):
            if run["topic_mode"] == "impromptu" and run["think_seconds"]:
                out.append({"key": f"t{s['position']}", "kind": "think", "label": f"{s['name']}: thinking time", "who": s["name"],
                            "seconds": run["think_seconds"], "speaker": s, "warn": 10 if run["think_seconds"] > 20 else 0})
            out.append({"key": f"s{s['position']}", "kind": "speech", "label": s["name"], "who": s["name"],
                        "seconds": run["speech_seconds"], "speaker": s, "warn": _warn(run["warning_seconds"], run["speech_seconds"])})
    for i, st in enumerate(out):
        st["index"] = i
    return out


def _warn(warning: int, seconds: int) -> int:
    """The warning bell rings this many seconds before time; never at or before the start."""
    return warning if 0 < warning < seconds else 0


def remaining(run: dict, step: dict | None, at: float | None = None) -> float:
    if step is None:
        return 0.0
    at = now() if at is None else at
    elapsed = run["timer_elapsed"] + ((at - run["timer_started_at"]) if run["timer_state"] == "running" and run["timer_started_at"] is not None else 0)
    return step["seconds"] + run["timer_extra"] - elapsed


def elapsed(run: dict, at: float | None = None) -> float:
    at = now() if at is None else at
    return run["timer_elapsed"] + ((at - run["timer_started_at"]) if run["timer_state"] == "running" and run["timer_started_at"] is not None else 0)


def timing(seconds: float | None, target: int) -> str:
    """How a speech's length compares with its time: short (under three quarters), over (more than 15 s past), or on time."""
    if seconds is None:
        return ""
    if seconds > target + 15:
        return "over"
    if seconds < target * 0.75:
        return "short"
    return "on time"


def view(conn, run: dict) -> dict:
    """Everything the teacher's page and the projector show."""
    spk = speakers(conn, run["id"])
    st = steps(run, spk)
    cur = st[run["step"]] if 0 <= run["step"] < len(st) else None
    times = json.loads(run["step_seconds"] or "{}")
    t0 = now()
    rem = remaining(run, cur, t0)
    # Impromptu topics are hidden until that speaker's turn (their thinking time) comes round.
    revealed = {s["key"] for s in st[: run["step"] + 1]} if cur else {s["key"] for s in st}
    for s in spk:
        s["seconds"] = times.get(f"{s['side']}{s['position']}" if run["kind"] == "debate" else f"s{s['position']}")
        s["timing"] = timing(s["seconds"], run["speech_seconds"])
        s["scores_d"] = json.loads(s["scores"] or "{}")
        s["total"] = sum(float(v) for v in s["scores_d"].values() if v not in ("", None))
        s["topic_shown"] = run["kind"] == "debate" or run["topic_mode"] == "prepared" or \
            f"t{s['position']}" in revealed or f"s{s['position']}" in revealed
    rub = one(conn, "SELECT * FROM rubric WHERE code = ? AND deleted_at IS NULL", (RUBRIC[run["kind"]],))
    crit = rows(conn, "SELECT * FROM rubric_criterion WHERE rubric_id = ? AND deleted_at IS NULL ORDER BY position",
                (rub["id"] if rub else 0,))
    teams = {}
    if run["kind"] == "debate":
        for side in ("aff", "neg"):
            members = [s for s in spk if s["side"] == side]
            teams[side] = {"name": run[side + "_name"], "speakers": members,
                           "total": sum(s["total"] for s in members), "scored": any(s["scores_d"] for s in members)}
    nxt = st[run["step"] + 1] if cur and run["step"] + 1 < len(st) else None
    phase = "idle"
    if cur and run["timer_state"] != "idle" or (cur and run["timer_elapsed"] > 0):
        phase = "over" if rem <= 0 else ("warn" if cur["warn"] and rem <= cur["warn"] else "go")
    return {"run": run, "speakers": spk, "steps": st, "cur": cur, "next": nxt, "remaining": rem, "phase": phase,
            "server_now": t0, "times": times, "rubric": rub, "criteria": crit, "teams": teams,
            "upcoming": [s for s in st[run["step"] + 1: run["step"] + 4] if s["kind"] != "think"] if cur else [],
            "finished": run["status"] == "finished", "view_seq": scalar(conn, "SELECT MAX(seq) FROM event_log") or 0}


# ---------- create and edit ----------

def _settings(form: dict, kind: str) -> dict:
    def num(key, default, lo, hi):
        try:
            v = int(float(form.get(key) or default))
        except (TypeError, ValueError):
            v = default
        return max(lo, min(v, hi))
    out = {"title": (form.get("title") or "").strip()[:80], "motion": (form.get("motion") or "").strip()[:300],
           "speech_seconds": num("speech_seconds", 240 if kind == "debate" else 120, 15, 1200),
           "warning_seconds": num("warning_seconds", 60, 0, 300),
           "level": form.get("level") if form.get("level") in ("junior", "middle", "senior") else "middle"}
    if kind == "debate":
        out.update({"speakers_per_side": num("speakers_per_side", 3, 1, 4), "reply": 1 if form.get("reply") else 0,
                    "reply_seconds": num("reply_seconds", 120, 30, 600), "prep_seconds": num("prep_minutes", 0, 0, 120) * 60,
                    "aff_name": (form.get("aff_name") or "").strip()[:40] or "Affirmative",
                    "neg_name": (form.get("neg_name") or "").strip()[:40] or "Negative"})
    else:
        out.update({"topic_mode": "impromptu" if form.get("topic_mode") == "impromptu" else "prepared",
                    "think_seconds": num("think_seconds", 60, 0, 600)})
    return out


def _slots(form: dict, kind: str, per_side: int) -> list[tuple[str, int, str, str]]:
    """(side, position, name, topic) from the form, validated. Debates: aff_1..aff_4 and neg_1..neg_4; speaking
    rounds: one name per line, optionally followed by " - topic"."""
    out = []
    if kind == "debate":
        for side in ("aff", "neg"):
            for p in range(1, per_side + 1):
                out.append((side, p, clean_name(form.get(f"{side}_{p}") or ""), ""))
    else:
        lines = [x.strip() for x in (form.get("names") or "").splitlines() if x.strip()]
        if len(lines) > MAX_SPEAKERS:
            raise UserError(f"A speaking round holds up to {MAX_SPEAKERS} speakers.")
        for p, line in enumerate(lines, 1):
            name, _, topic = line.partition(" - ")
            out.append(("", p, clean_name(name), topic.strip()[:200]))
        if not out:
            raise UserError("Add at least one speaker: one first name per line.")
    return out


def create_run(w: Writer, kind: str, class_id: int | None, form: dict) -> int:
    if kind not in ("debate", "speeches"):
        raise UserError("Choose a class debate or a speaking round.")
    if class_id is not None and not can_run_class(w.conn, w.actor, class_id):
        raise UserError("You aren't assigned to that class.", 403)
    st = _settings(form, kind)
    slots = _slots(form, kind, st.get("speakers_per_side", 3))
    if not st["title"]:
        st["title"] = (st["motion"][:60] if kind == "debate" and st["motion"] else
                       ("Class debate" if kind == "debate" else "Speaking round"))
    rid = w.insert("class_run", {"kind": kind, "class_id": class_id, "staff_id": w.actor.id if w.actor.kind == "staff" else None,
                                 "projector_token": secrets.token_urlsafe(12), "created_at": now_iso(), **st})
    _write_slots(w, rid, class_id, slots)
    return rid


def update_run(w: Writer, run: dict, form: dict) -> None:
    st = _settings(form, run["kind"])
    st["title"] = st["title"] or run["title"]
    slots = _slots(form, run["kind"], st.get("speakers_per_side", 3))
    w.update("class_run", run["id"], st, ch(run["id"]), action="edit")
    _write_slots(w, run["id"], run["class_id"], slots)
    fresh = one(w.conn, "SELECT * FROM class_run WHERE id = ?", (run["id"],))
    if fresh["step"] >= len(steps(fresh, speakers(w.conn, run["id"]))):
        w.update("class_run", run["id"], {"step": 0, "timer_state": "idle", "timer_elapsed": 0, "timer_extra": 0,
                                          "timer_started_at": None}, ch(run["id"]), action="restart")


def _write_slots(w: Writer, rid: int, class_id: int | None, slots) -> None:
    """Keep each speaker row (and its scores) when the slot's name is unchanged; rename, add or remove the rest."""
    students = roster(w.conn, class_id)
    have = {(s["side"], s["position"]): s for s in speakers(w.conn, rid)}
    keep = set()
    for side, pos, name, topic in slots:
        sid = match_student(students, name) if name else None
        label = name or (f"Speaker {pos}" if not side else "")
        old = have.get((side, pos))
        keep.add((side, pos))
        if old:
            changes = {"name": label, "student_id": sid}
            if topic or old["name"] != label:
                changes["topic"] = topic
            if old["name"] != label:
                changes.update({"scores": "{}", "comment": ""})
            w.update("class_run_speaker", old["id"], changes, ch(rid))
        else:
            w.insert("class_run_speaker", {"run_id": rid, "side": side, "position": pos, "name": label,
                                           "student_id": sid, "topic": topic}, ch(rid))
    for slot, old in have.items():
        if slot not in keep:
            w.soft_delete("class_run_speaker", old["id"], ch(rid))


# ---------- running it ----------

def _draw_topic(conn, run: dict, used: set[str]) -> str:
    topics = [t for (t,) in conn.execute("SELECT topic FROM impromptu_topic WHERE deleted_at IS NULL AND level IN (?, 'any')",
                                         (run["level"],)) if t not in used]
    return random.choice(topics) if topics else ""


def act(w: Writer, run: dict, action: str, arg: int | None = None) -> None:
    rid, c = run["id"], ch(run["id"])
    spk = speakers(w.conn, rid)
    st = steps(run, spk)
    if action == "start":
        if not st:
            raise UserError("Add speakers first.")
        if run["timer_state"] != "running":
            w.update("class_run", rid, {"timer_state": "running", "timer_started_at": now(),
                                        "status": "running" if run["status"] == "ready" else run["status"]}, c, action="timer_start")
            # The first speaker's impromptu topic is drawn when their turn starts, like everyone else's.
            cur = st[run["step"]] if 0 <= run["step"] < len(st) else None
            if run["kind"] == "speeches" and run["topic_mode"] == "impromptu" and cur and cur["speaker"] and not cur["speaker"]["topic"]:
                w.update("class_run_speaker", cur["speaker"]["id"],
                         {"topic": _draw_topic(w.conn, run, {s["topic"] for s in spk if s["topic"]})}, c, action="topic_drawn")
    elif action == "pause":
        if run["timer_state"] == "running":
            w.update("class_run", rid, {"timer_state": "paused", "timer_elapsed": elapsed(run), "timer_started_at": None}, c,
                     action="timer_pause")
    elif action == "toggle":
        act(w, run, "pause" if run["timer_state"] == "running" else "start")
    elif action == "reset":
        w.update("class_run", rid, {"timer_state": "idle", "timer_elapsed": 0, "timer_extra": 0, "timer_started_at": None}, c,
                 action="timer_reset")
    elif action == "add30":
        w.update("class_run", rid, {"timer_extra": run["timer_extra"] + 30}, c, action="timer_extend")
    elif action in ("next", "prev", "goto"):
        target = {"next": run["step"] + 1, "prev": run["step"] - 1}.get(action, arg if arg is not None else run["step"])
        if target < 0:
            return
        times = json.loads(run["step_seconds"] or "{}")
        cur = st[run["step"]] if 0 <= run["step"] < len(st) else None
        spent = elapsed(run)
        if cur and spent >= 1:
            times[cur["key"]] = round(spent, 1)
        changes = {"step_seconds": json.dumps(times), "timer_state": "idle", "timer_elapsed": 0, "timer_extra": 0,
                   "timer_started_at": None}
        if target >= len(st):
            changes.update({"status": "finished", "step": len(st)})
            w.update("class_run", rid, changes, c, action="finish")
            return
        changes.update({"step": target, "status": "running" if run["status"] != "running" else run["status"]})
        w.update("class_run", rid, changes, c, action="step")
        new = st[target]
        if run["kind"] == "speeches" and run["topic_mode"] == "impromptu" and new["speaker"] and not new["speaker"]["topic"]:
            used = {s["topic"] for s in spk if s["topic"]}
            w.update("class_run_speaker", new["speaker"]["id"], {"topic": _draw_topic(w.conn, run, used)}, c, action="topic_drawn")
    elif action == "finish":
        act(w, run, "goto", len(st))
    elif action == "reopen":
        w.update("class_run", rid, {"status": "running", "step": max(0, len(st) - 1)}, c, action="reopen")
    elif action == "redraw":
        s = next((x for x in spk if x["id"] == arg), None)
        if not s:
            raise UserError("That speaker isn't in this run.", 404)
        used = {x["topic"] for x in spk if x["topic"]}
        w.update("class_run_speaker", s["id"], {"topic": _draw_topic(w.conn, run, used)}, c, action="topic_drawn")
    else:
        raise UserError("Unknown action.")


def save_scores(w: Writer, run: dict, form: dict) -> None:
    rub = one(w.conn, "SELECT id FROM rubric WHERE code = ?", (RUBRIC[run["kind"]],))
    crit = rows(w.conn, "SELECT * FROM rubric_criterion WHERE rubric_id = ? AND deleted_at IS NULL", (rub["id"] if rub else 0,))
    for s in speakers(w.conn, run["id"]):
        scores = {}
        for cr in crit:
            raw = form.get(f"sc_{s['id']}_{cr['id']}")
            if raw in (None, ""):
                continue
            try:
                v = float(raw)
            except ValueError:
                raise UserError(f"{cr['name']} for {s['name']} must be a number.")
            if not cr["min_score"] <= v <= cr["max_score"]:
                raise UserError(f"{cr['name']} for {s['name']} must be between {cr['min_score']:g} and {cr['max_score']:g}.")
            scores[str(cr["id"])] = v
        comment = (form.get(f"cm_{s['id']}") or "").strip()[:1000]
        w.update("class_run_speaker", s["id"], {"scores": json.dumps(scores), "comment": comment}, ch(run["id"]), action="score")
    winner = form.get("winner") if form.get("winner") in ("aff", "neg") else ""
    w.update("class_run", run["id"], {"winner": winner if run["kind"] == "debate" else "",
                                      "comment": (form.get("comment") or "").strip()[:2000]}, ch(run["id"]), action="result")


def runs_for(conn, actor, limit: int = 30) -> list[dict]:
    rs = rows(conn, "SELECT r.*, c.name AS class_name, (SELECT COUNT(*) FROM class_run_speaker s WHERE s.run_id = r.id "
                    "AND s.deleted_at IS NULL) AS n_speakers FROM class_run r LEFT JOIN class c ON c.id = r.class_id "
                    "WHERE r.deleted_at IS NULL ORDER BY r.id DESC LIMIT 200")
    return [r for r in rs if run_access(conn, actor, r)][:limit]


def student_results(conn, student_id: int) -> list[dict]:
    """A student's own speeches in class runs: time, scores and the teacher's comment."""
    out = rows(conn, "SELECT s.*, r.kind, r.title, r.motion, r.speech_seconds, r.step_seconds, r.winner, r.created_at, "
                     "r.aff_name, r.neg_name, r.status FROM class_run_speaker s JOIN class_run r ON r.id = s.run_id "
                     "WHERE s.student_id = ? AND s.deleted_at IS NULL AND r.deleted_at IS NULL ORDER BY r.id DESC LIMIT 20",
                (student_id,))
    names = {c["id"]: c for c in rows(conn, "SELECT id, name, max_score FROM rubric_criterion")}
    for s in out:
        times = json.loads(s["step_seconds"] or "{}")
        s["seconds"] = times.get(f"{s['side']}{s['position']}" if s["kind"] == "debate" else f"s{s['position']}")
        s["timing"] = timing(s["seconds"], s["speech_seconds"])
        s["score_list"] = [(names[int(k)]["name"], v, names[int(k)]["max_score"]) for k, v in json.loads(s["scores"] or "{}").items()
                           if int(k) in names]
        s["result"] = ("won" if s["winner"] == s["side"] else "lost") if s["kind"] == "debate" and s["winner"] else ""
    return out


def count_runs(conn) -> int:
    return scalar(conn, "SELECT COUNT(*) FROM class_run WHERE deleted_at IS NULL") or 0
