"""Live session (chair tools, spec §3.4): speakers list, timers, motions, divisions, minutes.

All state lives in the database, so a chair whose browser closes simply
reopens the page and is back in control (CH-6). Every change is an event on
the channel `session:<id>`, which drives live updates and the minutes.
"""
from __future__ import annotations

import json
import math
import secrets

from app.db import Writer, one, rows, scalar
from app.engine.rules import VotingRule, tally
from app.errors import UserError
from app.util import display_name, now, now_iso

PARTICIPANT_TTL_S = 120     # a student counts toward the cap while seen in the last 2 minutes


def ch(session_id: int) -> str:
    return f"session:{session_id}"


def get_session(conn, sid: int) -> dict:
    s = one(conn, "SELECT ls.*, cm.name AS committee, cm.class_id, cm.voting_rule_id, cm.procedure_rule_set_id, cm.conference_id "
                  "FROM live_session ls JOIN committee cm ON cm.id = ls.committee_id WHERE ls.id = ?", (sid,))
    if not s:
        raise UserError("That session doesn't exist.", 404)
    return s


def _open_only(s: dict) -> None:
    if s["state"] == "closed":
        raise UserError("This session is closed. Open a new session to continue.", 409)


def open_session(w: Writer, committee_id: int) -> int:
    """Returns the committee's open session, creating one if there isn't one (chair reconnect)."""
    existing = scalar(w.conn, "SELECT id FROM live_session WHERE committee_id = ? AND state != 'closed' ORDER BY id DESC LIMIT 1",
                      (committee_id,))
    if existing:
        return existing
    com = one(w.conn, "SELECT cm.*, pr.speaking_time_default FROM committee cm LEFT JOIN procedure_rule_set pr "
                      "ON pr.id = cm.procedure_rule_set_id WHERE cm.id = ?", (committee_id,))
    if not com:
        raise UserError("That committee doesn't exist.", 404)
    sid = w.insert("live_session", {"committee_id": committee_id, "title": com["name"], "chair_label": w.actor.label,
                                    "projector_token": secrets.token_urlsafe(12), "created_at": now_iso(),
                                    "speaking_time_s": com["speaking_time_default"] or 90})
    w.log("live_session", sid, "opened", None, {"committee": com["name"]}, ch(sid))
    if com["class_id"]:
        w.touch(f"class:{com['class_id']}")      # students' pages show "Live now"
    return sid


def set_state(w: Writer, sid: int, state: str) -> None:
    if state not in ("open", "suspended", "closed"):
        raise UserError("Unknown session state.")
    changes = {"state": state}
    if state == "closed":
        changes["closed_at"] = now_iso()
        for t in rows(w.conn, "SELECT id FROM timer WHERE session_id = ? AND state IN ('running','paused')", (sid,)):
            w.update("timer", t["id"], {"state": "done"}, ch(sid))
    w.update("live_session", sid, changes, ch(sid), action=f"session_{state}")
    cls = scalar(w.conn, "SELECT cm.class_id FROM live_session ls JOIN committee cm ON cm.id = ls.committee_id WHERE ls.id = ?", (sid,))
    if cls:
        w.touch(f"class:{cls}")


def set_mode(w: Writer, sid: int, mode: str, topic: str = "") -> None:
    w.update("live_session", sid, {"mode": mode, "mode_topic": topic}, ch(sid), action="mode")


# ---------- participants and the 25-student cap (D-022) ----------

def active_participants(conn, sid: int) -> int:
    return scalar(conn, "SELECT COUNT(*) FROM session_participant WHERE session_id = ? AND last_seen > ?",
                  (sid, now() - PARTICIPANT_TTL_S))


def admit(w: Writer, sid: int, student_id: int, cap: int = 25) -> None:
    """Admit a student to a live session, or refuse if `cap` other students are already in it."""
    s = get_session(w.conn, sid)
    _open_only(s)
    p = one(w.conn, "SELECT * FROM session_participant WHERE session_id = ? AND student_id = ?", (sid, student_id))
    t = now()
    if p and t - p["last_seen"] < PARTICIPANT_TTL_S:
        w.conn.execute("UPDATE session_participant SET last_seen = ? WHERE id = ?", (t, p["id"]))
        return
    if active_participants(w.conn, sid) >= cap:
        raise UserError(f"This session is full: it already has {cap} students, the most a live session can hold. "
                        "Ask your teacher.", 409)
    if p:
        w.conn.execute("UPDATE session_participant SET last_seen = ? WHERE id = ?", (t, p["id"]))
    else:
        w.conn.execute("INSERT INTO session_participant (session_id, student_id, joined_at, last_seen) VALUES (?,?,?,?)",
                       (sid, student_id, now_iso(), t))
        w.log("session_participant", f"{sid}:{student_id}", "joined", None, {"student_id": student_id}, ch(sid))


def seen(conn, sid: int, student_id: int) -> None:
    conn.execute("UPDATE session_participant SET last_seen = ? WHERE session_id = ? AND student_id = ?", (now(), sid, student_id))


# ---------- speakers list ----------

def add_speaker(w: Writer, sid: int, delegation_id: int, student_id: int | None = None, list_kind: str = "general",
                amendment_id: int | None = None, side: str = "") -> int:
    s = get_session(w.conn, sid)
    _open_only(s)
    if list_kind not in ("general", "moderated"):
        raise UserError("Unknown speakers list.")
    d = one(w.conn, "SELECT * FROM delegation WHERE id = ? AND committee_id = ? AND deleted_at IS NULL", (delegation_id, s["committee_id"]))
    if not d:
        raise UserError("That delegation isn't in this committee.")
    if one(w.conn, "SELECT 1 FROM speakers_list_entry WHERE session_id = ? AND delegation_id = ? AND status = 'waiting' AND list_kind = ? "
                   "AND amendment_id IS ?", (sid, delegation_id, list_kind, amendment_id)):
        raise UserError(f"{d['iso3']} is already waiting on the speakers list.")
    pos = (scalar(w.conn, "SELECT MAX(position) FROM speakers_list_entry WHERE session_id = ?", (sid,)) or 0) + 1
    return w.insert("speakers_list_entry", {"session_id": sid, "list_kind": list_kind, "delegation_id": delegation_id,
                                            "student_id": student_id, "position": pos, "added_by": w.actor.label,
                                            "added_at": now_iso(), "amendment_id": amendment_id, "side": side}, ch(sid))


def current_list(s: dict) -> tuple[str, int | None]:
    """Which speakers list is live (D-068): for and against the amendment on the floor, the moderated caucus list,
    or the general speakers list."""
    if s.get("floor_amendment_id"):
        return "general", s["floor_amendment_id"]
    return ("moderated" if s.get("mode") == "moderated" else "general"), None


def waiting(conn, sid: int, s: dict | None = None, every_list: bool = False) -> list[dict]:
    """Delegations waiting to speak on the list that is live now (or on every list)."""
    q = ("SELECT e.*, d.iso3, c.name AS country, st.first_name, st.last_initial FROM speakers_list_entry e "
         "JOIN delegation d ON d.id = e.delegation_id JOIN country c ON c.iso3 = d.iso3 "
         "LEFT JOIN student st ON st.id = e.student_id WHERE e.session_id = ? AND e.status = 'waiting' ")
    if every_list:
        return rows(conn, q + "ORDER BY e.position", (sid,))
    kind, amendment = current_list(s or get_session(conn, sid))
    return rows(conn, q + "AND e.list_kind = ? AND e.amendment_id IS ? ORDER BY e.position", (sid, kind, amendment))


def move_speaker(w: Writer, entry_id: int, direction: str) -> None:
    e = one(w.conn, "SELECT * FROM speakers_list_entry WHERE id = ?", (entry_id,))
    if not e or e["status"] != "waiting":
        raise UserError("That speaker isn't waiting any more.")
    queue = waiting(w.conn, e["session_id"], every_list=True)
    queue = [q for q in queue if q["list_kind"] == e["list_kind"] and q["amendment_id"] == e["amendment_id"]]
    idx = next(i for i, q in enumerate(queue) if q["id"] == entry_id)
    j = idx - 1 if direction == "up" else idx + 1
    if not 0 <= j < len(queue):
        return
    other = queue[j]
    w.update("speakers_list_entry", entry_id, {"position": other["position"]}, ch(e["session_id"]), action="reorder")
    w.update("speakers_list_entry", other["id"], {"position": e["position"]}, ch(e["session_id"]), action="reorder")


def withdraw_speaker(w: Writer, entry_id: int) -> None:
    e = one(w.conn, "SELECT * FROM speakers_list_entry WHERE id = ?", (entry_id,))
    if e and e["status"] == "waiting":
        w.update("speakers_list_entry", entry_id, {"status": "withdrawn"}, ch(e["session_id"]), action="withdraw")


def _extra_percent(conn, student_id) -> int:
    if not student_id:
        return 0
    return scalar(conn, "SELECT extra_percent FROM timing_adjustment WHERE student_id = ?", (student_id,)) or 0


def next_speaker(w: Writer, sid: int) -> int | None:
    """Finish the current speaker and call the next one. Their timer is ready (not started)."""
    s = get_session(w.conn, sid)
    _open_only(s)
    _finish_current(w, s)
    queue = waiting(w.conn, sid, s)
    if not queue:
        w.update("live_session", sid, {"current_entry_id": None}, ch(sid), action="list_empty")
        return None
    nxt = queue[0]
    w.update("speakers_list_entry", nxt["id"], {"status": "speaking", "spoke_at": now_iso()}, ch(sid), action="speaking")
    w.update("live_session", sid, {"current_entry_id": nxt["id"]}, ch(sid), action="next_speaker")
    extra = _extra_percent(w.conn, nxt["student_id"])
    dur = s["speaking_time_s"] * (1 + extra / 100)
    label = nxt["country"] + (f" ({display_name(nxt['first_name'], nxt['last_initial'])})" if nxt["first_name"] else "")
    if nxt.get("side"):
        label += f" · {nxt['side']} the amendment"
    if extra:
        label += f" · +{extra}% time"
    make_timer(w, sid, "speaker", label, dur, entry_id=nxt["id"])
    return nxt["id"]


def _finish_current(w: Writer, s: dict, yielded_to: str = "") -> None:
    if s["current_entry_id"]:
        cur = one(w.conn, "SELECT * FROM speakers_list_entry WHERE id = ?", (s["current_entry_id"],))
        if cur and cur["status"] == "speaking":
            w.update("speakers_list_entry", cur["id"], {"status": "done", "yielded_to": yielded_to}, ch(s["id"]), action="spoke")
        for t in rows(w.conn, "SELECT * FROM timer WHERE session_id = ? AND entry_id = ? AND state != 'done'", (s["id"], s["current_entry_id"])):
            _timer_stop(w, t, "done")


def yield_floor(w: Writer, sid: int, to: str) -> None:
    if to not in ("chair", "questions", "another delegate"):
        raise UserError("Yield to the chair, to questions, or to another delegate.")
    s = get_session(w.conn, sid)
    _finish_current(w, s, yielded_to=to)
    w.update("live_session", sid, {"current_entry_id": None}, ch(sid), action=f"yield_to_{to.replace(' ', '_')}")


# ---------- timers (pausable and extendable: WCAG 2.2.1) ----------

def make_timer(w: Writer, sid: int, kind: str, label: str, duration_s: float, entry_id: int | None = None,
               start: bool = False) -> int:
    for t in rows(w.conn, "SELECT * FROM timer WHERE session_id = ? AND kind = ? AND state IN ('idle','running','paused')", (sid, kind)):
        _timer_stop(w, t, "done")
    tid = w.insert("timer", {"session_id": sid, "kind": kind, "label": label, "duration_s": float(duration_s),
                             "entry_id": entry_id, "created_at": now_iso(),
                             "state": "running" if start else "idle", "started_at": now() if start else None}, ch(sid))
    return tid


def remaining(t: dict, at: float | None = None) -> float:
    at = now() if at is None else at
    elapsed = t["elapsed_s"] + ((at - t["started_at"]) if t["state"] == "running" and t["started_at"] else 0)
    return t["duration_s"] + t["extended_s"] - elapsed


def _timer_stop(w: Writer, t: dict, state: str) -> None:
    el = t["elapsed_s"] + ((now() - t["started_at"]) if t["state"] == "running" and t["started_at"] else 0)
    w.update("timer", t["id"], {"state": state, "elapsed_s": el, "started_at": None}, ch(t["session_id"]), action=f"timer_{state}")


def timer_action(w: Writer, timer_id: int, action: str, seconds: float = 0) -> None:
    t = one(w.conn, "SELECT * FROM timer WHERE id = ?", (timer_id,))
    if not t:
        raise UserError("That timer doesn't exist.", 404)
    c = ch(t["session_id"])
    if action == "start":
        if t["state"] in ("idle", "paused"):
            w.update("timer", timer_id, {"state": "running", "started_at": now()}, c, action="timer_start")
    elif action == "pause":
        if t["state"] == "running":
            _timer_stop(w, t, "paused")
    elif action == "reset":
        w.update("timer", timer_id, {"state": "idle", "elapsed_s": 0, "started_at": None, "extended_s": 0}, c, action="timer_reset")
    elif action == "extend":
        if not 0 < seconds <= 600:
            raise UserError("Extend by between 1 second and 10 minutes.")
        w.update("timer", timer_id, {"extended_s": t["extended_s"] + seconds, "state": "paused" if t["state"] == "done" else t["state"]},
                 c, action="timer_extend")
    elif action == "stop":
        _timer_stop(w, t, "done")
    else:
        raise UserError("Unknown timer action.")


def current_timers(conn, sid: int) -> list[dict]:
    ts = rows(conn, "SELECT * FROM timer WHERE session_id = ? AND state != 'done' ORDER BY kind = 'speaker' DESC, id DESC", (sid,))
    t0 = now()
    for t in ts:
        t["remaining"] = remaining(t, t0)
        t["server_now"] = t0
    return ts


def set_timing_adjustment(w: Writer, student_id: int, extra_percent: int, note: str = "") -> None:
    if not 0 <= extra_percent <= 200:
        raise UserError("Extra time is between 0% and 200%.")
    existing = one(w.conn, "SELECT id FROM timing_adjustment WHERE student_id = ?", (student_id,))
    if existing:
        w.update("timing_adjustment", existing["id"], {"extra_percent": extra_percent, "note": note})
    else:
        w.insert("timing_adjustment", {"student_id": student_id, "extra_percent": extra_percent, "note": note})


# ---------- motions ----------

def propose_motion(w: Writer, sid: int, procedure_motion_id: int, proposer_delegation_id: int | None,
                   duration_s: int | None = None, speaking_time_s: int | None = None, topic: str = "") -> int:
    s = get_session(w.conn, sid)
    _open_only(s)
    pm = one(w.conn, "SELECT * FROM procedure_motion WHERE id = ? AND rule_set_id IS ?", (procedure_motion_id, s["procedure_rule_set_id"]))
    if not pm:
        raise UserError("That motion isn't in this committee's rules of procedure.")
    if pm["has_duration"] and not duration_s:
        raise UserError(f"Give a duration for “{pm['name']}”.")
    if pm["has_speaking_time"] and not speaking_time_s:
        raise UserError(f"Give a speaking time for “{pm['name']}”.")
    from app.modules.floor.service import UNMOD_MAX_S
    if pm["code"] == "unmod" and duration_s and duration_s > UNMOD_MAX_S:
        raise UserError(f"An unmoderated caucus is at most {UNMOD_MAX_S // 60} minutes. Move to extend it when it ends.")
    if pm["code"] in ("mod", "unmod", "suspend") and duration_s and duration_s > 3600:
        raise UserError("Keep it under an hour.")
    return w.insert("motion", {"session_id": sid, "procedure_motion_id": procedure_motion_id,
                               "proposer_delegation_id": proposer_delegation_id, "duration_s": duration_s,
                               "speaking_time_s": speaking_time_s, "topic": (topic or "")[:200], "created_at": now_iso()}, ch(sid))


def motions(conn, sid: int, open_only: bool = True) -> list[dict]:
    """Pending motions in order of precedence (most disruptive first), then order proposed (D-012)."""
    q = ("SELECT m.*, pm.name, pm.code, pm.precedence, pm.needs_second, pm.voting_rule_id, d.iso3 AS proposer, d2.iso3 AS seconder "
         "FROM motion m JOIN procedure_motion pm ON pm.id = m.procedure_motion_id LEFT JOIN delegation d ON d.id = m.proposer_delegation_id "
         "LEFT JOIN delegation d2 ON d2.id = m.seconder_delegation_id WHERE m.session_id = ?")
    if open_only:
        q += " AND m.status IN ('proposed','voting')"
    return rows(conn, q + " ORDER BY m.status = 'voting' DESC, pm.precedence DESC, m.id", (sid,))


def second_motion(w: Writer, motion_id: int, delegation_id: int) -> None:
    m = one(w.conn, "SELECT * FROM motion WHERE id = ?", (motion_id,))
    if not m or m["status"] != "proposed":
        raise UserError("That motion isn't open for a second.")
    if m["proposer_delegation_id"] == delegation_id:
        raise UserError("A delegation can't second its own motion.")
    w.update("motion", motion_id, {"seconder_delegation_id": delegation_id}, ch(m["session_id"]), action="seconded")


def decide_motion(w: Writer, motion_id: int, outcome: str) -> None:
    """outcome: 'consent' (passes with no objection), 'vote' (opens a procedural division), 'withdrawn', 'ruled_out'."""
    m = one(w.conn, "SELECT m.*, pm.name, pm.code, pm.needs_second, pm.voting_rule_id FROM motion m "
                    "JOIN procedure_motion pm ON pm.id = m.procedure_motion_id WHERE m.id = ?", (motion_id,))
    if not m or m["status"] not in ("proposed", "voting"):
        raise UserError("That motion has already been dealt with.")
    if outcome in ("consent", "vote") and m["needs_second"] and not m["seconder_delegation_id"]:
        raise UserError(f"“{m['name']}” needs a second before it can be decided.")
    c = ch(m["session_id"])
    if outcome == "consent":
        w.update("motion", motion_id, {"status": "passed", "decided_at": now_iso()}, c, action="motion_passed_by_consent")
        apply_motion(w, motion_id)
    elif outcome == "vote":
        title = f"Motion: {m['name']}" + (f" — {m['topic']}" if m["topic"] else "")
        did = open_division(w, m["session_id"], title, "motion", motion_id, procedural=True, rule_id=m["voting_rule_id"])
        w.update("motion", motion_id, {"status": "voting", "division_id": did}, c, action="motion_to_vote")
    elif outcome in ("withdrawn", "ruled_out"):
        w.update("motion", motion_id, {"status": outcome, "decided_at": now_iso()}, c, action=f"motion_{outcome}")
    else:
        raise UserError("Unknown decision.")


def apply_motion(w: Writer, motion_id: int) -> None:
    m = one(w.conn, "SELECT m.*, pm.code, pm.name FROM motion m JOIN procedure_motion pm ON pm.id = m.procedure_motion_id WHERE m.id = ?",
            (motion_id,))
    sid, c = m["session_id"], ch(m["session_id"])
    code = m["code"]
    if code == "mod":
        set_mode(w, sid, "moderated", m["topic"])
        if m["speaking_time_s"]:
            w.update("live_session", sid, {"speaking_time_s": m["speaking_time_s"]}, c, action="speaking_time")
        make_timer(w, sid, "caucus", "Moderated caucus" + (f": {m['topic']}" if m["topic"] else ""), m["duration_s"] or 300, start=True)
    elif code == "unmod":
        set_mode(w, sid, "unmoderated", m["topic"])
        make_timer(w, sid, "caucus", "Unmoderated caucus", m["duration_s"] or 300, start=True)
    elif code == "speaking_time" and m["speaking_time_s"]:
        w.update("live_session", sid, {"speaking_time_s": m["speaking_time_s"]}, c, action="speaking_time")
    elif code == "close_debate":
        # Debate is closed: into voting procedure (D-068). Any amendment still on the floor is voted first.
        set_mode(w, sid, "voting")
        w.update("live_session", sid, {"stage": "voting_procedure"}, c, action="stage")
    elif code == "introduce_amendment":
        import re
        found = re.search(r"(?i)amendment\s*#?(\d+)", m["topic"] or "")
        if found:
            from app.modules.floor.service import bring_to_floor
            try:
                bring_to_floor(w, sid, int(found.group(1)))
            except UserError:
                pass                 # the chair brings it to the floor from the amendment board instead
    elif code == "suspend":
        set_state(w, sid, "suspended")
        if m["duration_s"]:
            make_timer(w, sid, "general", "Suspension", m["duration_s"], start=True)
    elif code == "adjourn":
        set_state(w, sid, "closed")


def end_caucus(w: Writer, sid: int) -> None:
    set_mode(w, sid, "formal")
    for t in rows(w.conn, "SELECT * FROM timer WHERE session_id = ? AND kind = 'caucus' AND state != 'done'", (sid,)):
        _timer_stop(w, t, "done")


# ---------- divisions ----------

def _delegations(conn, committee_id: int) -> list[dict]:
    return rows(conn, "SELECT d.id, d.iso3, c.name, (SELECT COUNT(*) FROM delegation_member dm WHERE dm.delegation_id = d.id "
                      "AND dm.deleted_at IS NULL) AS students FROM delegation d JOIN country c ON c.iso3 = d.iso3 "
                      "WHERE d.committee_id = ? AND d.deleted_at IS NULL ORDER BY c.name", (committee_id,))


def open_division(w: Writer, sid: int, title: str, target_kind: str, target_id: int | None, procedural: bool = False,
                  rule_id: int | None = None, pred: dict | None = None) -> int:
    """Opens a vote. For substantive votes, delegations without a student are voted by the engine
    (their most likely vote from a fresh, stored prediction) and labelled computed (D-022)."""
    s = get_session(w.conn, sid)
    _open_only(s)
    if scalar(w.conn, "SELECT COUNT(*) FROM division WHERE session_id = ? AND status = 'open'", (sid,)):
        raise UserError("Close the division that is open before starting another.")
    rule_id = rule_id or s["voting_rule_id"]
    pred_id = None
    computed_votes: dict[str, str] = {}
    if not procedural and target_kind in ("paragraph", "amendment", "resolution") and target_id:
        from app.modules.mun.predict import run_prediction, store_prediction
        if pred is None or (pred["target"]["kind"], pred["target"]["id"]) != (target_kind, target_id):
            pred = run_prediction(w.conn, target_kind, target_id, with_swing=False)
        pred_id = store_prediction(w, pred, label=f"Before division: {title}")
        computed_votes = {d.iso3: d.modal_vote for d in pred["dists"]}
    did = w.insert("division", {"session_id": sid, "title": title[:200], "target_kind": target_kind, "target_id": target_id,
                                "rule_id": rule_id, "procedural": int(procedural), "prediction_id": pred_id,
                                "opened_at": now_iso()}, ch(sid))
    if not procedural:
        # Delegations whose students are all away (none seen in this session in the last two minutes) are voted by the
        # engine too, labelled computed, so an absent student never holds up a vote (D-079). A student who arrives in
        # time takes the vote back.
        here = {r["delegation_id"] for r in rows(
            w.conn, "SELECT DISTINCT dm.delegation_id FROM session_participant sp JOIN delegation_member dm ON dm.student_id = sp.student_id "
                    "AND dm.deleted_at IS NULL WHERE sp.session_id = ? AND sp.last_seen > ?", (sid, now() - PARTICIPANT_TTL_S))}
        for d in _delegations(w.conn, s["committee_id"]):
            if d["students"] == 0 or d["id"] not in here:
                w.conn.execute("INSERT INTO division_vote (division_id, iso3, delegation_id, vote, computed, cast_by, cast_at) "
                               "VALUES (?,?,?,?,1,?,?)", (did, d["iso3"], d["id"], computed_votes.get(d["iso3"], "abstain"),
                                                          "engine" if d["students"] == 0 else "engine: away", now_iso()))
    w.update("live_session", sid, {"current_division_id": did, "mode": "voting"}, ch(sid), action="division_opened")
    return did


def voters(conn, division: dict, committee_id: int) -> list[dict]:
    """Who votes: every delegation for a substantive vote; only delegations with students for a procedural one."""
    ds = _delegations(conn, committee_id)
    return [d for d in ds if d["students"] > 0] if division["procedural"] else ds


def cast_vote(w: Writer, division_id: int, delegation_id: int, vote: str) -> None:
    dv = one(w.conn, "SELECT dv.*, ls.committee_id FROM division dv JOIN live_session ls ON ls.id = dv.session_id WHERE dv.id = ?",
             (division_id,))
    if not dv or dv["status"] != "open":
        raise UserError("Voting on that division has closed.")
    if vote not in ("yes", "abstain", "no"):
        raise UserError("Vote yes, abstain or no.")
    if dv["procedural"] and vote == "abstain":
        raise UserError("Procedural votes are yes or no (no abstentions).")
    d = one(w.conn, "SELECT * FROM delegation WHERE id = ? AND committee_id = ?", (delegation_id, dv["committee_id"]))
    if not d:
        raise UserError("That delegation isn't in this committee.")
    if vote == "abstain" and not dv["procedural"] and one(
            w.conn, "SELECT 1 FROM roll_call WHERE session_id = ? AND delegation_id = ? AND status = 'present_and_voting'",
            (dv["session_id"], delegation_id)):
        raise UserError(f"{d['iso3']} answered “present and voting” at roll call, so it can't abstain on a substantive vote.")
    existing = one(w.conn, "SELECT * FROM division_vote WHERE division_id = ? AND iso3 = ?", (division_id, d["iso3"]))
    if existing and existing["computed"] and existing["cast_by"] != "engine: away":
        raise UserError("That delegation is voted by the engine (no student holds it).")
    if existing and existing["computed"]:
        # The student arrived after the vote opened: their own vote replaces the engine's.
        w.update("division_vote", existing["id"], {"vote": vote, "computed": 0, "cast_by": w.actor.label, "cast_at": now_iso()},
                 ch(dv["session_id"]), action="vote_cast")
    elif existing:
        w.update("division_vote", existing["id"], {"vote": vote, "cast_by": w.actor.label, "cast_at": now_iso()},
                 ch(dv["session_id"]), action="vote_changed")
    else:
        w.insert("division_vote", {"division_id": division_id, "iso3": d["iso3"], "delegation_id": delegation_id, "vote": vote,
                                   "cast_by": w.actor.label, "cast_at": now_iso()}, ch(dv["session_id"]))


def division_state(conn, division_id: int) -> dict:
    dv = one(conn, "SELECT dv.*, ls.committee_id, vr.name AS rule_name FROM division dv JOIN live_session ls ON ls.id = dv.session_id "
                   "JOIN voting_rule vr ON vr.id = dv.rule_id WHERE dv.id = ?", (division_id,))
    if not dv:
        raise UserError("That division doesn't exist.", 404)
    votes = {v["iso3"]: v for v in rows(conn, "SELECT * FROM division_vote WHERE division_id = ?", (division_id,))}
    vs = voters(conn, dv, dv["committee_id"])
    dv["voters"] = [{**d, "vote": votes.get(d["iso3"], {}).get("vote"), "computed": votes.get(d["iso3"], {}).get("computed", 0)} for d in vs]
    dv["cast"] = sum(1 for v in dv["voters"] if v["vote"])
    dv["counts"] = {k: sum(1 for v in dv["voters"] if v["vote"] == k) for k in ("yes", "abstain", "no")}
    # Live veto warning (Security Council, D-068): a permanent member voting no blocks a substantive vote.
    veto = (one(conn, "SELECT veto_iso3 FROM voting_rule WHERE id = ?", (dv["rule_id"],)) or {}).get("veto_iso3") or ""
    holders = {x.strip().upper() for x in veto.split(",") if x.strip()}
    dv["veto_by"] = [v["name"] for v in dv["voters"] if v["iso3"] in holders and v["vote"] == "no"] if not dv["procedural"] else []
    return dv


def scaled_rule(rule: VotingRule, voters_n: int, members: int) -> VotingRule:
    """Procedural votes in a small group: only delegations with students vote, so an absolute
    minimum (e.g. 9 of 15 in the Security Council) is scaled to the share of members voting (D-040)."""
    if not rule.min_yes or voters_n >= members:
        return rule
    return VotingRule(rule.code, rule.name, rule.threshold_num, rule.threshold_den, rule.denominator, rule.at_threshold,
                      max(1, math.ceil(rule.min_yes * voters_n / members)), rule.veto)


def close_division(w: Writer, division_id: int) -> dict:
    dv = division_state(w.conn, division_id)
    if dv["status"] != "open":
        raise UserError("That division is already closed.")
    rule = VotingRule.from_row(one(w.conn, "SELECT * FROM voting_rule WHERE id = ?", (dv["rule_id"],)))
    members = len(_delegations(w.conn, dv["committee_id"]))
    votes = {v["iso3"]: (v["vote"] or "absent") for v in dv["voters"]}
    if dv["procedural"]:
        rule = scaled_rule(rule, len(dv["voters"]), members)
        out = tally(rule, votes, len(dv["voters"]))
    else:
        out = tally(rule, votes, members)
    computed = sum(1 for v in dv["voters"] if v["computed"])
    summary = out.summary + (f" ({computed} computed by the engine)" if computed else "")
    c = ch(dv["session_id"])
    w.update("division", division_id, {"status": "closed", "closed_at": now_iso(), "yes": out.yes, "no": out.no,
                                       "abstain": out.abstain, "absent": out.absent, "computed": computed,
                                       "passed": int(out.passed), "summary": summary}, c, action="division_closed")
    w.update("live_session", dv["session_id"], {"current_division_id": None, "mode": "formal"}, c, action="division_result")
    if dv["target_kind"] == "motion":
        w.update("motion", dv["target_id"], {"status": "passed" if out.passed else "failed", "decided_at": now_iso()}, c,
                 action="motion_result")
        if out.passed:
            apply_motion(w, dv["target_id"])
    elif dv["target_kind"] in ("paragraph", "amendment", "resolution") and dv["target_id"]:
        # Human votes become calibration data next to the prediction made when the vote opened.
        # Computed votes are the engine's own guesses, so they are never used to calibrate it.
        from app.modules.mun.service import record_actual_votes, set_amendment_status
        human = {v["iso3"]: (v["vote"] or "absent") for v in dv["voters"] if not v["computed"]}
        record_actual_votes(w, dv["target_kind"], dv["target_id"], human, "conference", dv["prediction_id"])
        if dv["target_kind"] == "amendment":
            a = one(w.conn, "SELECT status FROM amendment WHERE id = ?", (dv["target_id"],))
            if a and a["status"] == "tabled":
                set_amendment_status(w, dv["target_id"], "passed" if out.passed else "failed")
            if one(w.conn, "SELECT 1 FROM live_session WHERE id = ? AND floor_amendment_id = ?", (dv["session_id"], dv["target_id"])):
                from app.modules.floor.service import clear_floor
                clear_floor(w, dv["session_id"])
        if dv["target_kind"] == "resolution":
            w.update("resolution", dv["target_id"], {"status": "passed" if out.passed else "failed"}, c)
            w.update("live_session", dv["session_id"], {"resolution_id": dv["target_id"]}, c, action="draft_voted")
    return {"passed": out.passed, "summary": summary}


def cancel_division(w: Writer, division_id: int) -> None:
    dv = one(w.conn, "SELECT * FROM division WHERE id = ?", (division_id,))
    if dv and dv["status"] == "open":
        w.update("division", division_id, {"status": "cancelled", "closed_at": now_iso()}, ch(dv["session_id"]), action="division_cancelled")
        w.update("live_session", dv["session_id"], {"current_division_id": None, "mode": "formal"}, ch(dv["session_id"]))
        if dv["target_kind"] == "motion":
            w.update("motion", dv["target_id"], {"status": "proposed", "division_id": None}, ch(dv["session_id"]))


# ---------- minutes ----------

def _hhmm(iso: str) -> str:
    return iso[11:16] if iso and len(iso) >= 16 else ""


def generate_minutes(conn, sid: int) -> str:
    """Minutes from the session log (CH-5). Times are UTC as stored; the chair can edit them."""
    from jinja2.sandbox import SandboxedEnvironment
    s = get_session(conn, sid)
    conf = one(conn, "SELECT name FROM conference WHERE id = ?", (s["conference_id"],))
    items = []
    for e in rows(conn, "SELECT e.*, d.iso3, c.name AS country, st.first_name, st.last_initial FROM speakers_list_entry e "
                        "JOIN delegation d ON d.id = e.delegation_id JOIN country c ON c.iso3 = d.iso3 "
                        "LEFT JOIN student st ON st.id = e.student_id WHERE e.session_id = ? AND e.spoke_at IS NOT NULL", (sid,)):
        who = f" ({display_name(e['first_name'], e['last_initial'])})" if e["first_name"] else ""
        y = f"; yielded to {e['yielded_to']}" if e["yielded_to"] else ""
        items.append((e["spoke_at"], f"{e['country']}{who} spoke{' in moderated caucus' if e['list_kind'] == 'moderated' else ''}{y}."))
    for m in motions(conn, sid, open_only=False):
        detail = []
        if m["duration_s"]:
            detail.append(f"{m['duration_s'] // 60} min" if m["duration_s"] % 60 == 0 else f"{m['duration_s']} s")
        if m["speaking_time_s"]:
            detail.append(f"{m['speaking_time_s']} s speeches")
        if m["topic"]:
            detail.append(m["topic"])
        d = f" ({', '.join(detail)})" if detail else ""
        result = {"passed": "passed", "failed": "failed", "withdrawn": "was withdrawn", "ruled_out": "was ruled out of order",
                  "proposed": "was pending", "voting": "was being voted on"}[m["status"]]
        items.append((m["created_at"], f"Motion: {m['name']}{d}, proposed by {m['proposer'] or 'the chair'}"
                                       f"{', seconded by ' + m['seconder'] if m['seconder'] else ''}; {result}."))
    divisions = rows(conn, "SELECT dv.*, vr.name AS rule FROM division dv JOIN voting_rule vr ON vr.id = dv.rule_id "
                           "WHERE dv.session_id = ? AND dv.status = 'closed' ORDER BY dv.id", (sid,))
    for dv in divisions:
        items.append((dv["closed_at"], f"Division — {dv['title']}: {dv['summary']}."))
    # The floor (D-068): points and their answers, amendments brought to the floor or adopted as friendly.
    kinds = {"order": "Point of order", "privilege": "Point of personal privilege", "inquiry": "Point of parliamentary inquiry",
             "reply": "Right of reply"}
    outcome = {"answered": "answered", "granted": "granted", "declined": "declined", "withdrawn": "withdrawn", "raised": "not reached"}
    for p in rows(conn, "SELECT fp.*, c.name AS country FROM floor_point fp JOIN delegation d ON d.id = fp.delegation_id "
                        "JOIN country c ON c.iso3 = d.iso3 WHERE fp.session_id = ?", (sid,)):
        items.append((p["created_at"], f"{kinds[p['kind']]} from {p['country']}{': ' + p['note'] if p['note'] else ''}; {outcome[p['status']]}."))
    for ev in rows(conn, "SELECT * FROM event_log WHERE channel = ? AND action IN ('amendment_on_floor', 'friendly', 'floor_reopened') "
                         "ORDER BY seq", (ch(sid),)):
        after = json.loads(ev["after_json"] or "{}")
        if ev["action"] == "amendment_on_floor" and after.get("floor_amendment_id"):
            items.append((ev["at"], f"Amendment {after['floor_amendment_id']} was brought to the floor."))
        elif ev["action"] == "friendly":
            items.append((ev["at"], f"Amendment {ev['entity_id']} was accepted as friendly and added without a vote."))
        elif ev["action"] == "floor_reopened":
            items.append((ev["at"], "The floor was reopened with another draft resolution."))
    for ev in rows(conn, "SELECT * FROM event_log WHERE channel = ? AND action IN ('session_suspended','session_open','session_closed','opened') "
                         "ORDER BY seq", (ch(sid),)):
        label = {"opened": "Session opened", "session_suspended": "Session suspended", "session_open": "Session resumed",
                 "session_closed": "Session closed"}[ev["action"]]
        items.append((ev["at"], label + "."))
    items.sort(key=lambda x: x[0] or "")
    dels = _delegations(conn, s["committee_id"])
    tpl = scalar(conn, "SELECT body FROM template WHERE kind = 'minutes' AND deleted_at IS NULL ORDER BY id LIMIT 1") or "{% for item in items %}{{ item.time }} {{ item.text }}\n{% endfor %}"
    env = SandboxedEnvironment(trim_blocks=True, lstrip_blocks=True)
    return env.from_string(tpl).render(
        committee=s["committee"], conference=conf["name"] if conf else "", opened_at=s["created_at"].replace("T", " ")[:16] + " UTC",
        chair=s["chair_label"], present_count=len(dels), student_count=sum(d["students"] for d in dels),
        computed_count=sum(1 for d in dels if d["students"] == 0),
        items=[{"time": _hhmm(t), "text": x} for t, x in items],
        divisions=[{"title": d["title"], "summary": d["summary"], "rule": d["rule"]} for d in divisions])


def save_minutes(w: Writer, sid: int, body: str, generated: bool) -> int:
    v = (scalar(w.conn, "SELECT MAX(version) FROM minutes WHERE session_id = ?", (sid,)) or 0) + 1
    return w.insert("minutes", {"session_id": sid, "version": v, "body": body, "generated": int(generated),
                                "author": w.actor.label, "created_at": now_iso()}, ch(sid))
