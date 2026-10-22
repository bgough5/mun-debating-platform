"""Sponsor/second resolution, ported from v2 shared/engine.js (tallySponsorship,
resolveSponsorship). Parity-tested against fixtures generated from the JS.

Events are dicts: {seq, player, kind, payload}. Sponsoring is exclusive per
player (a later sponsorship replaces an earlier one); co-sponsorship is
allowed. A sponsor's own second doesn't count. Ties go to the candidate
sponsored first (lowest seq) — D-012.
"""
from __future__ import annotations


def tally(events: list[dict], sponsor_kind: str, second_kind: str, id_field: str) -> dict:
    sponsors_of: dict[str, set] = {}
    current: dict[str, str | None] = {}
    first_seq: dict[str, int] = {}
    seconds_of: dict[str, set] = {}
    for e in events:
        if e["kind"] == sponsor_kind:
            prev = current.get(e["player"])
            if prev and prev in sponsors_of:
                sponsors_of[prev].discard(e["player"])
            new = e["payload"].get(id_field) or None
            current[e["player"]] = new
            if new:
                sponsors_of.setdefault(new, set()).add(e["player"])
                first_seq.setdefault(new, e["seq"])
        elif e["kind"] == second_kind:
            cid = e["payload"].get(id_field)
            s = seconds_of.setdefault(cid, set())
            if e["payload"].get("seconded"):
                s.add(e["player"])
            else:
                s.discard(e["player"])
    return {"sponsors_of": sponsors_of, "current": current, "first_seq": first_seq, "seconds_of": seconds_of}


def resolve(events: list[dict], sponsor_kind: str, second_kind: str, id_field: str) -> str | None:
    t = tally(events, sponsor_kind, second_kind, id_field)
    sponsors_of, first_seq, seconds_of = t["sponsors_of"], t["first_seq"], t["seconds_of"]

    def effective(cid: str) -> int:
        return len([p for p in seconds_of.get(cid, set()) if p not in sponsors_of.get(cid, set())])

    # Iterate in the order candidates were first sponsored, as JS Object.keys does
    # for string keys inserted in that order.
    sponsored = [cid for cid in sponsors_of if sponsors_of[cid]]
    winner = None
    for cid in sponsored:
        if winner is None:
            winner = cid
            continue
        c, wc = effective(cid), effective(winner)
        if c > wc or (c == wc and first_seq[cid] < first_seq[winner]):
            winner = cid
    return winner
