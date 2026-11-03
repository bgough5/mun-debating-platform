"""A student's own country, always one click away on the live page (D-095).

Ben: students "should be able to togle up their countries alignments and information at will. it shouldn't just be
seen once". The live page has a "My country" panel above the tabs, on every tab, that opens and closes whenever the
student likes. It shows the flag, the UN regional group, a permanent seat, every grouping the country belongs to
(blocs and alliances, D-090) with the other countries in this room that share it, and the country's likely leanings
from its brief, labelled as estimates. Alignments are marked unchecked until someone checks them in Admin.
"""
from __future__ import annotations

from app.db import one, rows
from app.modules.mun import worldmap as WMAP


def card(conn, committee_id: int, iso3: str, topic_id: int | None = None) -> dict | None:
    c = one(conn, "SELECT iso3, name, p5, region, flag_svg FROM country WHERE iso3 = ?", (iso3,))
    if not c:
        return None
    room = {r["iso3"]: r["name"] for r in rows(conn, "SELECT d.iso3, c.name FROM delegation d JOIN country c ON c.iso3 = d.iso3 "
                                                     "WHERE d.committee_id = ? AND d.deleted_at IS NULL ORDER BY c.name", (committee_id,))}
    groups = []
    for g in WMAP.groupings(conn):
        if iso3 in g["members"]:
            allies = sorted(room[x] for x in g["members"] if x in room and x != iso3)
            groups.append({"code": g["code"], "name": g["name"], "kind": (g["kind"] or "").capitalize(), "verified": bool(g["verified"]),
                           "source": g.get("source") or "", "allies": allies})
    groups.sort(key=lambda g: (-len(g["allies"]), g["name"]))
    leanings = rows(conn, "SELECT a.name, a.blurb FROM country_archetype ca JOIN archetype a ON a.id = ca.archetype_id "
                          "WHERE ca.iso3 = ? AND (ca.topic_id IS ? OR ca.topic_id IS NULL) ORDER BY ca.weight DESC LIMIT 2",
                    (iso3, topic_id))
    return {**c, "region_name": WMAP.REGIONS.get(c["region"] or "", ""), "groups": groups, "leanings": leanings,
            "unchecked": any(not g["verified"] for g in groups),
            "shared": sorted({a for g in groups for a in g["allies"]})}
