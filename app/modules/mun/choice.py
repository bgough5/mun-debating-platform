"""How a committee's countries are given out (D-094).

Ben: "students should have the ability to pick which country they want to be if the chair allows it (or still be
random or assigned by chair)". The Chair picks the way when starting the activity, and can change it during the
session:
  - random: each student ticked for today is seated at random, filling empty countries first;
  - choose: students pick a country on their live page while the Chair keeps choosing open; closing it seats anyone
    who hasn't chosen at random;
  - chair: the Chair assigns countries on the committee page, as before.
A country can be held by up to CAP students (D-086: one to four is normal, and numbers needn't be even). The first
student to take a country is its head of delegation, who casts its vote (D-088).
"""
from __future__ import annotations

import random

from app.db import Writer, one, rows
from app.errors import UserError
from app.modules.mun.service import assign_member, committee_channel
from app.util import display_name

MODES = {"random": "At random", "choose": "Students choose", "chair": "The Chair assigns them"}
CAP = 4


def set_roster(w: Writer, committee_id: int, student_ids: list[int]) -> None:
    """Who is taking part today: they can open the session before they have a country."""
    have = {r["student_id"]: r for r in rows(w.conn, "SELECT * FROM committee_roster WHERE committee_id = ?", (committee_id,))}
    for sid in student_ids:
        r = have.get(sid)
        if r is None:
            w.insert("committee_roster", {"committee_id": committee_id, "student_id": sid}, committee_channel(committee_id))
        elif r["deleted_at"]:
            w.restore("committee_roster", r["id"], committee_channel(committee_id))


def on_roster(conn, committee_id: int, student_id: int) -> bool:
    return bool(one(conn, "SELECT 1 FROM committee_roster WHERE committee_id = ? AND student_id = ? AND deleted_at IS NULL",
                    (committee_id, student_id)))


def _seats(conn, committee_id: int) -> list[dict]:
    return rows(conn, "SELECT d.id, d.iso3, (SELECT COUNT(*) FROM delegation_member dm WHERE dm.delegation_id = d.id "
                      "AND dm.deleted_at IS NULL) AS n FROM delegation d WHERE d.committee_id = ? AND d.deleted_at IS NULL",
                (committee_id,))


def seated_ids(conn, committee_id: int) -> set[int]:
    return {r["student_id"] for r in rows(conn, "SELECT dm.student_id FROM delegation_member dm JOIN delegation d ON d.id = dm.delegation_id "
                                                "WHERE d.committee_id = ? AND dm.deleted_at IS NULL AND d.deleted_at IS NULL", (committee_id,))}


def allocate_random(w: Writer, committee_id: int, student_ids: list[int], rng: random.Random | None = None) -> int:
    """Seat each student who has no country yet at random, always into one of the emptiest countries."""
    rng = rng or random.Random()
    seats = _seats(w.conn, committee_id)
    if not seats:
        raise UserError("Add delegations before seating students.")
    taken = seated_ids(w.conn, committee_id)
    todo = [s for s in student_ids if s not in taken]
    rng.shuffle(todo)
    for sid in todo:
        low = min(d["n"] for d in seats)
        target = rng.choice([d for d in seats if d["n"] == low])
        assign_member(w, target["id"], sid, "head" if target["n"] == 0 else "delegate")
        target["n"] += 1
    return len(todo)


def set_mode(w: Writer, committee_id: int, mode: str, session_channel: str = "") -> None:
    if mode not in MODES:
        raise UserError("Choose how countries are given out: at random, students choose, or the Chair assigns them.")
    w.update("committee", committee_id, {"country_mode": mode, "choosing_open": 1 if mode == "choose" else 0},
             committee_channel(committee_id), action="country_mode")
    if session_channel:
        w.touch(session_channel)


def close_choosing(w: Writer, committee_id: int, session_channel: str = "") -> int:
    """Stop choosing; anyone on today's list who hasn't chosen is seated at random."""
    w.update("committee", committee_id, {"choosing_open": 0}, committee_channel(committee_id), action="choosing_closed")
    left = [r["student_id"] for r in rows(w.conn, "SELECT student_id FROM committee_roster WHERE committee_id = ? AND deleted_at IS NULL",
                                          (committee_id,))]
    n = allocate_random(w, committee_id, left)
    if session_channel:
        w.touch(session_channel)
    return n


def choose(w: Writer, committee_id: int, student_id: int, delegation_id: int, session_channel: str = "") -> str:
    """A student takes a country (or moves to another) while the Chair allows choosing."""
    c = one(w.conn, "SELECT country_mode, choosing_open FROM committee WHERE id = ?", (committee_id,))
    if not c or not c["choosing_open"]:
        raise UserError("Choosing countries is closed. Your teacher gives out the countries.", 409)
    d = one(w.conn, "SELECT d.id, d.iso3, c.name FROM delegation d JOIN country c ON c.iso3 = d.iso3 "
                    "WHERE d.id = ? AND d.committee_id = ? AND d.deleted_at IS NULL", (delegation_id, committee_id))
    if not d:
        raise UserError("That country isn't in this committee.", 404)
    members = rows(w.conn, "SELECT * FROM delegation_member WHERE delegation_id = ? AND deleted_at IS NULL ORDER BY id", (d["id"],))
    if any(m["student_id"] == student_id for m in members):
        return d["name"]
    if len(members) >= CAP:
        raise UserError(f"{d['name']} already has {CAP} delegates. Choose another country.", 409)
    old = one(w.conn, "SELECT dm.* FROM delegation_member dm JOIN delegation d ON d.id = dm.delegation_id WHERE dm.student_id = ? "
                      "AND d.committee_id = ? AND dm.deleted_at IS NULL AND d.deleted_at IS NULL", (student_id, committee_id))
    if old:
        w.soft_delete("delegation_member", old["id"], committee_channel(committee_id))
        if old["role"] == "head":                     # the next student holding that country leads it
            nxt = one(w.conn, "SELECT id FROM delegation_member WHERE delegation_id = ? AND deleted_at IS NULL ORDER BY id LIMIT 1",
                      (old["delegation_id"],))
            if nxt:
                w.update("delegation_member", nxt["id"], {"role": "head"}, committee_channel(committee_id))
    assign_member(w, d["id"], student_id, "head" if not members else "delegate")
    if session_channel:
        w.touch(session_channel)
    return d["name"]


def view(conn, committee_id: int) -> dict:
    """Everything the chooser and the Chair's card show; the same for every viewer (it goes in the shared session view)."""
    c = one(conn, "SELECT country_mode, choosing_open FROM committee WHERE id = ?", (committee_id,)) or {"country_mode": "chair", "choosing_open": 0}
    holders: dict = {}
    for m in rows(conn, "SELECT dm.delegation_id, dm.student_id, dm.role, st.first_name, st.last_initial FROM delegation_member dm "
                        "JOIN delegation d ON d.id = dm.delegation_id JOIN student st ON st.id = dm.student_id "
                        "WHERE d.committee_id = ? AND dm.deleted_at IS NULL AND d.deleted_at IS NULL ORDER BY dm.role = 'head' DESC, dm.id",
                  (committee_id,)):
        holders.setdefault(m["delegation_id"], []).append({"id": m["student_id"], "name": display_name(m["first_name"], m["last_initial"])})
    roster = rows(conn, "SELECT st.id, st.first_name, st.last_initial FROM committee_roster r JOIN student st ON st.id = r.student_id "
                        "WHERE r.committee_id = ? AND r.deleted_at IS NULL ORDER BY st.first_name", (committee_id,))
    seated = {h["id"] for hs in holders.values() for h in hs}
    return {"mode": c["country_mode"], "mode_name": MODES.get(c["country_mode"], ""), "open": bool(c["choosing_open"]), "cap": CAP,
            "holders": holders, "roster": len(roster),
            "waiting": [display_name(r["first_name"], r["last_initial"]) for r in roster if r["id"] not in seated]}


def options(conn, committee_id: int) -> list[dict]:
    """The countries to choose from, with what a student needs to choose well: flag, region, permanent seat and
    alignments (the same groupings as the map and the board, D-090/D-093)."""
    from app.modules.chair.board import BADGES, REGION_SHORT
    from app.modules.mun import worldmap as WMAP
    dels = rows(conn, "SELECT d.id, d.iso3, c.name, c.p5, c.region, c.flag_svg FROM delegation d JOIN country c ON c.iso3 = d.iso3 "
                      "WHERE d.committee_id = ? AND d.deleted_at IS NULL ORDER BY c.name", (committee_id,))
    groups = WMAP.groupings(conn)
    names = {code: label for code, _m, label in BADGES}
    out = []
    for d in dels:
        out.append({**d, "region_name": REGION_SHORT.get(d["region"] or "", ""),
                    "groups": [names.get(g["code"], g["name"]) for g in groups if d["iso3"] in g["members"] and g["code"] in names]})
    return out
