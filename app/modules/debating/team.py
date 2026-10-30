"""Debate teams (D-087): students on the same side of a class debate read each other's case and speech, read-only,
with an overview of everyone's arguments so the team doesn't double up.

A team is the side of a class debate (Ben, 30 Oct 2026: "Same side of a debate"). Each speaker's material is their
own prep case for that motion and side. Nobody can change a teammate's work: the team page has no forms, and every
edit route still checks the case belongs to the student editing it.
"""
from __future__ import annotations

import re

from app.db import one, rows
from app.errors import UserError
from app.util import display_name

ORDINAL = {1: "First", 2: "Second", 3: "Third", 4: "Fourth"}
STOP = set("""about above after again against because been before being below between both but could does doing down during each
few from further have having here into itself just more most must need only other ought over same should some such than that their
theirs them then there these they this those through under until very were what when where which while will with would your yours
also every many much make makes made more people thing things really because therefore however whether""".split())
OVERLAP = 0.34          # share of key words two arguments have in common before they're flagged


def _norm(motion: str) -> str:
    return re.sub(r"[\s.!?]+$", "", " ".join((motion or "").lower().split()))


def key_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", (text or "").lower()) if len(w) >= 4 and w not in STOP}


def similarity(a: str, b: str) -> float:
    ka, kb = key_words(a), key_words(b)
    return len(ka & kb) / len(ka | kb) if ka and kb else 0.0


def my_runs(conn, student_id: int, limit: int = 8) -> list[dict]:
    """Class debates where this student speaks on a side, newest first."""
    out = rows(conn, "SELECT r.id, r.title, r.motion, r.aff_name, r.neg_name, r.status, r.created_at, s.side FROM class_run_speaker s "
                     "JOIN class_run r ON r.id = s.run_id WHERE s.student_id = ? AND s.side IN ('aff', 'neg') AND s.deleted_at IS NULL "
                     "AND r.deleted_at IS NULL AND r.kind = 'debate' GROUP BY r.id ORDER BY r.id DESC LIMIT ?", (student_id, limit))
    for r in out:
        r["side_name"] = r[f"{r['side']}_name"]
        r["mates"] = one(conn, "SELECT COUNT(*) AS n FROM class_run_speaker WHERE run_id = ? AND side = ? AND student_id IS NOT NULL "
                               "AND student_id != ? AND deleted_at IS NULL", (r["id"], r["side"], student_id))["n"]
    return out


def team_for_case(conn, student_id: int, case: dict) -> dict | None:
    """The newest class debate on this case's motion where the student is on the case's side, if any."""
    for r in my_runs(conn, student_id, limit=30):
        if r["side"] == case["side"] and _norm(r["motion"]) == _norm(case["motion"]):
            return {"run_id": r["id"], "mates": r["mates"]}
    return None


def _case_of(conn, student_id: int, motion: str, side: str) -> dict | None:
    for c in rows(conn, "SELECT * FROM prep_case WHERE student_id = ? AND side = ? AND deleted_at IS NULL ORDER BY updated_at DESC",
                  (student_id, side)):
        if _norm(c["motion"]) == _norm(motion):
            return c
    return None


def team_view(conn, student_id: int, run_id: int) -> dict:
    run = one(conn, "SELECT * FROM class_run WHERE id = ? AND deleted_at IS NULL AND kind = 'debate'", (run_id,))
    if not run:
        raise UserError("That debate doesn't exist.", 404)
    me = one(conn, "SELECT side FROM class_run_speaker WHERE run_id = ? AND student_id = ? AND side IN ('aff', 'neg') "
                   "AND deleted_at IS NULL", (run_id, student_id))
    if not me:
        raise UserError("You aren't speaking in that debate, so its team page isn't yours to open.", 403)
    side = me["side"]
    from app.modules.debating import prep as P
    members = []
    for sp in rows(conn, "SELECT s.*, st.first_name, st.last_initial FROM class_run_speaker s LEFT JOIN student st ON st.id = s.student_id "
                         "WHERE s.run_id = ? AND s.side = ? AND s.deleted_at IS NULL ORDER BY s.position", (run_id, side)):
        m = {"position": sp["position"], "role": f"{ORDINAL.get(sp['position'], str(sp['position']))} speaker",
             "name": display_name(sp["first_name"], sp["last_initial"]) if sp["first_name"] else (sp["name"] or "Not chosen yet"),
             "student_id": sp["student_id"], "me": sp["student_id"] == student_id, "case": None, "arguments": [], "rebuttals": []}
        case = _case_of(conn, sp["student_id"], run["motion"], side) if sp["student_id"] else None
        if case:
            v = P.case_view(conn, case)
            m["case"] = case
            m["arguments"] = [{"claim": p["parts_d"].get("claim", ""), "parts": p["parts_d"]} for p in v["arguments"]]
            m["rebuttals"] = [p["parts_d"].get("they_say", "") for p in v["custom"]] + \
                             [a["argument"] for a in v["opposition"] if a.get("rebuttal")]
            m["words"] = P.words(case["speech_text"])
        members.append(m)
    # Arguments from different speakers that share many key words: worth a conversation, not proof of a double-up.
    overlaps = []
    for i, a in enumerate(members):
        for b in members[i + 1:]:
            for x in a["arguments"]:
                for y in b["arguments"]:
                    tx = " ".join((x["parts"].get("claim", ""), x["parts"].get("reason", "")))
                    ty = " ".join((y["parts"].get("claim", ""), y["parts"].get("reason", "")))
                    if similarity(tx, ty) >= OVERLAP:
                        overlaps.append({"a": a["name"], "a_claim": x["claim"], "b": b["name"], "b_claim": y["claim"]})
    mine = next((m for m in members if m["me"]), None)
    return {"run": run, "side": side, "side_name": run[f"{side}_name"], "members": members, "overlaps": overlaps,
            "my_case": mine["case"] if mine else None}
