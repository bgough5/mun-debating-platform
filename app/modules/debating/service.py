"""Debating module: events, teams, rooms, adjudicators, rounds and draws, ballots,
ladder and speaker tab, house points, run sheets and MC scripts, and practice.

Results are always recomputed from ballots, never stored separately, so a
corrected ballot fixes the ladder everywhere at once.
"""
from __future__ import annotations

import hashlib
import json
import random
import secrets

from jinja2.sandbox import SandboxedEnvironment

from app.db import Writer, one, rows, scalar
from app.engine import draw as D
from app.errors import UserError
from app.util import display_name, now_iso

TEMPLATE_ENV = SandboxedEnvironment(trim_blocks=True, lstrip_blocks=True)


def ch(event_id: int) -> str:
    return f"debate:{event_id}"


def get_event(conn, event_id: int) -> dict:
    e = one(conn, "SELECT e.*, f.name AS format_name, f.code AS format_code, f.speakers_per_team, f.reply, f.speech_seconds, "
                  "f.reply_seconds, f.prep_minutes, f.roles, r.name AS rubric_name FROM debate_event e "
                  "JOIN debate_format f ON f.id = e.format_id JOIN rubric r ON r.id = e.rubric_id WHERE e.id = ? AND e.deleted_at IS NULL",
            (event_id,))
    if not e:
        raise UserError("That debating event doesn't exist.", 404)
    return e


def _seed(*parts) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:8], 16)


# ---------- setup ----------

def create_event(w: Writer, name: str, kind: str, format_id: int, rubric_id: int | None = None, class_id: int | None = None,
                 starts_on: str = "", start_time: str = "09:00", seed: int | None = None) -> int:
    name = (name or "").strip()
    if not name:
        raise UserError("Give the event a name, e.g. “House Debating Carnival 2026”.")
    if kind not in ("carnival", "competition", "class", "practice"):
        raise UserError("Unknown event type.")
    if not one(w.conn, "SELECT 1 FROM debate_format WHERE id = ?", (format_id,)):
        raise UserError("Choose a debate format.")
    rubric_id = rubric_id or scalar(w.conn, "SELECT id FROM rubric WHERE kind = 'debate_speaker' AND deleted_at IS NULL ORDER BY id LIMIT 1")
    if not rubric_id:
        raise UserError("Add a debating rubric under Admin → Rubrics first.")
    return w.insert("debate_event", {"name": name, "kind": kind, "format_id": format_id, "rubric_id": rubric_id,
                                     "class_id": class_id, "starts_on": starts_on or "", "start_time": start_time or "09:00",
                                     "seed": seed if seed is not None else secrets.randbelow(2 ** 31),
                                     "projector_token": secrets.token_urlsafe(12)})


def add_team(w: Writer, event_id: int, name: str, house_id: int | None, student_ids: list[int], needs_accessible: bool = False) -> int:
    e = get_event(w.conn, event_id)
    name = (name or "").strip()
    if not name:
        raise UserError("Give the team a name.")
    if len(student_ids) > e["speakers_per_team"] + 1:
        raise UserError(f"A team in this format has {e['speakers_per_team']} speakers (plus one reserve at most).")
    for sid in student_ids:
        clash = one(w.conn, "SELECT t.name FROM team_member tm JOIN team t ON t.id = tm.team_id WHERE tm.student_id = ? "
                            "AND t.event_id = ? AND tm.deleted_at IS NULL AND t.deleted_at IS NULL", (sid, event_id))
        if clash:
            raise UserError(f"A student is already in the team “{clash['name']}” in this event.")
    tid = w.insert("team", {"event_id": event_id, "name": name[:80], "house_id": house_id,
                            "needs_accessible": int(bool(needs_accessible))}, ch(event_id))
    for pos, sid in enumerate(student_ids, 1):
        w.insert("team_member", {"team_id": tid, "student_id": sid, "position": pos}, ch(event_id))
    return tid


def auto_teams(w: Writer, event_id: int, student_ids: list[int], by_house: bool = True, size: int | None = None) -> int:
    """Make teams from students: one house per team (for house carnivals), seeded order.
    Leftovers become reserves (a 4th member) rather than being left out."""
    e = get_event(w.conn, event_id)
    size = size or e["speakers_per_team"]
    studs = rows(w.conn, f"SELECT st.id, st.first_name, st.house_id, h.name AS house FROM student st LEFT JOIN house h ON h.id = st.house_id "
                         f"WHERE st.id IN ({','.join('?' * len(student_ids)) or 'NULL'}) AND st.deleted_at IS NULL AND st.active = 1 ORDER BY st.id",
                 student_ids)
    taken = {r["student_id"] for r in rows(w.conn, "SELECT tm.student_id FROM team_member tm JOIN team t ON t.id = tm.team_id "
                                                   "WHERE t.event_id = ? AND tm.deleted_at IS NULL AND t.deleted_at IS NULL", (event_id,))}
    studs = [s for s in studs if s["id"] not in taken]
    groups: dict = {}
    for s in studs:
        groups.setdefault(s["house_id"] if by_house else 0, []).append(s)
    rng = random.Random(_seed(e["seed"], "teams"))
    made = 0
    existing = scalar(w.conn, "SELECT COUNT(*) FROM team WHERE event_id = ?", (event_id,)) or 0
    for key in sorted(groups, key=lambda k: (k is None, k)):
        members = groups[key]
        rng.shuffle(members)
        teams = [members[i:i + size] for i in range(0, len(members), size)]
        if len(teams) > 1 and len(teams[-1]) < size:
            # spread the short last group as reserves over the other teams
            short = teams.pop()
            for i, s in enumerate(short):
                teams[i % len(teams)].append(s)
        for t in teams:
            made += 1
            house = t[0]["house"] if by_house and t[0]["house"] else None
            label = f"{house} {made + existing}" if house else f"Team {made + existing}"
            add_team(w, event_id, label, t[0]["house_id"] if by_house else None, [s["id"] for s in t])
    return made


def add_rooms(w: Writer, event_id: int, names: list[str], accessible: bool = True) -> int:
    n = 0
    for i, nm in enumerate(names):
        nm = nm.strip()
        if nm:
            w.insert("room", {"event_id": event_id, "name": nm[:60], "accessible": int(accessible), "priority": 100 - i}, ch(event_id))
            n += 1
    return n


def add_adjudicator(w: Writer, event_id: int, name: str, rating: float = 5, house_id: int | None = None,
                    staff_id: int | None = None, student_id: int | None = None) -> int:
    name = (name or "").strip()
    if student_id and not name:
        st = one(w.conn, "SELECT first_name, last_initial FROM student WHERE id = ?", (student_id,))
        name = display_name(st["first_name"], st["last_initial"]) if st else ""
    if staff_id and not name:
        name = scalar(w.conn, "SELECT name FROM staff WHERE id = ?", (staff_id,)) or ""
    if not name:
        raise UserError("Give the adjudicator a name.")
    if not 0 <= rating <= 10:
        raise UserError("Rating is from 0 to 10.")
    return w.insert("adjudicator", {"event_id": event_id, "name": name[:60], "rating": rating, "house_id": house_id,
                                    "staff_id": staff_id, "student_id": student_id}, ch(event_id))


# ---------- results ----------

def criteria(conn, rubric_id: int) -> list[dict]:
    return rows(conn, "SELECT * FROM rubric_criterion WHERE rubric_id = ? AND deleted_at IS NULL ORDER BY position", (rubric_id,))


def pairing_result(conn, pairing_id: int) -> dict | None:
    """Panel decision: majority of ballots; an even split goes to the chair's ballot.
    Team scores and speaker scores are averaged over the ballots."""
    p = one(conn, "SELECT * FROM pairing WHERE id = ?", (pairing_id,))
    if not p or p["neg_team_id"] is None:
        return None
    bs = rows(conn, "SELECT b.*, pa.role FROM ballot b LEFT JOIN pairing_adjudicator pa ON pa.pairing_id = b.pairing_id "
                    "AND pa.adjudicator_id = b.adjudicator_id AND pa.deleted_at IS NULL WHERE b.pairing_id = ? AND b.deleted_at IS NULL "
                    "ORDER BY b.id", (pairing_id,))
    if not bs:
        return None
    votes = {p["aff_team_id"]: 0, p["neg_team_id"]: 0}
    for b in bs:
        votes[b["winner_team_id"]] = votes.get(b["winner_team_id"], 0) + 1
    if votes[p["aff_team_id"]] == votes[p["neg_team_id"]]:
        chair = next((b for b in bs if b["role"] == "chair"), bs[0])
        winner = chair["winner_team_id"]
    else:
        winner = max(votes, key=lambda t: votes[t])
    aff = sum(b["aff_total"] for b in bs) / len(bs)
    neg = sum(b["neg_total"] for b in bs) / len(bs)
    split = f"{max(votes.values())}–{min(votes.values())}" if len(bs) > 1 else "unanimous (single adjudicator)"
    return {"winner": winner, "loser": p["neg_team_id"] if winner == p["aff_team_id"] else p["aff_team_id"],
            "aff_total": aff, "neg_total": neg, "margin": abs(aff - neg), "ballots": len(bs), "split": split}


def team_states(conn, event_id: int, up_to_round: int | None = None) -> dict[int, D.TeamState]:
    e = get_event(conn, event_id)
    teams = {t["id"]: D.TeamState(t["id"], t["name"], t["house_id"], needs_accessible=bool(t["needs_accessible"]))
             for t in rows(conn, "SELECT * FROM team WHERE event_id = ? AND active = 1 AND deleted_at IS NULL", (event_id,))}
    q = ("SELECT p.*, r.number FROM pairing p JOIN debate_round r ON r.id = p.round_id WHERE r.event_id = ? AND p.deleted_at IS NULL "
         "AND r.deleted_at IS NULL")
    params: list = [event_id]
    if up_to_round is not None:
        q += " AND r.number < ?"
        params.append(up_to_round)
    for p in rows(conn, q, params):
        a = teams.get(p["aff_team_id"])
        if p["neg_team_id"] is None:
            if a:
                a.byes += 1
                if e["bye_counts_as_win"]:
                    a.wins += 1
            continue
        n = teams.get(p["neg_team_id"])
        if a:
            a.aff += 1
            a.opponents.add(p["neg_team_id"])
        if n:
            n.neg += 1
            n.opponents.add(p["aff_team_id"])
        res = pairing_result(conn, p["id"])
        if res and a and n:
            win, lose = teams.get(res["winner"]), teams.get(res["loser"])
            win.wins += 1
            a.points += res["aff_total"]
            n.points += res["neg_total"]
            win.margin += res["margin"]
            lose.margin -= res["margin"]
    return teams


def ladder(conn, event_id: int) -> list[dict]:
    states = team_states(conn, event_id)
    houses = {h["id"]: h["name"] for h in rows(conn, "SELECT id, name FROM house")}
    out = []
    for rank, t in enumerate(sorted(states.values(), key=D.rank_key), 1):
        out.append({"rank": rank, "team_id": t.id, "team": t.name, "house": houses.get(t.house, ""), "wins": t.wins,
                    "points": round(t.points, 1), "margin": round(t.margin, 1), "aff": t.aff, "neg": t.neg, "byes": t.byes})
    return out


def speaker_tab(conn, event_id: int) -> list[dict]:
    """Average total speaker score per student over the debates they spoke in (all ballots averaged per debate)."""
    rows_ = rows(conn, "SELECT bs.speaker_student_id AS sid, b.pairing_id, b.id AS ballot_id, SUM(bs.score) AS total "
                       "FROM ballot_score bs JOIN ballot b ON b.id = bs.ballot_id JOIN pairing p ON p.id = b.pairing_id "
                       "JOIN debate_round r ON r.id = p.round_id WHERE r.event_id = ? AND b.deleted_at IS NULL AND p.deleted_at IS NULL "
                       "AND bs.speaker_student_id IS NOT NULL GROUP BY bs.speaker_student_id, b.id", (event_id,))
    per: dict = {}
    for r in rows_:
        per.setdefault(r["sid"], {}).setdefault(r["pairing_id"], []).append(r["total"])
    names = {s["id"]: (display_name(s["first_name"], s["last_initial"]), s["house"]) for s in rows(
        conn, "SELECT st.id, st.first_name, st.last_initial, h.name AS house FROM student st LEFT JOIN house h ON h.id = st.house_id")}
    tab = []
    for sid, debates in per.items():
        avgs = [sum(v) / len(v) for v in debates.values()]
        tab.append({"student_id": sid, "name": names.get(sid, ("?", ""))[0], "house": names.get(sid, ("", ""))[1],
                    "debates": len(avgs), "average": round(sum(avgs) / len(avgs), 2)})
    tab.sort(key=lambda r: (-r["average"], -r["debates"], r["student_id"]))
    for i, r in enumerate(tab, 1):
        r["rank"] = i
    return tab


# ---------- rounds and draws ----------

def create_round(w: Writer, event_id: int, kind: str | None = None, motion: str = "", info: str = "") -> int:
    e = get_event(w.conn, event_id)
    n = (scalar(w.conn, "SELECT MAX(number) FROM debate_round WHERE event_id = ? AND deleted_at IS NULL", (event_id,)) or 0) + 1
    kind = kind or ("random" if n == 1 else "power")
    if kind not in ("random", "power"):
        raise UserError("A round is drawn at random or power-paired.")
    if scalar(w.conn, "SELECT COUNT(*) FROM team WHERE event_id = ? AND active = 1 AND deleted_at IS NULL", (event_id,)) < 2:
        raise UserError("Add at least two teams before drawing a round.")
    rid = w.insert("debate_round", {"event_id": event_id, "number": n, "kind": kind, "motion": (motion or "").strip()[:400],
                                    "info": (info or "")[:2000], "seed": _seed(e["seed"], "round", n), "created_at": now_iso()}, ch(event_id))
    if e["status"] == "setup":
        w.update("debate_event", event_id, {"status": "running"}, ch(event_id))
    return rid


def generate_draw(w: Writer, round_id: int) -> list[str]:
    r = one(w.conn, "SELECT * FROM debate_round WHERE id = ?", (round_id,))
    if not r:
        raise UserError("That round doesn't exist.", 404)
    if r["status"] != "draft":
        raise UserError("This round has been released. Undo the release before redrawing.")
    e = get_event(w.conn, r["event_id"])
    if r["kind"] == "power":
        prev = rows(w.conn, "SELECT p.id FROM pairing p JOIN debate_round dr ON dr.id = p.round_id WHERE dr.event_id = ? "
                            "AND dr.number < ? AND p.neg_team_id IS NOT NULL AND p.deleted_at IS NULL", (e["id"], r["number"]))
        missing = sum(1 for p in prev if not pairing_result(w.conn, p["id"]))
        if missing:
            raise UserError(f"{missing} debate(s) in earlier rounds have no ballot yet. Power pairing needs every result first.")
    states = team_states(w.conn, e["id"], up_to_round=r["number"])
    for old in rows(w.conn, "SELECT id FROM pairing WHERE round_id = ? AND deleted_at IS NULL", (round_id,)):
        w.soft_delete("pairing", old["id"], ch(e["id"]))
    pairs = D.make_draw(list(states.values()), r["kind"], r["seed"], bool(e["avoid_same_house"]))
    rooms = [D.Room(x["id"], bool(x["accessible"]), x["priority"]) for x in
             rows(w.conn, "SELECT * FROM room WHERE event_id = ? AND active = 1 AND deleted_at IS NULL", (e["id"],))]
    seen: dict[int, set] = {}
    for x in rows(w.conn, "SELECT pa.adjudicator_id, p.aff_team_id, p.neg_team_id FROM pairing_adjudicator pa JOIN pairing p ON p.id = pa.pairing_id "
                          "JOIN debate_round dr ON dr.id = p.round_id WHERE dr.event_id = ? AND dr.number < ? AND p.deleted_at IS NULL "
                          "AND pa.deleted_at IS NULL", (e["id"], r["number"])):
        seen.setdefault(x["adjudicator_id"], set()).update({x["aff_team_id"], x["neg_team_id"]})
    adjs = [D.Adj(x["id"], x["rating"], x["house_id"], seen.get(x["id"], set())) for x in
            rows(w.conn, "SELECT * FROM adjudicator WHERE event_id = ? AND active = 1 AND deleted_at IS NULL", (e["id"],))]
    problems = D.allocate_rooms(pairs, rooms, states) if rooms else ["No rooms set up: add rooms to allocate them."]
    problems += D.allocate_adjudicators(pairs, adjs, states) if adjs else ["No adjudicators set up yet."]
    for p in pairs:
        note = ("Rule relaxed: " + ", ".join(p.relaxed)) if p.relaxed else ""
        pid = w.insert("pairing", {"round_id": round_id, "aff_team_id": p.aff, "neg_team_id": p.neg, "room_id": p.room,
                                   "bracket": p.bracket, "position": p.position, "note": note}, ch(e["id"]))
        for adj_id, role in p.adjudicators:
            w.insert("pairing_adjudicator", {"pairing_id": pid, "adjudicator_id": adj_id, "role": role}, ch(e["id"]))
    w.log("debate_round", round_id, "draw_generated", None, {"pairings": len(pairs), "problems": problems}, ch(e["id"]))
    return problems + [f"Debate {p.position}: {', '.join(p.relaxed)} could not be avoided." for p in pairs if p.relaxed]


def round_draw(conn, round_id: int) -> list[dict]:
    ps = rows(conn, "SELECT p.*, ta.name AS aff, tn.name AS neg, ha.name AS aff_house, hn.name AS neg_house, rm.name AS room, "
                    "rm.accessible FROM pairing p JOIN team ta ON ta.id = p.aff_team_id LEFT JOIN team tn ON tn.id = p.neg_team_id "
                    "LEFT JOIN house ha ON ha.id = ta.house_id LEFT JOIN house hn ON hn.id = tn.house_id LEFT JOIN room rm ON rm.id = p.room_id "
                    "WHERE p.round_id = ? AND p.deleted_at IS NULL ORDER BY p.neg_team_id IS NULL, p.position", (round_id,))
    adj = {}
    for a in rows(conn, "SELECT pa.pairing_id, pa.role, a.name, a.id FROM pairing_adjudicator pa JOIN adjudicator a ON a.id = pa.adjudicator_id "
                        "JOIN pairing p ON p.id = pa.pairing_id WHERE p.round_id = ? AND pa.deleted_at IS NULL "
                        "ORDER BY pa.role = 'chair' DESC, a.name", (round_id,)):
        adj.setdefault(a["pairing_id"], []).append(a)
    nb = {r["pairing_id"]: r["n"] for r in rows(conn, "SELECT b.pairing_id, COUNT(*) AS n FROM ballot b JOIN pairing p ON p.id = b.pairing_id "
                                                      "WHERE p.round_id = ? AND b.deleted_at IS NULL GROUP BY b.pairing_id", (round_id,))}
    for p in ps:
        p["adjudicators"] = adj.get(p["id"], [])
        p["ballots"] = nb.get(p["id"], 0)
        p["result"] = pairing_result(conn, p["id"]) if p["ballots"] else None
    return ps


def set_round_status(w: Writer, round_id: int, status: str, motion_released: bool | None = None) -> None:
    r = one(w.conn, "SELECT * FROM debate_round WHERE id = ?", (round_id,))
    if not r:
        raise UserError("That round doesn't exist.", 404)
    if status not in ("draft", "released", "closed"):
        raise UserError("Unknown round status.")
    if status == "released" and not scalar(w.conn, "SELECT COUNT(*) FROM pairing WHERE round_id = ? AND deleted_at IS NULL", (round_id,)):
        raise UserError("Generate the draw before releasing the round.")
    changes = {"status": status}
    if motion_released is not None:
        changes["motion_released"] = int(motion_released)
    w.update("debate_round", round_id, changes, ch(r["event_id"]), action=f"round_{status}")


def swap_teams(w: Writer, pairing_a: int, team_a: int, pairing_b: int, team_b: int) -> None:
    """Manual draw edit: exchange two teams between debates (or sides within one)."""
    pa, pb = (one(w.conn, "SELECT p.*, r.status, r.event_id FROM pairing p JOIN debate_round r ON r.id = p.round_id WHERE p.id = ?", (x,))
              for x in (pairing_a, pairing_b))
    if not pa or not pb or pa["round_id"] != pb["round_id"]:
        raise UserError("Both debates must be in the same round.")
    if pa["status"] != "draft":
        raise UserError("Edit the draw before it is released.")

    def slot(p, t):
        if p["aff_team_id"] == t:
            return "aff_team_id"
        if p["neg_team_id"] == t:
            return "neg_team_id"
        raise UserError("That team isn't in that debate.")
    sa, sb = slot(pa, team_a), slot(pb, team_b)
    if pairing_a == pairing_b:
        w.update("pairing", pairing_a, {sa: team_b, sb: team_a}, ch(pa["event_id"]), action="draw_edit")
    else:
        w.update("pairing", pairing_a, {sa: team_b}, ch(pa["event_id"]), action="draw_edit")
        w.update("pairing", pairing_b, {sb: team_a}, ch(pa["event_id"]), action="draw_edit")


# ---------- ballots ----------

def submit_ballot(w: Writer, pairing_id: int, adjudicator_id: int | None, scores: dict, speakers: dict,
                  winner_team_id: int | None, comments: str = "", speaker_comments: dict | None = None) -> int:
    """scores: {(team_id, position): {criterion_id: score}}; speakers: {(team_id, position): student_id or None}.

    The winner is the team with the higher total. A drawn total is not allowed in
    schools debating: the adjudicator must say who won, and the ballot records it.
    """
    p = one(w.conn, "SELECT p.*, r.event_id, r.status AS round_status FROM pairing p JOIN debate_round r ON r.id = p.round_id WHERE p.id = ?",
            (pairing_id,))
    if not p or p["deleted_at"]:
        raise UserError("That debate doesn't exist.", 404)
    if p["neg_team_id"] is None:
        raise UserError("A bye has no ballot.")
    e = get_event(w.conn, p["event_id"])
    crit = {c["id"]: c for c in criteria(w.conn, e["rubric_id"])}
    n = e["speakers_per_team"]
    totals = {p["aff_team_id"]: 0.0, p["neg_team_id"]: 0.0}
    for team in totals:
        for pos in range(1, n + 1):
            sc = scores.get((team, pos))
            if not sc:
                raise UserError(f"Scores are missing for speaker {pos} of a team. Every speaker needs a score for every criterion.")
            for cid, c in crit.items():
                v = sc.get(cid)
                if v is None:
                    raise UserError(f"Give speaker {pos} a score for {c['name']}.")
                if not c["min_score"] <= v <= c["max_score"]:
                    raise UserError(f"{c['name']} scores must be between {c['min_score']:g} and {c['max_score']:g} (got {v:g}).")
                totals[team] += v * c["weight"]
    aff_t, neg_t = totals[p["aff_team_id"]], totals[p["neg_team_id"]]
    higher = p["aff_team_id"] if aff_t > neg_t else p["neg_team_id"] if neg_t > aff_t else None
    if higher is None:
        if winner_team_id not in totals:
            raise UserError("The totals are level. Choose the winning team: a debate can't be a draw.")
        higher = winner_team_id
    elif winner_team_id and winner_team_id != higher:
        raise UserError("The winner must be the team with the higher total. Check the scores, or change who won.")
    ev = ch(p["event_id"])
    for old in rows(w.conn, "SELECT id FROM ballot WHERE pairing_id = ? AND adjudicator_id IS ? AND deleted_at IS NULL", (pairing_id, adjudicator_id)):
        w.soft_delete("ballot", old["id"], ev)
    bid = w.insert("ballot", {"pairing_id": pairing_id, "adjudicator_id": adjudicator_id, "rubric_id": e["rubric_id"],
                              "winner_team_id": higher, "aff_total": aff_t, "neg_total": neg_t, "margin": abs(aff_t - neg_t),
                              "comments": (comments or "")[:4000], "entered_by": w.actor.label, "entered_at": now_iso()}, ev)
    for (team, pos), sc in scores.items():
        if team not in totals or pos > n:
            continue
        for cid, v in sc.items():
            w.conn.execute("INSERT INTO ballot_score (ballot_id, team_id, speaker_student_id, position, criterion_id, score, comment) "
                           "VALUES (?,?,?,?,?,?,?)", (bid, team, speakers.get((team, pos)), pos, cid, v,
                                                      ((speaker_comments or {}).get((team, pos)) or "")[:2000]))
    return bid


# ---------- house points ----------

def award_house_points(w: Writer, event_id: int, round_id: int | None = None, final: bool = False) -> int:
    """Create attributable entries from the rules (spec §8.4: reversible by staff). Idempotent per source."""
    rules = {r["code"]: r for r in rows(w.conn, "SELECT * FROM house_points_rule WHERE deleted_at IS NULL")}
    teams = {t["id"]: t for t in rows(w.conn, "SELECT * FROM team WHERE event_id = ?", (event_id,))}
    made = 0

    def add(house, pts, reason, kind, src):
        nonlocal made
        if not house or not pts:
            return
        # Already awarded, or awarded and then reversed by staff: a reversal is a decision, so never re-award it.
        if one(w.conn, "SELECT 1 FROM house_points_entry WHERE event_id = ? AND source_kind = ? AND source_id = ? AND house_id = ? "
                       "AND reverses_id IS NULL", (event_id, kind, src, house)):
            return
        w.insert("house_points_entry", {"event_id": event_id, "house_id": house, "points": pts, "reason": reason, "source_kind": kind,
                                        "source_id": src, "entered_by": w.actor.label, "created_at": now_iso()}, ch(event_id))
        made += 1

    if round_id:
        r = one(w.conn, "SELECT * FROM debate_round WHERE id = ? AND event_id = ?", (round_id, event_id))
        for p in rows(w.conn, "SELECT * FROM pairing WHERE round_id = ? AND deleted_at IS NULL", (round_id,)):
            if p["neg_team_id"] is None:
                continue
            res = pairing_result(w.conn, p["id"])
            if not res:
                continue
            for t in (p["aff_team_id"], p["neg_team_id"]):
                for code, r_ in rules.items():
                    if r_["kind"] == "participation":
                        add(teams[t]["house_id"], r_["points"], f"Round {r['number']}: {teams[t]['name']} debated", "participation", f"{p['id']}:{t}")
            win_house = teams[res["winner"]]["house_id"]
            for stale in rows(w.conn, "SELECT id FROM house_points_entry WHERE event_id = ? AND source_kind = 'win' AND source_id = ? "
                                      "AND house_id IS NOT ? AND reverses_id IS NULL AND reversed_by_id IS NULL",
                              (event_id, f"{p['id']}", win_house)):
                reverse_entry(w, stale["id"], "ballot corrected: the other team won")
            for code, r_ in rules.items():
                if r_["kind"] == "win":
                    add(teams[res["winner"]]["house_id"], r_["points"], f"Round {r['number']}: {teams[res['winner']]['name']} won",
                        "win", f"{p['id']}")
    if final:
        lad = ladder(w.conn, event_id)
        tab = speaker_tab(w.conn, event_id)
        for code, r_ in rules.items():
            if r_["kind"] == "team_place" and r_["place"] and len(lad) >= r_["place"]:
                row = lad[r_["place"] - 1]
                add(teams[row["team_id"]]["house_id"], r_["points"], f"{r_['label']}: {row['team']}", "team_place", f"{r_['place']}")
            if r_["kind"] == "speaker_place" and r_["place"] and len(tab) >= r_["place"]:
                row = tab[r_["place"] - 1]
                h = scalar(w.conn, "SELECT house_id FROM student WHERE id = ?", (row["student_id"],))
                add(h, r_["points"], f"{r_['label']}: {row['name']}", "speaker_place", f"{r_['place']}")
    return made


def reverse_entry(w: Writer, entry_id: int, reason: str = "") -> int:
    e = one(w.conn, "SELECT * FROM house_points_entry WHERE id = ?", (entry_id,))
    if not e or e["reversed_by_id"] or e["reverses_id"]:
        raise UserError("That entry can't be reversed (already reversed, or it is itself a reversal).")
    rid = w.insert("house_points_entry", {"event_id": e["event_id"], "house_id": e["house_id"], "points": -e["points"],
                                          "reason": f"Reversal of #{entry_id}" + (f": {reason}" if reason else ""), "source_kind": "reversal",
                                          "source_id": str(entry_id), "entered_by": w.actor.label, "created_at": now_iso(),
                                          "reverses_id": entry_id}, ch(e["event_id"]) if e["event_id"] else "")
    w.update("house_points_entry", entry_id, {"reversed_by_id": rid})
    return rid


def house_totals(conn, event_id: int | None = None) -> list[dict]:
    q = ("SELECT h.id, h.name, h.colour, COALESCE(SUM(e.points), 0) AS points FROM house h LEFT JOIN house_points_entry e "
         "ON e.house_id = h.id" + (" AND e.event_id = ?" if event_id else "") + " WHERE h.deleted_at IS NULL GROUP BY h.id "
         "ORDER BY points DESC, h.name")
    return rows(conn, q, (event_id,) if event_id else ())


# ---------- run sheet and MC script ----------

def _hhmm_add(start: str, minutes: int) -> str:
    try:
        h, m = (int(x) for x in start.split(":")[:2])
    except ValueError:
        h, m = 9, 0
    t = h * 60 + m + minutes
    return f"{(t // 60) % 24:02d}:{t % 60:02d}"


def document_context(conn, event_id: int) -> dict:
    e = get_event(conn, event_id)
    rounds = rows(conn, "SELECT * FROM debate_round WHERE event_id = ? AND deleted_at IS NULL ORDER BY number", (event_id,))
    for r in rounds:
        ps = rows(conn, "SELECT * FROM pairing WHERE round_id = ? AND deleted_at IS NULL", (r["id"],))
        r["pairings"] = [p for p in ps if p["neg_team_id"]]
        r["byes"] = sum(1 for p in ps if not p["neg_team_id"])
    teams = rows(conn, "SELECT * FROM team WHERE event_id = ? AND deleted_at IS NULL", (event_id,))
    house_ids = {t["house_id"] for t in teams if t["house_id"]}
    houses = [h for h in rows(conn, "SELECT * FROM house WHERE deleted_at IS NULL ORDER BY name") if h["id"] in house_ids]
    rooms = rows(conn, "SELECT * FROM room WHERE event_id = ? AND deleted_at IS NULL ORDER BY priority DESC, id", (event_id,))
    schedule, t = [], 0
    schedule.append({"time": _hhmm_add(e["start_time"], t), "what": "Arrival, house roll call and welcome", "who": "MC"})
    t += 15
    n_rounds = max(len(rounds), 1)
    for i in range(n_rounds):
        r = rounds[i] if i < len(rounds) else {"number": i + 1, "motion": ""}
        schedule.append({"time": _hhmm_add(e["start_time"], t), "what": f"Round {r['number']}: draw and motion announced", "who": "MC"})
        schedule.append({"time": _hhmm_add(e["start_time"], t + 5), "what": f"Round {r['number']}: preparation ({e['prep_minutes']} min)", "who": "Teams"})
        schedule.append({"time": _hhmm_add(e["start_time"], t + 5 + e["prep_minutes"]), "what": f"Round {r['number']}: debates", "who": "Adjudicators"})
        t += max(e["round_minutes"], e["prep_minutes"] + 25) + e["break_minutes"]
    schedule.append({"time": _hhmm_add(e["start_time"], t), "what": "Results, house points and close", "who": "MC"})
    totals = house_totals(conn, event_id)
    lad = ladder(conn, event_id) if rounds else []
    return {"event": e, "format": {"name": e["format_name"]}, "rounds": rounds, "teams": teams, "houses": houses, "rooms": rooms,
            "schedule": schedule, "ladder": lad, "house_totals": [h for h in totals if h["id"] in house_ids],
            "time_of_day": "morning" if e["start_time"] < "12:00" else "afternoon"}


def generate_document(conn, event_id: int, kind: str) -> str:
    code = {"run_sheet": "run_sheet", "mc_script": "mc_script"}[kind]
    body = scalar(conn, "SELECT body FROM template WHERE kind = ? AND deleted_at IS NULL ORDER BY id LIMIT 1", (code,))
    if not body:
        raise UserError(f"There is no {kind.replace('_', ' ')} template. Add one under Admin → Templates.")
    try:
        return TEMPLATE_ENV.from_string(body).render(**document_context(conn, event_id))
    except Exception as ex:      # a coordinator-edited template with a mistake
        raise UserError(f"The template has a mistake and couldn't be filled in: {ex}. Fix it under Admin → Templates.")


def save_document(w: Writer, event_id: int, kind: str, body: str, generated: bool) -> int:
    v = (scalar(w.conn, "SELECT MAX(version) FROM event_document WHERE event_id = ? AND kind = ?", (event_id, kind)) or 0) + 1
    return w.insert("event_document", {"event_id": event_id, "kind": kind, "version": v, "body": body, "generated": int(generated),
                                       "author": w.actor.label, "created_at": now_iso()}, ch(event_id))


# ---------- practice (1-3 students and whole classes) ----------

def create_practice(w: Writer, class_id: int, student_ids: list[int], motion: str = "") -> dict:
    """A practice event for the students present: format and roles fit the number (D-022)."""
    n = len(student_ids)
    if n == 0:
        raise UserError("Tick the students who are here.")
    plan = D.plan_practice(n)
    if plan[0]["format"] == "solo":
        return {"solo": True, "plan": plan}
    fmt = {f["speakers_per_team"]: f["id"] for f in rows(w.conn, "SELECT * FROM debate_format WHERE deleted_at IS NULL ORDER BY id")}
    size = max(r["aff"] for r in plan)
    fmt_id = fmt.get(size) or next(iter(fmt.values()))
    rng = random.Random(_seed(class_id, now_iso()[:16], n))
    order = list(student_ids)
    rng.shuffle(order)
    eid = create_event(w, f"Practice {now_iso()[:10]}", "practice", fmt_id, class_id=class_id)
    rid = None
    roles_out = []
    pos = 0
    for i, room in enumerate(plan, 1):
        aff = order[pos:pos + room["aff"]]
        pos += room["aff"]
        neg = order[pos:pos + room["neg"]]
        pos += room["neg"]
        adj = order[pos:pos + room["adjudicators"]]
        pos += room["adjudicators"]
        ta = add_team(w, eid, f"Room {i} Affirmative", None, aff)
        tn = add_team(w, eid, f"Room {i} Negative", None, neg)
        room_id = w.insert("room", {"event_id": eid, "name": f"Room {i}", "priority": 100 - i}, ch(eid))
        if rid is None:
            rid = w.insert("debate_round", {"event_id": eid, "number": 1, "kind": "random", "motion": motion[:400],
                                            "seed": _seed(eid, 1), "created_at": now_iso(), "status": "released",
                                            "motion_released": 1}, ch(eid))
        pid = w.insert("pairing", {"round_id": rid, "aff_team_id": ta, "neg_team_id": tn, "room_id": room_id, "position": i}, ch(eid))
        for sid in adj:
            aid = add_adjudicator(w, eid, "", 3, student_id=sid)
            w.insert("pairing_adjudicator", {"pairing_id": pid, "adjudicator_id": aid,
                                             "role": "chair" if sid == adj[0] else "trainee"}, ch(eid))
        roles_out.append({"room": i, "format": room["format"], "aff": aff, "neg": neg, "adjudicators": adj})
    w.update("debate_event", eid, {"status": "running"}, ch(eid))
    return {"solo": False, "event_id": eid, "round_id": rid, "plan": plan, "rooms": roles_out}


def save_practice_speech(w: Writer, student_id: int, rubric_id: int, topic: str, target_seconds: int, actual_seconds: int | None,
                         self_scores: dict, reflection: str, kind: str = "speech") -> int:
    crit = {c["id"]: c for c in criteria(w.conn, rubric_id)}
    clean = {}
    for cid, v in self_scores.items():
        c = crit.get(int(cid))
        if c and v not in (None, ""):
            v = float(v)
            if not c["min_score"] <= v <= c["max_score"]:
                raise UserError(f"{c['name']} is scored from {c['min_score']:g} to {c['max_score']:g}.")
            clean[str(cid)] = v
    return w.insert("practice_speech", {"student_id": student_id, "rubric_id": rubric_id, "topic": (topic or "")[:300], "kind": kind,
                                        "target_seconds": target_seconds, "actual_seconds": actual_seconds,
                                        "self_scores": json.dumps(clean), "reflection": (reflection or "")[:4000],
                                        "created_at": now_iso()})


# ---------- what a student sees ----------

def student_summary(conn, student_id: int) -> dict:
    """S-6: a student's own debates, scores against the rubric and practice. Never anyone else's scores."""
    debates = rows(conn, "SELECT e.name AS event, e.id AS event_id, r.number, r.motion, r.motion_released, r.status, p.id AS pairing_id, "
                         "t.name AS team, CASE WHEN p.aff_team_id = t.id THEN 'Affirmative' ELSE 'Negative' END AS side, rm.name AS room, "
                         "(SELECT name FROM team WHERE id = CASE WHEN p.aff_team_id = t.id THEN p.neg_team_id ELSE p.aff_team_id END) AS opponent "
                         "FROM team_member tm JOIN team t ON t.id = tm.team_id JOIN debate_event e ON e.id = t.event_id "
                         "JOIN debate_round r ON r.event_id = e.id JOIN pairing p ON p.round_id = r.id AND (p.aff_team_id = t.id OR p.neg_team_id = t.id) "
                         "LEFT JOIN room rm ON rm.id = p.room_id WHERE tm.student_id = ? AND tm.deleted_at IS NULL AND p.deleted_at IS NULL "
                         "AND r.status != 'draft' AND e.deleted_at IS NULL ORDER BY e.id DESC, r.number DESC LIMIT 20", (student_id,))
    scores = rows(conn, "SELECT rc.name, rc.max_score, AVG(bs.score) AS avg, COUNT(DISTINCT b.pairing_id) AS debates FROM ballot_score bs "
                        "JOIN ballot b ON b.id = bs.ballot_id JOIN rubric_criterion rc ON rc.id = bs.criterion_id "
                        "WHERE bs.speaker_student_id = ? AND b.deleted_at IS NULL GROUP BY rc.id ORDER BY rc.position", (student_id,))
    feedback = rows(conn, "SELECT DISTINCT bs.comment, r.number, e.name AS event FROM ballot_score bs JOIN ballot b ON b.id = bs.ballot_id "
                          "JOIN pairing p ON p.id = b.pairing_id JOIN debate_round r ON r.id = p.round_id JOIN debate_event e ON e.id = r.event_id "
                          "WHERE bs.speaker_student_id = ? AND bs.comment != '' AND b.deleted_at IS NULL ORDER BY b.id DESC LIMIT 5", (student_id,))
    practice = scalar(conn, "SELECT COUNT(*) FROM practice_speech WHERE student_id = ? AND deleted_at IS NULL", (student_id,))
    adjudicating = rows(conn, "SELECT p.id AS pairing_id, r.number, e.name AS event, rm.name AS room FROM adjudicator a "
                              "JOIN pairing_adjudicator pa ON pa.adjudicator_id = a.id JOIN pairing p ON p.id = pa.pairing_id "
                              "JOIN debate_round r ON r.id = p.round_id JOIN debate_event e ON e.id = r.event_id LEFT JOIN room rm ON rm.id = p.room_id "
                              "WHERE a.student_id = ? AND pa.deleted_at IS NULL AND p.deleted_at IS NULL AND r.status = 'released' "
                              "ORDER BY r.id DESC LIMIT 5", (student_id,))
    house = scalar(conn, "SELECT h.name FROM student st JOIN house h ON h.id = st.house_id WHERE st.id = ?", (student_id,))
    return {"debating": {"debates": debates, "scores": scores, "feedback": feedback, "practice": practice,
                         "adjudicating": adjudicating, "house": house}}
