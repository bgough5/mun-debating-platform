"""Seed reference data from the CSV/JSON files in app/db/seed/.

Reference data only: countries, blocs, rules, rubrics, templates, the v2
climate pack (every value labelled 'model estimate, unsourced'). No people.
"""
from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

from app.util import now_iso

SEED_DIR = Path(__file__).resolve().parent / "seed"
PACK_FILE = SEED_DIR / "legacy_pack_climate2026.json"
PACK_TOPIC = "climate2026"
UNSOURCED = "model estimate, unsourced (v2 pack, HANDOVER.md §12)"

# v2 pack country names -> ISO-3
PACK_ISO3 = {
    "Australia": "AUS", "Barbados": "BRB", "Brazil": "BRA", "Canada": "CAN", "Central African Republic": "CAF",
    "Chile": "CHL", "China": "CHN", "Costa Rica": "CRI", "Denmark": "DNK", "Egypt": "EGY", "Fiji": "FJI",
    "France": "FRA", "Gambia": "GMB", "Germany": "DEU", "Greece": "GRC", "India": "IND", "Japan": "JPN",
    "Kenya": "KEN", "Madagascar": "MDG", "Mexico": "MEX", "Mongolia": "MNG", "Morocco": "MAR",
    "Philippines": "PHL", "Saudi Arabia": "SAU", "South Africa": "ZAF", "Spain": "ESP", "Türkiye": "TUR",
    "Tuvalu": "TUV", "United Kingdom": "GBR", "United States of America": "USA", "Vanuatu": "VUT",
}


def _csv(name: str) -> list[dict]:
    with open(SEED_DIR / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _id(conn, table, code):
    r = conn.execute(f"SELECT id FROM {table} WHERE code = ?", (code,)).fetchone()
    return r[0] if r else None


def load_pack() -> dict:
    return json.loads(PACK_FILE.read_text(encoding="utf-8"))


def seed_reference(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT COUNT(*) FROM country").fetchone()[0]:
        return
    pack = load_pack()
    flags = {PACK_ISO3[n]: f["svg"] for n, f in pack["flags"].items()}
    for r in _csv("countries.csv"):
        conn.execute("INSERT INTO country (iso3, name, un_member, p5, region, flag_svg) VALUES (?,?,?,?,?,?)",
                     (r["iso3"], r["name"], int(r["un_member"]), int(r["p5"]), r["region"], flags.get(r["iso3"], "")))
    for r in _csv("blocs.csv"):
        conn.execute("INSERT INTO bloc (code, name, kind, cohesion, source, verified, notes) VALUES (?,?,?,?,?,?,?)",
                     (r["code"], r["name"], r["kind"], float(r["cohesion"]), r["source"], int(r["verified"]), r["notes"]))
    for r in _csv("bloc_members.csv"):
        conn.execute("INSERT INTO bloc_member (bloc_id, iso3, source) VALUES (?,?,?)",
                     (_id(conn, "bloc", r["bloc_code"]), r["iso3"], r["source"]))
    for r in _csv("voting_rules.csv"):
        conn.execute("INSERT INTO voting_rule (code, name, threshold_num, threshold_den, denominator, at_threshold, "
                     "min_yes, veto_iso3, notes) VALUES (?,?,?,?,?,?,?,?,?)",
                     (r["code"], r["name"], int(r["threshold_num"]), int(r["threshold_den"]), r["denominator"],
                      r["at_threshold"], int(r["min_yes"]), r["veto_iso3"], r["notes"]))
    for r in _csv("procedure_rule_sets.csv"):
        conn.execute("INSERT INTO procedure_rule_set (code, name, speaking_time_default, notes) VALUES (?,?,?,?)",
                     (r["code"], r["name"], int(r["speaking_time_default"]), r["notes"]))
    for r in _csv("procedure_motions.csv"):
        conn.execute("INSERT INTO procedure_motion (rule_set_id, code, name, precedence, voting_rule_id, needs_second, "
                     "has_duration, has_speaking_time, description) VALUES (?,?,?,?,?,?,?,?,?)",
                     (_id(conn, "procedure_rule_set", r["rule_set_code"]), r["code"], r["name"], int(r["precedence"]),
                      _id(conn, "voting_rule", r["voting_rule_code"]), int(r["needs_second"]), int(r["has_duration"]),
                      int(r["has_speaking_time"]), r["description"]))
    for r in _csv("committee_types.csv"):
        conn.execute("INSERT INTO committee_type (code, name, default_rule_id, default_procedure_id, notes) VALUES (?,?,?,?,?)",
                     (r["code"], r["name"], _id(conn, "voting_rule", r["default_rule_code"]),
                      _id(conn, "procedure_rule_set", r["default_procedure_code"]), r["notes"]))
    for r in _csv("source_types.csv"):
        conn.execute("INSERT INTO source_type (code, label, shown_as, weight, requires_source, notes) VALUES (?,?,?,?,?,?)",
                     (r["code"], r["label"], r["shown_as"], float(r["weight"]), int(r["requires_source"]), r["notes"]))
    for r in _csv("pathway_milestones.csv"):
        conn.execute("INSERT INTO pathway_milestone (code, name, track, position, description) VALUES (?,?,?,?,?)",
                     (r["code"], r["name"], r["track"], int(r["position"]), r["description"]))
    for rub in json.loads((SEED_DIR / "rubrics.json").read_text(encoding="utf-8")):
        cur = conn.execute("INSERT INTO rubric (code, name, kind, levels, notes) VALUES (?,?,?,?,?)",
                           (rub["code"], rub["name"], rub["kind"], rub["levels"], rub["notes"]))
        for pos, c in enumerate(rub["criteria"], 1):
            cc = conn.execute("INSERT INTO rubric_criterion (rubric_id, position, code, name, min_score, max_score, "
                              "weight, hint) VALUES (?,?,?,?,?,?,?,?)",
                              (cur.lastrowid, pos, c["code"], c["name"], c["min"], c["max"], c["weight"], c["hint"]))
            for lvl, text in enumerate(c["levels"], 1):
                conn.execute("INSERT INTO rubric_descriptor (criterion_id, level, descriptor) VALUES (?,?,?)",
                             (cc.lastrowid, lvl, text))
    for r in _csv("templates.csv"):
        body = (SEED_DIR / "templates" / r["file"]).read_text(encoding="utf-8")
        conn.execute("INSERT INTO template (code, kind, name, body) VALUES (?,?,?,?)", (r["code"], r["kind"], r["name"], body))
    mv = json.loads((SEED_DIR / "model_v2_default.json").read_text(encoding="utf-8"))
    conn.execute("INSERT INTO model_version (name, params_json, active, notes, created_at) VALUES (?,?,1,?,?)",
                 (mv["name"], json.dumps(mv["params"]), mv["notes"], now_iso()))
    _seed_pack(conn, pack)
    conn.commit()


def _table_exists(conn, name: str) -> bool:
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone())


def _empty(conn, table: str) -> bool:
    return _table_exists(conn, table) and not conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def seed_later_phases(conn: sqlite3.Connection) -> None:
    """Seeds for tables added by later migrations; runs on every start and fills only empty tables,
    so an existing database (e.g. the laptop's real data) gets them when it is upgraded."""
    if _empty(conn, "debate_format"):
        for r in _csv("debate_formats.csv"):
            conn.execute("INSERT INTO debate_format (code, name, speakers_per_team, reply, speech_seconds, reply_seconds, prep_minutes, "
                         "roles, notes) VALUES (?,?,?,?,?,?,?,?,?)", (r["code"], r["name"], int(r["speakers_per_team"]), int(r["reply"]),
                                                                       int(r["speech_seconds"]), int(r["reply_seconds"]),
                                                                       int(r["prep_minutes"]), r["roles"], r["notes"]))
    if _empty(conn, "house_points_rule"):
        for r in _csv("house_points_rules.csv"):
            conn.execute("INSERT INTO house_points_rule (code, label, kind, place, points) VALUES (?,?,?,?,?)",
                         (r["code"], r["label"], r["kind"], int(r["place"]) if r["place"] else None, float(r["points"])))
    if _empty(conn, "motion_bank"):
        for r in _csv("motion_bank.csv"):
            conn.execute("INSERT INTO motion_bank (motion, topic, level, source) VALUES (?,?,?,?)",
                         (r["motion"], r["topic"], r["level"], "Generic schools motion, written for the platform"))
    if _empty(conn, "data_source"):
        for r in _csv("data_sources.csv"):
            conn.execute("INSERT INTO data_source (code, name, url, licence_found, synthetic, attribution, notes) VALUES (?,?,?,?,?,?,?)",
                         (r["code"], r["name"], r["url"], r["licence_found"], int(r["synthetic"]), r["attribution"], r["notes"]))
    if _empty(conn, "history_tag_rule"):
        for r in _csv("history_tag_rules.csv"):
            tid = _id(conn, "topic", r["topic_code"])
            if tid:
                conn.execute("INSERT INTO history_tag_rule (topic_id, tag_code, keyword) VALUES (?,?,?)", (tid, r["tag_code"], r["keyword"]))
    if _empty(conn, "procedure_stage"):
        for r in _csv("procedure_stages.csv"):
            rs = _id(conn, "procedure_rule_set", r["rule_set"])
            if rs:
                conn.execute("INSERT INTO procedure_stage (rule_set_id, code, position, name, chair_script, chair_next, student_prompt) "
                             "VALUES (?,?,?,?,?,?,?)", (rs, r["code"], int(r["position"]), r["name"], r["chair_script"],
                                                         r["chair_next"], r["student_prompt"]))
    conn.commit()


def _seed_pack(conn, pack):
    cur = conn.execute("INSERT INTO topic (code, name, notes) VALUES (?,?,?)",
                       (PACK_TOPIC, pack["meta"]["title"],
                        "Carried over from the v2 pack. Every value is a model estimate, unsourced (spec §11)."))
    topic_id = cur.lastrowid
    tag_ids = {}
    for code, label in pack["tags"].items():
        tag_ids[code] = conn.execute("INSERT INTO tag (topic_id, code, label) VALUES (?,?,?)",
                                     (topic_id, code, label)).lastrowid
    for code, a in pack["archetypes"].items():
        aid = conn.execute("INSERT INTO archetype (code, name, blurb) VALUES (?,?,?)",
                           (code, a["name"], a["blurb"])).lastrowid
        for tag, val in a["affinity"].items():
            conn.execute("INSERT INTO archetype_affinity (archetype_id, tag_id, value, source) VALUES (?,?,?,?)",
                         (aid, tag_ids[tag], val, UNSOURCED))
        for stance, line in pack["lines"][code].items():
            conn.execute("INSERT INTO archetype_line (archetype_id, stance, line) VALUES (?,?,?)",
                         (aid, int(stance), line))
    # Blend order matters for bit-exact parity: insert in the pack's order.
    for c in pack["countries"]:
        for arch, wt in c["w"].items():
            conn.execute("INSERT INTO country_archetype (iso3, archetype_id, topic_id, weight, source) VALUES (?,?,?,?,?)",
                         (PACK_ISO3[c["n"]], _id(conn, "archetype", arch), topic_id, wt, UNSOURCED))
