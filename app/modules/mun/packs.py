"""Loads the v2 climate pack as a ready-made conference (used by demo mode and
available to the coordinator). Overrides become strong evidence items and
country facts become notes, all labelled 'Unsourced note' until a source is
attached (spec §11)."""
from __future__ import annotations

from app.db import Writer, one, scalar
from app.db.seed import PACK_ISO3, PACK_TOPIC, load_pack
from app.modules.mun import service

PACK_SOURCE = "v2 pack (src/pack_climate2026.js), hand-entered July 2026; source document not in the repo (audit §2)"

# Example amendments built from the v2 amendment types (tag change + text change).
EXAMPLE_AMENDMENTS = [("2.6", "review", "VUT"), ("2.1", "soften", "SAU"), ("2.2", "exempt", "IND")]


def amended_text(clause: dict, amendment: dict) -> str:
    op = amendment["textOp"]
    if op["type"] == "replaceVerb" and clause["text"].startswith(clause["verb"]):
        return op["with"] + clause["text"][len(clause["verb"]):]
    if op["type"] == "append":
        return clause["text"] + op["text"]
    return clause["text"]


def load_climate_conference(w: Writer, class_id: int | None = None, name_suffix: str = "") -> dict:
    pack = load_pack()
    topic_id = scalar(w.conn, "SELECT id FROM topic WHERE code = ?", (PACK_TOPIC,))
    ct = one(w.conn, "SELECT * FROM committee_type WHERE code = 'ga_plenary'")
    conf = service.create_conference(w, pack["meta"]["conference"] + name_suffix, organiser="UNAA Victoria",
                                     notes="Loaded from the v2 climate pack. Values are unsourced model estimates.")
    com = service.create_committee(w, conf, pack["meta"]["committee"], ct["id"], None, topic_id, class_id)
    isos = [PACK_ISO3[c["n"]] for c in pack["countries"]]
    dels = dict(zip(isos, service.add_delegations(w, com, isos)))
    res = service.create_resolution(w, com, pack["meta"]["title"])
    service.add_paragraph(w, res, "preambular", "Recognising that climate change is a common concern of humankind,")
    service.add_paragraph(w, res, "preambular", "Recalling the Paris Agreement and the goal of holding warming well below "
                                                "2°C above pre-industrial levels,")
    para_ids = {}
    for cl in pack["clauses"]:
        para_ids[cl["id"]] = service.add_paragraph(w, res, "operative", cl["text"], cl["tags"])
    for key, o in pack["overrides"].items():
        country, clause = key.split("|")
        service.add_evidence(w, subject_kind="country", iso3=PACK_ISO3[country], target_kind="paragraph",
                             target_id=para_ids[clause], position=o["s"], strength="strong", source=PACK_SOURCE,
                             source_type="unsourced_note", summary=o["line"])
    for c in pack["countries"]:
        service.add_evidence(w, subject_kind="country", iso3=PACK_ISO3[c["n"]], target_kind="topic", topic_id=topic_id,
                             position=None, source=PACK_SOURCE, source_type="unsourced_note",
                             summary="Country fact (unverified): " + c["fact"])
    amends = {a["id"]: a for a in pack["amendments"]}
    clauses = {c["id"]: c for c in pack["clauses"]}
    amendment_ids = []
    for clause_id, aid, sponsor in EXAMPLE_AMENDMENTS:
        a, cl = amends[aid], clauses[clause_id]
        tags = [t for t in cl["tags"] if t not in a["remove"]] + [t for t in a["add"] if t not in cl["tags"]]
        amendment_ids.append(service.table_amendment(w, para_ids[clause_id], "replace", amended_text(cl, a), tags,
                                                     dels[sponsor], rationale=a["detail"]))
    return {"conference_id": conf, "committee_id": com, "resolution_id": res, "paragraphs": para_ids,
            "delegations": dels, "amendments": amendment_ids}


# Security Council 2026 (Evatt-style practice). Elected members from memory of
# the 2025 and 2026 terms: verify before relying on it.
SC_2026 = ["CHN", "FRA", "RUS", "GBR", "USA", "DNK", "GRC", "PAK", "PAN", "SOM", "BHR", "COL", "COD", "LVA", "LBR"]


def load_security_council(w: Writer, class_id: int | None = None) -> dict:
    pack = load_pack()
    topic_id = scalar(w.conn, "SELECT id FROM topic WHERE code = ?", (PACK_TOPIC,))
    ct = one(w.conn, "SELECT * FROM committee_type WHERE code = 'sc'")
    conf = service.create_conference(w, "Evatt-style practice (Security Council)", organiser="South Oakleigh College",
                                     notes="Membership as remembered for 2026; check before use.")
    com = service.create_committee(w, conf, "Security Council", ct["id"], None, topic_id, class_id)
    dels = dict(zip(SC_2026, service.add_delegations(w, com, SC_2026)))
    res = service.create_resolution(w, com, "Climate-related security risks")
    paras = {}
    for cid in ("2.1", "2.6", "2.9"):
        cl = next(c for c in pack["clauses"] if c["id"] == cid)
        paras[cid] = service.add_paragraph(w, res, "operative", cl["text"], cl["tags"])
    return {"conference_id": conf, "committee_id": com, "resolution_id": res, "delegations": dels, "paragraphs": paras}
