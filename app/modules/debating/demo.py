"""Fake debating data for demo mode and tests: houses, a class event, and a 325-student carnival.

Every person here is generated (app/fakedata.py). Nothing is real.
"""
from __future__ import annotations

import random

from app.db import Writer, one, rows, scalar
from app.modules.debating import service as S

# South Oakleigh College's four houses, with the College's house colours (the College design system).
DEMO_HOUSES = [("ACA", "Acacia", "#D99E00"), ("GRE", "Grevillea", "#2563B5"), ("BAN", "Banksia", "#2E8B4A"), ("WAR", "Waratah", "#C8322B")]


def ensure_houses(w: Writer) -> list[int]:
    ids = []
    for code, name, colour in DEMO_HOUSES:
        h = one(w.conn, "SELECT id FROM house WHERE code = ?", (code,))
        ids.append(h["id"] if h else w.insert("house", {"code": code, "name": name, "colour": colour}, log=False))
    return ids


def assign_houses(w: Writer, student_ids: list[int], house_ids: list[int], rng: random.Random) -> None:
    for i, sid in enumerate(student_ids):
        w.conn.execute("UPDATE student SET house_id = ? WHERE id = ?", (house_ids[i % len(house_ids)], sid))


def populate_debating_demo(w: Writer, rng: random.Random, class_id: int, students: list[int]) -> dict:
    houses = ensure_houses(w)
    all_students = [r["id"] for r in rows(w.conn, "SELECT id FROM student ORDER BY id")]
    assign_houses(w, all_students, houses, rng)
    fmt = scalar(w.conn, "SELECT id FROM debate_format WHERE code = 'schools_3v3'")
    eid = S.create_event(w, "Year 8 class debates (demo)", "class", fmt, class_id=class_id, seed=8)
    S.auto_teams(w, eid, students[:18], by_house=False)
    S.add_rooms(w, eid, [f"Room {i}" for i in range(1, 4)])
    for i, name in enumerate(["Demo Chair", "Mr Adjudicator (demo)"]):
        S.add_adjudicator(w, eid, name, 7 - i)
    for sid in students[18:]:
        S.add_adjudicator(w, eid, "", 4, student_id=sid)       # two students adjudicate: a pathway step
    rid = S.create_round(w, eid, "random", "That homework should be banned in primary schools")
    S.generate_draw(w, rid)
    S.set_round_status(w, rid, "released", motion_released=True)
    simulate_ballots(w, rid, random.Random(81))
    return {"event_id": eid, "round_id": rid}


def simulate_ballots(w: Writer, round_id: int, rng: random.Random, strength: dict | None = None) -> int:
    """Fill every debate in a round with a plausible fake ballot (for demos and the carnival test)."""
    r = one(w.conn, "SELECT * FROM debate_round WHERE id = ?", (round_id,))
    e = S.get_event(w.conn, r["event_id"])
    crit = S.criteria(w.conn, e["rubric_id"])
    n = 0
    for p in rows(w.conn, "SELECT * FROM pairing WHERE round_id = ? AND deleted_at IS NULL AND neg_team_id IS NOT NULL", (round_id,)):
        adj = one(w.conn, "SELECT adjudicator_id FROM pairing_adjudicator WHERE pairing_id = ? AND role = 'chair' AND deleted_at IS NULL", (p["id"],))
        scores, speakers = {}, {}
        for team in (p["aff_team_id"], p["neg_team_id"]):
            members = [m["student_id"] for m in rows(w.conn, "SELECT student_id FROM team_member WHERE team_id = ? AND deleted_at IS NULL "
                                                            "ORDER BY position", (team,))]
            skill = (strength or {}).get(team, 0.5 + rng.random() * 0.3)
            for pos in range(1, e["speakers_per_team"] + 1):
                speakers[(team, pos)] = members[pos - 1] if pos - 1 < len(members) else None
                sc = {}
                for c in crit:
                    span = c["max_score"] - c["min_score"]
                    v = c["min_score"] + span * min(0.95, max(0.3, rng.gauss(skill, 0.08)))
                    sc[c["id"]] = round(v)
                scores[(team, pos)] = sc
        tot = {t: sum(sum(v.values()) for (tt, _), v in scores.items() if tt == t) for t in (p["aff_team_id"], p["neg_team_id"])}
        winner = p["aff_team_id"] if tot[p["aff_team_id"]] >= tot[p["neg_team_id"]] else p["neg_team_id"]
        S.submit_ballot(w, p["id"], adj["adjudicator_id"] if adj else None, scores, speakers, winner,
                        "Generated demo ballot.", {k: "Clear structure; work on rebuttal." for k in list(speakers)[:1]})
        n += 1
    return n


def make_carnival(w: Writer, n_students: int = 325, n_rounds: int = 4, seed: int = 325, rooms: int | None = None) -> dict:
    """A house debating carnival generated from fake data (spec Phase 3 exit: 325 students end to end)."""
    from app.fakedata import make_class
    rng = random.Random(seed)
    houses = ensure_houses(w)
    per_year = [n_students // 4 + (1 if i < n_students % 4 else 0) for i in range(4)]
    students: list[int] = []
    for i, n in enumerate(per_year):
        _, ids = make_class(w, f"Year {7 + i} carnival group (demo)", 2026, n, rng)
        students += ids
    assign_houses(w, students, houses, rng)
    fmt = scalar(w.conn, "SELECT id FROM debate_format WHERE code = 'schools_3v3'")
    eid = S.create_event(w, f"House Debating Carnival (demo, {n_students} students)", "carnival", fmt, seed=seed,
                         starts_on="2026-11-20", start_time="09:00")
    teams = S.auto_teams(w, eid, students, by_house=True)
    n_rooms = rooms or (teams + 1) // 2
    S.add_rooms(w, eid, [f"Room {i}" for i in range(1, n_rooms + 1)])
    for i in range(n_rooms + 6):        # staff and senior-student adjudicators (fake names)
        S.add_adjudicator(w, eid, f"Adjudicator {i + 1}", round(3 + rng.random() * 6, 1), houses[i % 4] if i % 3 == 0 else None)
    strength = {t["id"]: 0.45 + rng.random() * 0.4 for t in rows(w.conn, "SELECT id FROM team WHERE event_id = ?", (eid,))}
    motions = [m["motion"] for m in rows(w.conn, "SELECT motion FROM motion_bank WHERE level = 'junior' ORDER BY id LIMIT ?", (n_rounds,))]
    for r in range(n_rounds):
        rid = S.create_round(w, eid, None, motions[r % len(motions)] if motions else "")
        S.generate_draw(w, rid)
        S.set_round_status(w, rid, "released", motion_released=True)
        simulate_ballots(w, rid, rng, strength)
        S.award_house_points(w, eid, round_id=rid)
        S.set_round_status(w, rid, "closed")
    S.award_house_points(w, eid, final=True)
    w.update("debate_event", eid, {"status": "finished"})
    return {"event_id": eid, "students": len(students), "teams": teams, "rooms": n_rooms}
