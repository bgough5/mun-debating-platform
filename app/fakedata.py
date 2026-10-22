"""Fake-data generator. The ONLY source of people in development, tests and demo mode.

Names are drawn from a fixed list of common first names with a random last
initial; they are invented and seeded, so the same seed gives the same
people. No real student data is ever used (CLAUDE.md, spec §8.9).
"""
from __future__ import annotations

import random

from app.db import SYSTEM, Writer
from app.util import hash_passphrase, new_code, now_iso

FIRST_NAMES = [
    "Alex", "Sam", "Jordan", "Riley", "Charlie", "Taylor", "Jamie", "Casey", "Morgan", "Quinn", "Avery", "Harper",
    "Mia", "Noah", "Olivia", "Leo", "Isla", "Lucas", "Zara", "Ethan", "Chloe", "Oscar", "Ava", "Max", "Ruby",
    "Kai", "Layla", "Theo", "Aria", "Finn", "Ivy", "Hugo", "Nina", "Arlo", "Mila", "Eli", "Sana", "Ravi", "Mei",
    "Tariq", "Anika", "Dev", "Priya", "Omar", "Lina", "Hamish", "Grace", "Ben", "Lily", "Jack", "Emma", "Liam",
    "Sofia", "Henry", "Amelia", "Tom", "Ella", "Will", "Zoe", "Jai", "Maya", "Rohan", "Aisha", "Ken", "Yuki",
]
INITIALS = "ABCDEFGHJKLMNPRSTW"
DEMO_STAFF_PASSPHRASE = "demo-staff-only"   # demo dataset only; documented in the staff guide


def fake_people(rng: random.Random, n: int) -> list[tuple[str, str]]:
    """n (first_name, last_initial) pairs. The initial is only kept where two share a first name."""
    picks = [(rng.choice(FIRST_NAMES), rng.choice(INITIALS)) for _ in range(n)]
    counts: dict[str, int] = {}
    for f, _ in picks:
        counts[f] = counts.get(f, 0) + 1
    out, seen = [], set()
    for f, i in picks:
        if counts[f] > 1:
            while (f, i) in seen:
                i = rng.choice(INITIALS)
            seen.add((f, i))
            out.append((f, i))
        else:
            out.append((f, ""))
    return out


def make_class(w: Writer, name: str, year: int, n: int, rng: random.Random, code: str | None = None) -> tuple[int, list[int]]:
    cid = w.insert("class", {"name": name, "year": year, "code": code or new_code(), "code_set_at": now_iso()}, log=False)
    ids = []
    for f, i in fake_people(rng, n):
        ids.append(w.insert("student", {"class_id": cid, "first_name": f, "last_initial": i}, log=False))
    return cid, ids


def populate_demo(conn, seed: int = 2026) -> dict:
    """Demo dataset: fake classes, staff, a GA conference from the v2 pack and an SC practice committee."""
    from app.modules.mun import packs, service
    rng = random.Random(seed)
    conn.execute("BEGIN")
    w = Writer(conn, SYSTEM)
    try:
        info: dict = {}
        info["mun_class"], mun_students = make_class(w, "Year 9 Model UN (demo)", 2026, 25, rng, code="DEMO9M")
        info["small_class"], small = make_class(w, "Lunchtime MUN club (demo)", 2026, 3, rng, code="DEMO3C")
        info["debate_class"], debaters = make_class(w, "Year 8 Debating (demo)", 2026, 20, rng, code="DEMO8D")
        staff_id = w.insert("staff", {"name": "Demo Chair", "pass_hash": hash_passphrase(DEMO_STAFF_PASSPHRASE)}, log=False)
        for cid in (info["mun_class"], info["small_class"], info["debate_class"]):
            w.insert("staff_class", {"staff_id": staff_id, "class_id": cid}, log=False)
        ga = packs.load_climate_conference(w, info["mun_class"])
        service.allocate_round_robin(w, ga["committee_id"], mun_students)
        sc = packs.load_security_council(w, info["small_class"])
        service.allocate_round_robin(w, sc["committee_id"], small)
        info.update(ga=ga, sc=sc, staff_id=staff_id)
        try:
            from app.modules.debating.demo import populate_debating_demo
        except ImportError:
            populate_debating_demo = None
        if populate_debating_demo:
            info["debating"] = populate_debating_demo(w, rng, info["debate_class"], debaters)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return info
