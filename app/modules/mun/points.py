"""Model UN contributions (D-096): every student starts each session at 0 and only counts up.

Ben chose "automatic + my awards": points are counted from what happens in the committee, grouped into four strands
that show students what a good delegate does, and the Chair can add +1 to +3 with a reason. The counted part is
worked out from the session's own records every time it is shown (like the debating ladder), so a withdrawn or
corrected action corrects itself. Rules:
  - points go to the student who acted (the speaker, the student who raised the point, the account in the change log
    for roll call, motions and amendments); co-delegates are counted separately; the engine and absent students earn
    nothing; casting the country's vote earns nothing (only the head of delegation can, D-088);
  - each kind of action has a cap, so the loudest student can't run away with it;
  - no leaderboard: a student sees only their own; the Chair sees everyone; the board shows nothing per student (D-091).
"""
from __future__ import annotations

from app.db import Writer, one, rows
from app.errors import UserError
from app.util import display_name, now_iso

STRANDS = {"speaking": "Speaking", "procedure": "Procedure", "negotiation": "Negotiation", "reading": "Reading the room"}
# code: (strand, what it was for, points each, most times it counts in a session)
RULES = {
    "roll": ("procedure", "Answered the roll", 1, 1),
    "speech": ("speaking", "Gave a speech", 2, 3),
    "point": ("speaking", "Raised a point the Chair took", 1, 2),
    "motion": ("procedure", "Proposed a motion the committee took up", 1, 2),
    "second": ("procedure", "Seconded a motion", 1, 2),
    "amend": ("negotiation", "Submitted an amendment", 2, 2),
    "sign": ("negotiation", "Signed an amendment", 1, 3),
    "adopted": ("negotiation", "Sponsored an amendment that was adopted", 2, 2),
    "whip": ("reading", "Called a country's vote correctly", 1, 5),
}
AWARD_MAX = 3


def _session(conn, sid: int) -> dict:
    s = one(conn, "SELECT id, committee_id, created_at, closed_at FROM live_session WHERE id = ?", (sid,))
    if not s:
        raise UserError("That session doesn't exist.", 404)
    return s


def _logged(conn, s: dict, entity: str, actions: tuple, id_like: str | None = None) -> list[dict]:
    """Change-log rows a student made on `entity` during the session."""
    acts = ",".join("?" * len(actions))
    q = (f"SELECT entity_id, actor_id FROM event_log WHERE entity = ? AND action IN ({acts}) AND actor_kind = 'student' "
         "AND actor_id IS NOT NULL AND at >= ? AND (? IS NULL OR at <= ?)")
    args = [entity, *actions, s["created_at"], s["closed_at"], s["closed_at"]]
    if id_like:
        q += " AND entity_id LIKE ?"
        args.append(id_like)
    return rows(conn, q + " ORDER BY seq", args)


def counted(conn, sid: int) -> dict[int, dict[str, int]]:
    """{student id: {rule code: times}} for the session, before caps."""
    s = _session(conn, sid)
    out: dict[int, dict[str, int]] = {}

    def add(student_id, code, n=1):
        if student_id:
            out.setdefault(student_id, {}).setdefault(code, 0)
            out[student_id][code] += n

    # Roll call: the student who answered for their country (not the engine, not the Chair).
    seen = set()
    for r in _logged(conn, s, "roll_call", ("answered",), f"{sid}:%"):
        if (r["actor_id"], r["entity_id"]) not in seen:
            seen.add((r["actor_id"], r["entity_id"]))
            add(r["actor_id"], "roll")
    for e in rows(conn, "SELECT student_id FROM speakers_list_entry WHERE session_id = ? AND status = 'done' AND student_id IS NOT NULL", (sid,)):
        add(e["student_id"], "speech")
    for p in rows(conn, "SELECT student_id FROM floor_point WHERE session_id = ? AND status IN ('answered', 'granted') "
                        "AND student_id IS NOT NULL", (sid,)):
        add(p["student_id"], "point")
    taken = {m["id"] for m in rows(conn, "SELECT id FROM motion WHERE session_id = ? AND status IN ('voting', 'passed', 'failed')", (sid,))}
    for r in _logged(conn, s, "motion", ("create",)):
        if int(r["entity_id"]) in taken:
            add(r["actor_id"], "motion")
    session_motions = {m["id"] for m in rows(conn, "SELECT id FROM motion WHERE session_id = ?", (sid,))}
    for r in _logged(conn, s, "motion", ("seconded",)):
        if int(r["entity_id"]) in session_motions:
            add(r["actor_id"], "second")
    # Amendments in this committee (drafts never count: only submitted ones, D-068).
    amends = {a["id"]: a for a in rows(conn, "SELECT a.id, a.status, a.submitted_at FROM amendment a JOIN paragraph p ON p.id = a.paragraph_id "
                                             "JOIN resolution r ON r.id = p.resolution_id WHERE r.committee_id = ? AND a.deleted_at IS NULL "
                                             "AND a.submitted_at IS NOT NULL", (s["committee_id"],))}
    from app.modules.mun.who import acted_by
    sponsors = acted_by(conn, "amendment", list(amends))          # the student who wrote it (from the change log)
    for aid, a in amends.items():
        if aid in sponsors and a["submitted_at"] >= s["created_at"] and (not s["closed_at"] or a["submitted_at"] <= s["closed_at"]):
            add(sponsors[aid], "amend")
    for aid, a in amends.items():
        if a["status"] in ("passed", "friendly") and aid in sponsors and _adopted_in(conn, s, aid):
            add(sponsors[aid], "adopted")
    supports = {x["id"] for x in rows(conn, "SELECT id FROM amendment_support WHERE kind = 'signatory' AND deleted_at IS NULL")}
    for r in _logged(conn, s, "amendment_support", ("create",)):
        if r["entity_id"].isdigit() and int(r["entity_id"]) in supports:
            add(r["actor_id"], "sign")
    # Whip calls: correct predictions of votes cast by students (engine votes don't count, D-061).
    from app.modules.sim.service import whip_scores
    for wr in rows(conn, "SELECT id FROM whip_round WHERE session_id = ? AND status = 'locked'", (sid,)):
        sc = whip_scores(conn, wr["id"])
        if sc["ready"]:
            for st in sc["students"]:
                add(st["student_id"], "whip", st["human_ok"])
    return out


def _adopted_in(conn, s: dict, amendment_id: int) -> bool:
    """Was this amendment adopted during the session (by vote or as friendly)?"""
    return bool(one(conn, "SELECT 1 FROM event_log WHERE entity = 'amendment' AND entity_id = ? AND at >= ? AND (? IS NULL OR at <= ?) "
                          "AND (after_json LIKE '%\"status\": \"passed\"%' OR after_json LIKE '%\"status\": \"friendly\"%' "
                          "OR after_json LIKE '%\"status\":\"passed\"%' OR after_json LIKE '%\"status\":\"friendly\"%')",
                    (str(amendment_id), s["created_at"], s["closed_at"], s["closed_at"])))


def awards(conn, sid: int, student_id: int | None = None) -> list[dict]:
    q = ("SELECT a.*, st.first_name, st.last_initial FROM mun_award a JOIN student st ON st.id = a.student_id "
         "WHERE a.session_id = ? AND a.deleted_at IS NULL")
    args: list = [sid]
    if student_id is not None:
        q += " AND a.student_id = ?"
        args.append(student_id)
    return rows(conn, q + " ORDER BY a.id", args)


def tally(conn, sid: int) -> dict[int, dict]:
    """{student id: {"total", "strands": {strand: points}, "earned": [(label, times, points)], "awards": [...]}} after caps."""
    out: dict[int, dict] = {}

    def entry(student_id):
        return out.setdefault(student_id, {"total": 0, "strands": {k: 0 for k in STRANDS}, "earned": [], "awards": []})

    for student_id, codes in counted(conn, sid).items():
        e = entry(student_id)
        for code, times in codes.items():
            strand, label, each, cap = RULES[code]
            n = min(times, cap)
            if n <= 0:
                continue
            e["strands"][strand] += n * each
            e["total"] += n * each
            e["earned"].append({"label": label, "times": n, "points": n * each, "strand": STRANDS[strand]})
    for a in awards(conn, sid):
        e = entry(a["student_id"])
        e["strands"][a["strand"]] += a["points"]
        e["total"] += a["points"]
        e["awards"].append(a)
    return out


def mine(conn, sid: int, student_id: int) -> dict:
    """One student's own contributions, from 0."""
    return tally(conn, sid).get(student_id) or {"total": 0, "strands": {k: 0 for k in STRANDS}, "earned": [], "awards": []}


def board(conn, sid: int) -> list[dict]:
    """The Chair's view: every student in the committee, including those on 0."""
    s = _session(conn, sid)
    t = tally(conn, sid)
    people = rows(conn, "SELECT st.id, st.first_name, st.last_initial, c.name AS country, d.id AS delegation_id FROM delegation_member dm "
                        "JOIN delegation d ON d.id = dm.delegation_id JOIN country c ON c.iso3 = d.iso3 JOIN student st ON st.id = dm.student_id "
                        "WHERE d.committee_id = ? AND dm.deleted_at IS NULL AND d.deleted_at IS NULL ORDER BY c.name, st.first_name",
                  (s["committee_id"],))
    return [{**p, "name": display_name(p["first_name"], p["last_initial"]),
             **(t.get(p["id"]) or {"total": 0, "strands": {k: 0 for k in STRANDS}, "earned": [], "awards": []})} for p in people]


def award(w: Writer, sid: int, student_id: int, strand: str, points: int, reason: str, channel: str = "") -> int:
    """The Chair adds +1 to +3 for something the records can't see ("brought a quiet bloc in")."""
    s = _session(w.conn, sid)
    if strand not in STRANDS:
        raise UserError("Choose a strand: speaking, procedure, negotiation or reading the room.")
    if not isinstance(points, int) or not 1 <= points <= AWARD_MAX:
        raise UserError(f"Award 1 to {AWARD_MAX} points.")
    reason = (reason or "").strip()
    if not reason:
        raise UserError("Say what the points are for: the student sees it.")
    if not one(w.conn, "SELECT 1 FROM delegation_member dm JOIN delegation d ON d.id = dm.delegation_id WHERE dm.student_id = ? "
                       "AND d.committee_id = ? AND dm.deleted_at IS NULL AND d.deleted_at IS NULL", (student_id, s["committee_id"])):
        raise UserError("That student isn't in this committee.", 404)
    return w.insert("mun_award", {"session_id": sid, "student_id": student_id, "strand": strand, "points": points,
                                  "reason": reason[:160], "entered_by": w.actor.label, "created_at": now_iso()}, channel)


def withdraw(w: Writer, sid: int, award_id: int, channel: str = "") -> None:
    a = one(w.conn, "SELECT * FROM mun_award WHERE id = ? AND session_id = ? AND deleted_at IS NULL", (award_id, sid))
    if not a:
        raise UserError("That award isn't in this session.", 404)
    w.soft_delete("mun_award", award_id, channel)
