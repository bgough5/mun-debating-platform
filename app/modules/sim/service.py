"""Guided MUN simulation v3 (D-060), the whip-count exercise (D-061) and practice v3.

A live session moves through six stages that follow real committee procedure; in the
middle, the floor is open and motions decide what happens next (D-068).
The chair's script for each stage is data (procedure_stage), so it can be edited
under Admin. Students always see the stage and what they can do now.

Whip-count exercise: before a division, every student predicts how a few named
delegations will vote. Predictions lock when voting opens and are scored against
the votes actually cast, never against the model (audit §4, D-009). Votes cast
by the engine for delegations with no student are scored separately and labelled
computed.

Practice v3: one student, or a few, run delegations against a computed chamber.
Each computed delegation gets a hidden mandate drawn once from the engine's own
distribution for it (with the same bloc correlation the engine uses), so it votes
consistently, and amendments move it the way the engine says they would.
Students lobby by holding simulated conversations, record what they think each
delegation will do, and then see how well they read the room. Nothing in a
practice run changes the class's evidence, amendments or predictions.
"""
from __future__ import annotations

import json
import math
import random
import string

from app.db import Writer, one, rows, scalar
from app.engine.rules import VotingRule, tally
from app.errors import UserError
from app.util import display_name, now_iso

STAGES = ["roll_call", "agenda", "opening_speeches", "floor", "voting_procedure", "debrief"]      # D-068
ROLL = {"present": "Present", "present_and_voting": "Present and voting", "absent": "Absent"}
VOTES = ("yes", "abstain", "no")
LOBBY_LIMIT = 5            # conversations per student per practice run (an unmoderated caucus is short)


def ch(sid: int) -> str:
    return f"session:{sid}"


# ---------------- stages ----------------

def stages(conn, session: dict) -> list[dict]:
    """The stage list for this committee's rules of procedure (falls back to the GA set)."""
    rs = session.get("procedure_rule_set_id")
    out = rows(conn, "SELECT * FROM procedure_stage WHERE rule_set_id IS ? AND deleted_at IS NULL ORDER BY position", (rs,))
    if not out:
        out = rows(conn, "SELECT ps.* FROM procedure_stage ps JOIN procedure_rule_set r ON r.id = ps.rule_set_id "
                         "WHERE r.code = 'ga_simplified' AND ps.deleted_at IS NULL ORDER BY ps.position")
    return out


class _Blank(dict):
    def __missing__(self, key):
        return "…"


def fill(text: str, values: dict) -> str:
    """Fills {placeholders} in an admin-edited script; unknown or missing ones show as an ellipsis."""
    try:
        return string.Formatter().vformat(text or "", (), _Blank({k: v for k, v in values.items() if v not in (None, "")}))
    except (ValueError, IndexError):
        return text or ""


def script_values(conn, s: dict) -> dict:
    present = roll_present(conn, s["id"])
    last = one(conn, "SELECT * FROM division WHERE session_id = ? AND status = 'closed' ORDER BY id DESC LIMIT 1", (s["id"],))
    cur = one(conn, "SELECT * FROM division WHERE id = ?", (s["current_division_id"],)) if s.get("current_division_id") else None
    motion = one(conn, "SELECT m.*, pm.name FROM motion m JOIN procedure_motion pm ON pm.id = m.procedure_motion_id "
                       "WHERE m.session_id = ? ORDER BY m.id DESC LIMIT 1", (s["id"],))
    target = (cur or last or {}).get("title")
    return {
        "committee": s.get("committee") or s.get("title"), "agenda": s.get("agenda") or None,
        "present": present or None, "majority": (present // 2 + 1) if present else None,
        "speaking_time": s.get("speaking_time_s"), "target": target, "target_short": (target or "").split(":")[0].lower() or None,
        "yes": last["yes"] if last else None, "no": last["no"] if last else None, "abstain": last["abstain"] if last else None,
        "result": ("passes" if last["passed"] else "fails") if last else None,
        "minutes": (motion["duration_s"] // 60) if motion and motion["duration_s"] else None,
        "seconds": motion["speaking_time_s"] if motion else None, "topic": motion["topic"] if motion else None,
    }


def stage_view(conn, s: dict) -> dict:
    st = stages(conn, s)
    codes = [x["code"] for x in st]
    current = s.get("stage") or "roll_call"
    idx = codes.index(current) if current in codes else 0
    here = st[idx] if st else {"code": current, "name": current, "chair_script": "", "chair_next": "", "student_prompt": ""}
    values = script_values(conn, s)
    return {"stages": st, "stage": here, "stage_index": idx,
            "script": fill(here["chair_script"], values), "chair_next": fill(here["chair_next"], values),
            "student_prompt": fill(here["student_prompt"], values),
            "next_stage": st[idx + 1] if idx + 1 < len(st) else None, "prev_stage": st[idx - 1] if idx > 0 else None}


def set_stage(w: Writer, sid: int, code: str) -> None:
    if code not in STAGES:
        raise UserError("Unknown stage.")
    s = one(w.conn, "SELECT * FROM live_session WHERE id = ?", (sid,))
    if s["state"] == "closed":
        raise UserError("This session is closed.", 409)
    w.update("live_session", sid, {"stage": code}, ch(sid), action="stage")


# ---------------- roll call and agenda ----------------

def _delegations(conn, committee_id: int) -> list[dict]:
    return rows(conn, "SELECT d.id, d.iso3, c.name, (SELECT COUNT(*) FROM delegation_member dm WHERE dm.delegation_id = d.id "
                      "AND dm.deleted_at IS NULL) AS students FROM delegation d JOIN country c ON c.iso3 = d.iso3 "
                      "WHERE d.committee_id = ? AND d.deleted_at IS NULL ORDER BY c.name", (committee_id,))


def roll_state(conn, s: dict) -> list[dict]:
    answers = {r["delegation_id"]: r for r in rows(conn, "SELECT * FROM roll_call WHERE session_id = ?", (s["id"],))}
    return [{**d, "status": answers.get(d["id"], {}).get("status"), "computed": answers.get(d["id"], {}).get("computed", 0),
             "answered_by": answers.get(d["id"], {}).get("answered_by", "")} for d in _delegations(conn, s["committee_id"])]


def _signed(w, delegation_id: int) -> str:
    from app.modules.chair.service import actor_label
    return actor_label(w.conn, w.actor, delegation_id)


def roll_present(conn, sid: int) -> int:
    return scalar(conn, "SELECT COUNT(*) FROM roll_call WHERE session_id = ? AND status != 'absent'", (sid,)) or 0


def answer_roll(w: Writer, s: dict, delegation_id: int, status: str, computed: bool = False) -> None:
    if status not in ROLL:
        raise UserError("Answer Present, Present and voting, or Absent.")
    d = one(w.conn, "SELECT id FROM delegation WHERE id = ? AND committee_id = ? AND deleted_at IS NULL", (delegation_id, s["committee_id"]))
    if not d:
        raise UserError("That delegation isn't in this committee.", 404)
    w.conn.execute("INSERT INTO roll_call (session_id, delegation_id, status, computed, answered_by, answered_at) VALUES (?,?,?,?,?,?) "
                   "ON CONFLICT (session_id, delegation_id) DO UPDATE SET status = excluded.status, computed = excluded.computed, "
                   "answered_by = excluded.answered_by, answered_at = excluded.answered_at",
                   (s["id"], delegation_id, status, int(computed), _signed(w, delegation_id), now_iso()))
    w.log("roll_call", f"{s['id']}:{delegation_id}", "answered", None, {"status": status, "computed": computed}, ch(s["id"]))


def roll_computed(w: Writer, s: dict) -> int:
    """Delegations with no student answer 'present', labelled computed (D-041)."""
    n = 0
    for d in roll_state(w.conn, s):
        if d["students"] == 0 and not d["status"]:
            answer_roll(w, s, d["id"], "present", computed=True)
            n += 1
    return n


def set_agenda(w: Writer, sid: int, text: str) -> None:
    text = " ".join((text or "").split())[:200]
    if not text:
        raise UserError("Type the agenda topic.")
    w.update("live_session", sid, {"agenda": text}, ch(sid), action="agenda")


# ---------------- whip-count exercise (D-061) ----------------

def _students_in(conn, committee_id: int) -> list[dict]:
    return rows(conn, "SELECT dm.student_id, dm.delegation_id FROM delegation_member dm JOIN delegation d ON d.id = dm.delegation_id "
                      "WHERE d.committee_id = ? AND dm.deleted_at IS NULL AND d.deleted_at IS NULL ORDER BY dm.student_id", (committee_id,))


def start_whip(w: Writer, s: dict, target_kind: str, target_id: int, title: str, per_student: int = 5) -> int:
    if target_kind not in ("paragraph", "amendment", "resolution"):
        raise UserError("A whip count is for a paragraph, an amendment or the whole resolution.")
    if scalar(w.conn, "SELECT COUNT(*) FROM whip_round WHERE session_id = ? AND status = 'open'", (s["id"],)):
        raise UserError("A whip count is already running. Open the vote or cancel it first.")
    if scalar(w.conn, "SELECT COUNT(*) FROM division WHERE session_id = ? AND status = 'open'", (s["id"],)):
        raise UserError("Close the division that is open first: predictions must come before voting.")
    dels = _delegations(w.conn, s["committee_id"])
    students = _students_in(w.conn, s["committee_id"])
    if not students:
        raise UserError("No students are in delegations in this committee yet, so there is no one to predict.")
    per_student = max(1, min(int(per_student or 5), max(1, len(dels) - 1)))
    rid = w.insert("whip_round", {"session_id": s["id"], "target_kind": target_kind, "target_id": target_id, "title": title[:200],
                                  "per_student": per_student, "created_at": now_iso()}, ch(s["id"]))
    rng = random.Random(rid)
    order = [d["id"] for d in dels]
    rng.shuffle(order)
    rank = {d: i for i, d in enumerate(order)}
    cover = {d["id"]: 0 for d in dels}
    for st in students:
        others = [d for d in cover if d != st["delegation_id"]]
        others.sort(key=lambda d: (cover[d], rank[d]))       # spread named delegations evenly across students
        for d in others[:per_student]:
            cover[d] += 1
            w.conn.execute("INSERT OR IGNORE INTO whip_prediction (round_id, student_id, delegation_id) VALUES (?,?,?)",
                           (rid, st["student_id"], d))
    return rid


def open_round(conn, sid: int) -> dict | None:
    return one(conn, "SELECT * FROM whip_round WHERE session_id = ? AND status = 'open' ORDER BY id DESC LIMIT 1", (sid,))


def my_whip(conn, round_id: int, student_id: int) -> list[dict]:
    return rows(conn, "SELECT wp.*, d.iso3, c.name FROM whip_prediction wp JOIN delegation d ON d.id = wp.delegation_id "
                      "JOIN country c ON c.iso3 = d.iso3 WHERE wp.round_id = ? AND wp.student_id = ? ORDER BY c.name",
                (round_id, student_id))


def predict(w: Writer, round_id: int, student_id: int, delegation_id: int, vote: str) -> None:
    r = one(w.conn, "SELECT * FROM whip_round WHERE id = ?", (round_id,))
    if not r or r["status"] != "open":
        raise UserError("Predictions are closed: voting has started.", 409)
    if vote not in VOTES:
        raise UserError("Predict Yes, No or Abstain.")
    row = one(w.conn, "SELECT id FROM whip_prediction WHERE round_id = ? AND student_id = ? AND delegation_id = ?",
              (round_id, student_id, delegation_id))
    if not row:
        raise UserError("That delegation isn't one of yours to predict.", 403)
    w.conn.execute("UPDATE whip_prediction SET vote = ?, predicted_at = ? WHERE id = ?", (vote, now_iso(), row["id"]))
    w.log("whip_prediction", row["id"], "predicted", None, {"round": round_id}, ch(r["session_id"]))


def lock_round(w: Writer, round_id: int, division_id: int | None) -> None:
    w.update("whip_round", round_id, {"status": "locked", "locked_at": now_iso(), "division_id": division_id},
             ch(scalar(w.conn, "SELECT session_id FROM whip_round WHERE id = ?", (round_id,))), action="whip_locked")


def cancel_round(w: Writer, round_id: int) -> None:
    r = one(w.conn, "SELECT * FROM whip_round WHERE id = ?", (round_id,))
    if r and r["status"] == "open":
        w.update("whip_round", round_id, {"status": "cancelled"}, ch(r["session_id"]), action="whip_cancelled")


def whip_scores(conn, round_id: int) -> dict:
    """Each student's predictions scored against the votes actually cast (D-061).
    Engine-cast (computed) votes are scored separately and labelled; they are never mixed in silently."""
    r = one(conn, "SELECT * FROM whip_round WHERE id = ?", (round_id,))
    if not r or not r["division_id"]:
        return {"round": r, "students": [], "ready": False}
    dv = one(conn, "SELECT * FROM division WHERE id = ?", (r["division_id"],))
    actual = {v["delegation_id"]: v for v in rows(conn, "SELECT * FROM division_vote WHERE division_id = ?", (r["division_id"],))}
    preds = rows(conn, "SELECT wp.*, d.iso3, c.name AS country, st.first_name, st.last_initial FROM whip_prediction wp "
                       "JOIN delegation d ON d.id = wp.delegation_id JOIN country c ON c.iso3 = d.iso3 "
                       "JOIN student st ON st.id = wp.student_id WHERE wp.round_id = ? ORDER BY st.first_name, c.name", (round_id,))
    by: dict[int, dict] = {}
    for p in preds:
        s = by.setdefault(p["student_id"], {"student_id": p["student_id"], "name": display_name(p["first_name"], p["last_initial"]),
                                           "predictions": [], "human_n": 0, "human_ok": 0, "computed_n": 0, "computed_ok": 0, "missing": 0})
        a = actual.get(p["delegation_id"])
        item = {"country": p["country"], "iso3": p["iso3"], "predicted": p["vote"], "actual": a["vote"] if a else None,
                "computed": bool(a and a["computed"]), "correct": None}
        if p["vote"] is None:
            s["missing"] += 1
        elif a and a["vote"] in VOTES:
            item["correct"] = p["vote"] == a["vote"]
            key = "computed" if a["computed"] else "human"
            s[f"{key}_n"] += 1
            s[f"{key}_ok"] += int(item["correct"])
        s["predictions"].append(item)
    for s in by.values():
        n = s["human_n"] + s["computed_n"]
        s["accuracy"] = (s["human_ok"] + s["computed_ok"]) / n if n else None
        s["human_accuracy"] = s["human_ok"] / s["human_n"] if s["human_n"] else None
    ready = dv is not None and dv["status"] == "closed"
    return {"round": r, "division": dv, "students": sorted(by.values(), key=lambda x: x["name"]), "ready": ready}


# ---------------- debrief ----------------

FIDELITY_OK, FIDELITY_LOW = 0.30, 0.15


def _rule(conn, rule_id: int) -> VotingRule:
    return VotingRule.from_row(one(conn, "SELECT * FROM voting_rule WHERE id = ?", (rule_id,)))


def pivotal(rule: VotingRule, votes: dict[str, str], members: int) -> list[dict]:
    """Hindsight swing: delegations whose single changed vote would have flipped the result."""
    base = tally(rule, votes, members).passed
    out = []
    for iso, v in sorted(votes.items()):
        flips = [alt for alt in VOTES if alt != v and tally(rule, {**votes, iso: alt}, members).passed != base]
        if flips:
            out.append({"iso3": iso, "vote": v, "flip_to": flips})
    return out


def stored_quality(conn, prediction_id: int | None) -> dict[str, str]:
    """Evidence quality per country from the inputs stored with a prediction (D-065)."""
    from app.engine.model import CountryInput, Source, evidence_quality
    if not prediction_id:
        return {}
    raw = scalar(conn, "SELECT inputs_json FROM prediction WHERE id = ?", (prediction_id,))
    if not raw:
        return {}
    out = {}
    for c in json.loads(raw).get("countries", []):
        srcs = tuple(Source(s[0], s[1], s[2], s[2], s[3]) for s in c["sources"])
        out[c["iso3"]] = evidence_quality(CountryInput(c["iso3"], c["iso3"], srcs, c.get("group", ""), c.get("rho", 0.0)))
    return out


def debrief(conn, division_id: int) -> dict:
    dv = one(conn, "SELECT dv.*, ls.committee_id FROM division dv JOIN live_session ls ON ls.id = dv.session_id WHERE dv.id = ?",
             (division_id,))
    if not dv:
        raise UserError("That vote doesn't exist.", 404)
    if dv["status"] != "closed":
        raise UserError("The debrief is ready when the vote closes.", 409)
    votes = rows(conn, "SELECT dv.*, c.name AS country, d.id AS del_id FROM division_vote dv JOIN country c ON c.iso3 = dv.iso3 "
                       "LEFT JOIN delegation d ON d.id = dv.delegation_id WHERE dv.division_id = ? ORDER BY c.name", (division_id,))
    rule = _rule(conn, dv["rule_id"])
    members = len(_delegations(conn, dv["committee_id"]))
    vmap = {v["iso3"]: v["vote"] for v in votes}
    piv = pivotal(rule, vmap, members) if not dv["procedural"] else []
    names = {v["iso3"]: v["country"] for v in votes}
    quality = stored_quality(conn, dv["prediction_id"])
    for p in piv:
        p["country"] = names.get(p["iso3"], p["iso3"])
        p["quality"] = quality.get(p["iso3"], "unknown")
    # Engine calibration on this vote: the prediction stored when voting opened, against human votes only.
    engine = None
    if dv["prediction_id"]:
        pc = {r["iso3"]: r for r in rows(conn, "SELECT * FROM prediction_country WHERE prediction_id = ?", (dv["prediction_id"],))}
        pr = one(conn, "SELECT * FROM prediction WHERE id = ?", (dv["prediction_id"],))
        human = [v for v in votes if not v["computed"] and v["vote"] in VOTES and v["iso3"] in pc]
        if human:
            brier, ll, hit = 0.0, 0.0, 0
            for v in human:
                p = pc[v["iso3"]]
                probs = {"yes": p["p_yes"], "abstain": p["p_abstain"], "no": p["p_no"]}
                brier += sum((probs[k] - (1.0 if v["vote"] == k else 0.0)) ** 2 for k in VOTES)
                ll += -math.log(max(probs[v["vote"]], 1e-6))
                hit += int(max(VOTES, key=lambda k: (probs[k], k == "abstain")) == v["vote"])
            engine = {"n": len(human), "brier": brier / len(human), "log_loss": ll / len(human), "modal_hits": hit,
                      "p_pass": pr["p_pass"] if pr else None, "passed": bool(dv["passed"])}
    # Each student delegation: mandate fidelity (against the evidence-based prediction, with staff override, D-009),
    # coalition (winning side) and the delegate profile.
    overrides = {o["delegation_id"]: o for o in rows(conn, "SELECT * FROM fidelity_override WHERE division_id = ?", (division_id,))}
    winning = _winning_side(dv, rule)
    profiles = []
    pc = {r["iso3"]: r for r in rows(conn, "SELECT * FROM prediction_country WHERE prediction_id = ?", (dv["prediction_id"],))} \
        if dv["prediction_id"] else {}
    for v in votes:
        if v["computed"] or v["vote"] not in VOTES or not v["del_id"]:
            continue
        students = rows(conn, "SELECT st.first_name, st.last_initial FROM delegation_member dm JOIN student st ON st.id = dm.student_id "
                              "WHERE dm.delegation_id = ? AND dm.deleted_at IS NULL", (v["del_id"],))
        p = pc.get(v["iso3"])
        o = overrides.get(v["del_id"])
        if o:
            fid, why = ("consistent" if o["consistent"] else "inconsistent"), f"Staff judgement: {o['reason'] or 'no reason given'}"
        elif not p:
            fid, why = "unjudged", "No prediction was stored for this vote."
        elif p["unknown"]:
            fid, why = "unjudged", "No evidence about this country's position, so fidelity can't be judged."
        else:
            pv = {"yes": p["p_yes"], "abstain": p["p_abstain"], "no": p["p_no"]}[v["vote"]]
            fid = "consistent" if pv >= FIDELITY_OK else ("inconsistent" if pv < FIDELITY_LOW else "borderline")
            why = f"The evidence gave a {v['vote']} vote a {round(pv * 100)}% chance."
        coalition = "abstained" if v["vote"] == "abstain" else ("won" if v["vote"] == winning else "lost")
        profiles.append({"iso3": v["iso3"], "country": v["country"], "delegation_id": v["del_id"], "vote": v["vote"],
                         "students": [display_name(s["first_name"], s["last_initial"]) for s in students],
                         "fidelity": fid, "why": why, "coalition": coalition, "override": o,
                         "profile": delegate_profile(fid, coalition), "quality": quality.get(v["iso3"], "unknown")})
    wr = one(conn, "SELECT id FROM whip_round WHERE division_id = ?", (division_id,))
    return {"division": dv, "votes": votes, "pivotal": piv, "engine": engine, "profiles": profiles,
            "whip": whip_scores(conn, wr["id"]) if wr else None, "rule": rule}


def _winning_side(dv: dict, rule: VotingRule) -> str:
    return "yes" if dv["passed"] else "no"


PROFILES = {
    ("consistent", "won"): ("Statesman", "Moved the room without leaving your mandate. This is the job."),
    ("consistent", "lost"): ("Principled Isolate", "Your position held, but you didn't bring anyone with you."),
    ("consistent", "abstained"): ("Principled Isolate", "You held your position but stayed out of the result."),
    ("inconsistent", "won"): ("Gone Native", "You won the vote by voting against what the evidence says your country wants. Be ready to justify it."),
    ("inconsistent", "lost"): ("Passenger", "You were in the room but not in the negotiation."),
    ("inconsistent", "abstained"): ("Passenger", "You were in the room but not in the negotiation."),
}


def delegate_profile(fidelity: str, coalition: str) -> dict:
    """Feedback, not a grade (D-009, D-010). Borderline or unjudged fidelity says so instead of guessing."""
    if fidelity in ("unjudged", "borderline"):
        return {"name": "Not judged" if fidelity == "unjudged" else "Borderline",
                "line": "There isn't enough evidence to say whether this vote matched your mandate; your teacher can judge it."
                if fidelity == "unjudged" else "Your vote was plausible but not your country's most likely one. Can you explain why?"}
    name, line = PROFILES[(fidelity, coalition)]
    return {"name": name, "line": line}


def set_fidelity(w: Writer, division_id: int, delegation_id: int, consistent: bool, reason: str) -> None:
    w.conn.execute("INSERT INTO fidelity_override (division_id, delegation_id, consistent, reason, decided_by, decided_at) VALUES (?,?,?,?,?,?) "
                   "ON CONFLICT (division_id, delegation_id) DO UPDATE SET consistent = excluded.consistent, reason = excluded.reason, "
                   "decided_by = excluded.decided_by, decided_at = excluded.decided_at",
                   (division_id, delegation_id, int(consistent), (reason or "")[:300], w.actor.label, now_iso()))
    sid = scalar(w.conn, "SELECT session_id FROM division WHERE id = ?", (division_id,))
    w.log("fidelity_override", f"{division_id}:{delegation_id}", "decided", None, {"consistent": consistent}, ch(sid))


# ---------------- practice v3: a computed chamber ----------------

def _stance_bucket(x: float) -> int:
    return 2 if x >= 1.15 else 1 if x >= 0.4 else -2 if x <= -1.15 else -1 if x <= -0.4 else 0


def create_practice(w: Writer, owner_id: int, committee_id: int, paragraph_id: int, iso3: str) -> int:
    p = one(w.conn, "SELECT p.id, v.tags, r.committee_id FROM paragraph p JOIN paragraph_version v ON v.id = p.current_version_id "
                    "JOIN resolution r ON r.id = p.resolution_id WHERE p.id = ? AND p.deleted_at IS NULL", (paragraph_id,))
    if not p or p["committee_id"] != committee_id:
        raise UserError("Choose a paragraph from this committee.")
    if not one(w.conn, "SELECT 1 FROM delegation WHERE committee_id = ? AND iso3 = ? AND deleted_at IS NULL", (committee_id, iso3)):
        raise UserError("Choose a country that sits on this committee.")
    seed = random.SystemRandom().randrange(1, 2**31)
    pid = w.insert("sim_practice", {"owner_student_id": owner_id, "committee_id": committee_id, "paragraph_id": paragraph_id,
                                    "tags": p["tags"] or "", "seed": seed, "created_at": now_iso()})
    w.insert("sim_practice_member", {"practice_id": pid, "student_id": owner_id, "iso3": iso3})
    return pid


def add_member(w: Writer, practice: dict, student_id: int, iso3: str) -> None:
    if practice["stage"] != "lobbying":
        raise UserError("This practice has already voted.")
    if scalar(w.conn, "SELECT COUNT(*) FROM sim_practice_member WHERE practice_id = ?", (practice["id"],)) >= 3:
        raise UserError("Practice runs are for one to three students. Use a live session for bigger groups.")
    if not one(w.conn, "SELECT 1 FROM delegation WHERE committee_id = ? AND iso3 = ? AND deleted_at IS NULL", (practice["committee_id"], iso3)):
        raise UserError("Choose a country that sits on this committee.")
    try:
        w.insert("sim_practice_member", {"practice_id": practice["id"], "student_id": student_id, "iso3": iso3})
    except Exception:
        raise UserError("That student or country is already in this practice.")


def get_practice(conn, pid: int, student_id: int) -> dict:
    p = one(conn, "SELECT * FROM sim_practice WHERE id = ? AND deleted_at IS NULL", (pid,))
    if not p or not one(conn, "SELECT 1 FROM sim_practice_member WHERE practice_id = ? AND student_id = ?", (pid, student_id)):
        raise UserError("That practice isn't yours.", 403)
    return p


def _tags(p: dict) -> list[str]:
    return [t for t in (p["tags"] or "").split(",") if t.strip()]


def hidden_mandates(conn, p: dict, tags: list[str] | None = None) -> dict:
    """Each computed delegation's hidden position: the engine's mean for these tags plus one fixed draw of its
    uncertainty (bloc-correlated as in the engine), so it is consistent across amendments within a run.
    Only the class's own evidence is used, never practice readings."""
    from app.engine.model import distribution
    from app.modules.mun.predict import active_model, build_inputs, describe_target
    target = {**describe_target(conn, "paragraph", p["paragraph_id"]), "tags": tags if tags is not None else _tags(p)}
    _, params = active_model(conn)
    inputs, ctx = build_inputs(conn, target, params)
    rng = random.Random(p["seed"])
    groups: dict[str, float] = {}
    out = {}
    for ci in sorted(inputs, key=lambda c: c.iso3):
        d = distribution(ci, params)
        z = rng.gauss(0, 1)
        if ci.corr_group:
            g = groups.setdefault(ci.corr_group, random.Random(f"{p['seed']}:{ci.corr_group}").gauss(0, 1))
            rho = max(0.0, min(0.95, ci.rho))
            z = math.sqrt(rho) * g + math.sqrt(1 - rho) * z
        latent = d.mu + d.sigma * z
        vote = "yes" if latent > params.c_yes else "no" if latent < params.c_no else "abstain"
        out[ci.iso3] = {"latent": latent, "vote": vote, "bucket": _stance_bucket(latent), "name": ci.name}
    return out


def _lines(conn, iso3: str, topic_id: int | None) -> dict:
    a = one(conn, "SELECT ca.archetype_id FROM country_archetype ca WHERE ca.iso3 = ? AND ca.topic_id IS ? AND ca.deleted_at IS NULL "
                  "ORDER BY ca.weight DESC LIMIT 1", (iso3, topic_id))
    if not a:
        return {}
    return {r["stance"]: r["line"] for r in rows(conn, "SELECT stance, line FROM archetype_line WHERE archetype_id = ? AND deleted_at IS NULL",
                                                  (a["archetype_id"],))}


GENERIC_LINES = {
    2: "We are strongly in favour of this text and will say so on the floor.",
    1: "We can support this, though we would welcome some changes.",
    0: "We are still consulting our capital. We may abstain.",
    -1: "We have serious concerns about this text as drafted.",
    -2: "We cannot accept this. We will vote against it.",
}


def lobby(w: Writer, p: dict, student_id: int, iso3: str) -> int:
    """A simulated conversation: the delegation answers in character, from its hidden mandate."""
    if p["stage"] != "lobbying":
        raise UserError("This practice has already voted.")
    if one(w.conn, "SELECT 1 FROM sim_practice_member WHERE practice_id = ? AND iso3 = ?", (p["id"], iso3)):
        raise UserError("That delegation is played by a student in this practice. Talk to them instead.")
    used = scalar(w.conn, "SELECT COUNT(*) FROM sim_practice_lobby WHERE practice_id = ? AND student_id = ?", (p["id"], student_id))
    if used >= LOBBY_LIMIT:
        raise UserError(f"You've used all {LOBBY_LIMIT} conversations. Record what you think, then call the vote.")
    line = lobby_line(w.conn, p, iso3)
    return w.insert("sim_practice_lobby", {"practice_id": p["id"], "student_id": student_id, "iso3": iso3, "heard": line,
                                           "tags": p["tags"] or "", "created_at": now_iso()})


def record_reading(w: Writer, p: dict, student_id: int, lobby_id: int, position: int, note: str) -> None:
    row = one(w.conn, "SELECT * FROM sim_practice_lobby WHERE id = ? AND practice_id = ? AND student_id = ?", (lobby_id, p["id"], student_id))
    if not row:
        raise UserError("That conversation isn't yours.", 403)
    if position not in (-2, -1, 0, 1, 2):
        raise UserError("Choose a position from strongly oppose to strongly support.")
    w.conn.execute("UPDATE sim_practice_lobby SET position = ?, note = ? WHERE id = ?", (position, (note or "")[:300], lobby_id))


def amend(w: Writer, p: dict, tags: list[str]) -> None:
    if p["stage"] != "lobbying":
        raise UserError("This practice has already voted.")
    topic_id = scalar(w.conn, "SELECT topic_id FROM committee WHERE id = ?", (p["committee_id"],))
    allowed = {r["code"] for r in rows(w.conn, "SELECT code FROM tag WHERE topic_id IS ? AND deleted_at IS NULL", (topic_id,))}
    tags = [t for t in tags if t in allowed]
    if not tags:
        raise UserError("A paragraph needs at least one tag: choose what it commits countries to.")
    w.conn.execute("UPDATE sim_practice SET tags = ? WHERE id = ?", (",".join(tags), p["id"]))


def readings_as_sources(conn, p: dict) -> dict:
    """The students' recorded readings, as practice-only sources (weighted like class intel, labelled practice)."""
    from app.engine.model import Source
    from app.modules.mun.predict import active_model
    _, params = active_model(conn)
    w = scalar(conn, "SELECT weight FROM source_type WHERE code = 'student_intel'") or 2.0
    out: dict[str, list] = {}
    for r in rows(conn, "SELECT * FROM sim_practice_lobby WHERE practice_id = ? AND position IS NOT NULL ORDER BY id", (p["id"],)):
        out.setdefault(r["iso3"], []).append(Source(float(r["position"]), float(w), "student_intel", "Practice lobbying (your reading)",
                                                    f"practice:{r['id']}", False, r["note"]))
    return out


def practice_prediction(conn, p: dict) -> dict:
    from app.modules.mun.predict import run_prediction
    return run_prediction(conn, "paragraph", p["paragraph_id"], runs=2000, with_swing=True, seed=p["seed"],
                          tags_override=_tags(p), extra_sources=readings_as_sources(conn, p))


def set_member_vote(w: Writer, p: dict, student_id: int, vote: str) -> None:
    if vote not in VOTES:
        raise UserError("Vote Yes, No or Abstain.")
    w.conn.execute("UPDATE sim_practice_member SET vote = ? WHERE practice_id = ? AND student_id = ?", (vote, p["id"], student_id))


def practice_result(conn, p: dict, member_votes: dict, lobbies: list[dict], p_pass_before: float) -> dict:
    """The vote on a practice clause and its debrief, worked out without saving anything (single player for guests,
    D-099, uses it directly). `member_votes`: iso3 -> the players' own votes; `lobbies`: the conversations, each
    {iso3, heard, position (or None), note, tags (the clause's tags when it happened), student_id}."""
    original = one(conn, "SELECT v.tags FROM paragraph p JOIN paragraph_version v ON v.id = p.current_version_id WHERE p.id = ?",
                   (p["paragraph_id"],))["tags"] or ""
    now_m = hidden_mandates(conn, p)
    before_m = hidden_mandates(conn, p, [t for t in original.split(",") if t])
    votes = {iso: (member_votes.get(iso) or "abstain") if iso in member_votes else m["vote"] for iso, m in now_m.items()}
    c = one(conn, "SELECT * FROM committee WHERE id = ?", (p["committee_id"],))
    rule = _rule(conn, c["voting_rule_id"])
    out = tally(rule, votes, len(votes))
    # A reading is scored against the delegation's mandate when the conversation happened (the text may have been
    # amended since), and the debrief says if the amendment then moved that delegation.
    readings = []
    at_time: dict[str, dict] = {}
    for r in lobbies:
        tags_then = r.get("tags") or p["tags"] or ""
        then = at_time.setdefault(tags_then, hidden_mandates(conn, p, [t for t in tags_then.split(",") if t])).get(r["iso3"])
        truth = now_m.get(r["iso3"])
        pos = r.get("position")
        read_vote = None if pos is None else ("yes" if pos >= 1 else "no" if pos <= -1 else "abstain")
        readings.append({"iso3": r["iso3"], "country": truth["name"] if truth else r["iso3"], "heard": r.get("heard", ""),
                         "read": pos, "read_vote": read_vote, "student_id": r.get("student_id"),
                         "then_vote": then["vote"] if then else None, "actual_vote": truth["vote"] if truth else None,
                         "correct": None if read_vote is None or not then else read_vote == then["vote"],
                         "moved_after": bool(then and truth and then["vote"] != truth["vote"])})
    moved = [{"iso3": iso, "country": now_m[iso]["name"], "before": before_m[iso]["vote"], "after": now_m[iso]["vote"]}
             for iso in sorted(now_m) if iso in before_m and iso not in member_votes and before_m[iso]["vote"] != now_m[iso]["vote"]]
    names = {iso: m["name"] for iso, m in now_m.items()}
    piv = [{**x, "country": names.get(x["iso3"], x["iso3"])} for x in pivotal(rule, votes, len(votes))]
    return {"passed": out.passed, "summary": out.summary, "yes": out.yes, "no": out.no, "abstain": out.abstain,
            "vetoed_by": list(out.vetoed_by), "p_pass_before": p_pass_before, "readings": readings, "moved": moved,
            "pivotal": piv, "votes": votes, "rule": rule.name, "tags": _tags(p), "original_tags": original.split(",") if original else []}


def call_vote(w: Writer, p: dict, p_pass_before: float) -> dict:
    if p["stage"] != "lobbying":
        raise UserError("This practice has already voted.")
    members = {m["iso3"]: m["vote"] for m in rows(w.conn, "SELECT * FROM sim_practice_member WHERE practice_id = ?", (p["id"],))}
    lobbies = rows(w.conn, "SELECT * FROM sim_practice_lobby WHERE practice_id = ? ORDER BY id", (p["id"],))
    result = practice_result(w.conn, p, members, lobbies, p_pass_before)
    w.conn.execute("UPDATE sim_practice SET stage = 'voted', result_json = ? WHERE id = ?", (json.dumps(result), p["id"]))
    w.log("sim_practice", p["id"], "voted", None, {"passed": result["passed"]})
    return result


def lobby_line(conn, p: dict, iso3: str) -> str:
    """What a delegation says when lobbied: in character, from its hidden mandate on the clause as it now stands."""
    hm = hidden_mandates(conn, p).get(iso3)
    if not hm:
        raise UserError("That country isn't on this committee.")
    topic_id = scalar(conn, "SELECT topic_id FROM committee WHERE id = ?", (p["committee_id"],))
    return _lines(conn, iso3, topic_id).get(hm["bucket"]) or GENERIC_LINES[hm["bucket"]]


# ---------------- whip-count map (D-089) ----------------

def whip_map(conn, sid: int, reveal_only: bool = False) -> dict | None:
    """The class's whip count on the world map (D-089, D-090). Three phases:
    - "open": predictions are coming in; tokens show how many calls each country has, never which way (so the
      projector can't steer anyone's guess);
    - "locked": the vote is under way; countries show the class's most common prediction;
    - "revealed": the vote has closed; countries show the actual vote, tokens ringed green (called it) or red.
    Computed (engine) votes are marked *, as in the scores (D-061)."""
    from app.modules.mun import worldmap as WMAP
    r = one(conn, "SELECT * FROM whip_round WHERE session_id = ? AND status != 'cancelled' ORDER BY id DESC LIMIT 1", (sid,))
    if not r:
        return None
    dv = one(conn, "SELECT * FROM division WHERE id = ?", (r["division_id"],)) if r["division_id"] else None
    phase = "open" if r["status"] == "open" else ("revealed" if dv and dv["status"] == "closed" else "locked")
    if reveal_only and phase != "revealed":
        return None
    s = one(conn, "SELECT committee_id FROM live_session WHERE id = ?", (sid,))
    dels = _delegations(conn, s["committee_id"])
    counts: dict = {}
    for p in rows(conn, "SELECT delegation_id, vote FROM whip_prediction WHERE round_id = ? AND vote IS NOT NULL", (r["id"],)):
        counts.setdefault(p["delegation_id"], {"yes": 0, "abstain": 0, "no": 0})[p["vote"]] += 1
    actual = {v["delegation_id"]: v for v in rows(conn, "SELECT * FROM division_vote WHERE division_id = ?", (dv["id"],))} if dv else {}
    names = {"yes": "Yes", "no": "No", "abstain": "Abstain"}
    tiles, right, judged, values, labels = [], 0, 0, {}, {}
    for d in dels:
        c = counts.get(d["id"], {"yes": 0, "abstain": 0, "no": 0})
        n = sum(c.values())
        predicted = max(("yes", "abstain", "no"), key=lambda k: (c[k], k == "abstain")) if n else None
        a = actual.get(d["id"])
        vote = a["vote"] if a and a["vote"] in VOTES else None
        correct = (predicted == vote) if (phase == "revealed" and predicted and vote) else None
        if correct is not None:
            judged += 1
            right += int(correct)
        if phase == "open":
            labels[d["iso3"]] = f"{n} call{'' if n == 1 else 's'}" if n else ""
        elif phase == "locked" and predicted:
            values[d["iso3"]], labels[d["iso3"]] = predicted, names[predicted]
        elif phase == "revealed" and vote:
            values[d["iso3"]] = vote
            labels[d["iso3"]] = names[vote] + ("*" if a["computed"] else "")
        tiles.append({"iso3": d["iso3"], "name": d["name"], "n": n, "counts": c, "predicted": predicted, "actual": vote,
                      "computed": bool(a and a["computed"]), "students": d["students"], "correct": correct})
    wmap = WMAP.board(conn, [d["iso3"] for d in dels], mode="vote", values=values, labels=labels)
    judged_by = {t["iso3"]: t["correct"] for t in tiles}
    for t in wmap["tokens"]:
        if judged_by.get(t["iso3"]) is True:
            t["cls"] += " wm-right"
        elif judged_by.get(t["iso3"]) is False:
            t["cls"] += " wm-wrong"
    return {"round": r, "phase": phase, "tiles": sorted(tiles, key=lambda t: t["name"]), "wmap": wmap, "right": right,
            "judged": judged, "predicted_n": sum(1 for t in tiles if t["n"])}
