"""Model UN scenario packs as data files (D-097).

A pack is one JSON file in app/db/seed/packs/ (format 1, documented in docs/pack-authoring.md, with a blank
_template.json beside it). `validate()` checks a pack against every rule before it can be used; `install()` turns a
valid pack into a committee: topic and tags, conference, committee, delegations, a draft resolution, the countries'
positions as evidence, and breaking news for a fictional crisis. Packs are written by people and by other models, so
everything in them is treated as untrusted text: it is length-limited, never markup, and positions are always labelled
(a fictional crisis: "Unverified demo", never a real position; a real topic: an estimate with a source, or left out).
"""
from __future__ import annotations

import csv
import functools
import json
import re
from pathlib import Path

from app.db import Writer, one, rows, scalar
from app.errors import UserError

PACK_DIR = Path(__file__).resolve().parents[2] / "db" / "seed" / "packs"
COUNTRIES_CSV = Path(__file__).resolve().parents[2] / "db" / "seed" / "countries.csv"
FORMAT = 1
CODE = re.compile(r"^[a-z0-9_]{3,40}$")
TAG = re.compile(r"^[a-z][a-z0-9_]{1,30}$")
TOPIC_CODE = re.compile(r"^[A-Z][A-Z0-9_]{2,40}$")
URL = re.compile(r"^https?://\S+$")
LEVELS = ("junior", "middle", "senior")
COMMITTEE_TYPES = ("sc", "ga_plenary", "ga_third")
P5 = {"CHN", "FRA", "GBR", "RUS", "USA"}
UNVERIFIED = ("Invented for a practice scenario about a fictional country. This is not {name}'s real position on any issue; "
              "research the real position before using it.")
ESTIMATE = "Estimated for a practice pack from the source given, not {name}'s stated position. Check it before relying on it."


@functools.lru_cache(maxsize=1)
def un_members() -> dict:
    with COUNTRIES_CSV.open(encoding="utf-8") as f:
        return {r["iso3"]: r["name"] for r in csv.DictReader(f)}


def _text(v, field: str, lo: int, hi: int, errors: list) -> str:
    if not isinstance(v, str) or not v.strip():
        errors.append(f"{field}: missing.")
        return ""
    v = v.strip()
    if not lo <= len(v) <= hi:
        errors.append(f"{field}: {len(v)} characters; it must be {lo} to {hi}.")
    if "<" in v or ">" in v:
        errors.append(f"{field}: no markup (< or >) allowed.")
    if re.search(r"https?://", v) and not field.startswith("sources"):
        errors.append(f"{field}: no links in the text; put sources under \"sources\".")
    return v


def source_links(s) -> list[str]:
    """A country's sources: one link, or a list of up to four (one page rarely covers every clause)."""
    links = s if isinstance(s, list) else [s] if s else []
    return [x for x in links if isinstance(x, str) and URL.match(x)][:4]


def validate(pack: dict, filename_code: str | None = None) -> list[str]:
    """Every problem with a pack, in plain words (empty when it can be used)."""
    e: list[str] = []
    if not isinstance(pack, dict):
        return ["The pack must be one JSON object."]
    if pack.get("format") != FORMAT:
        e.append(f"format: must be {FORMAT}.")
    code = pack.get("code")
    if not isinstance(code, str) or not CODE.match(code):
        e.append("code: 3 to 40 lowercase letters, digits or underscores.")
    elif filename_code and code != filename_code:
        e.append(f"code: \"{code}\" must match the file name ({filename_code}.json).")
    _text(pack.get("title"), "title", 5, 120, e)
    _text(pack.get("summary"), "summary", 20, 300, e)
    if pack.get("level") not in LEVELS:
        e.append(f"level: one of {', '.join(LEVELS)}.")
    fictional = pack.get("fictional")
    if not isinstance(fictional, bool):
        e.append("fictional: true or false.")
    com = pack.get("committee") or {}
    if com.get("type") not in COMMITTEE_TYPES:
        e.append(f"committee.type: one of {', '.join(COMMITTEE_TYPES)}.")
    _text(com.get("name"), "committee.name", 5, 120, e)
    _text(com.get("conference"), "committee.conference", 5, 120, e)
    if com.get("notes") is not None:
        _text(com.get("notes"), "committee.notes", 0, 400, e)
    topic = pack.get("topic") or {}
    if not isinstance(topic.get("code"), str) or not TOPIC_CODE.match(topic.get("code", "")):
        e.append("topic.code: 3 to 41 capitals, digits or underscores, starting with a letter (e.g. SC_VELORIA).")
    _text(topic.get("name"), "topic.name", 5, 160, e)
    tags = pack.get("tags")
    if not isinstance(tags, dict) or not 2 <= len(tags) <= 12:
        e.append("tags: 2 to 12 of them, as {\"code\": \"what a clause with this tag does\"}.")
        tags = {}
    for t, label in tags.items():
        if not TAG.match(t):
            e.append(f"tags.{t}: a code is 2 to 31 lowercase letters, digits or underscores, starting with a letter.")
        _text(label, f"tags.{t}", 5, 80, e)
    members = un_members()
    countries = pack.get("countries")
    if not isinstance(countries, list) or not 2 <= len(countries or []) <= 60:
        e.append("countries: a list of 2 to 60 ISO-3 codes.")
        countries = []
    if len(set(countries)) != len(countries):
        e.append("countries: a country is listed twice.")
    for c in countries:
        if c not in members:
            e.append(f"countries: {c} isn't a country the platform knows (use ISO-3 codes from app/db/seed/countries.csv).")
    if com.get("type") == "sc" and (len(countries) != 15 or not P5 <= set(countries)):
        e.append("countries: a Security Council has exactly 15 members, including CHN, FRA, GBR, RUS and USA.")
    res = pack.get("resolution") or {}
    _text(res.get("title"), "resolution.title", 5, 160, e)
    for kind, lo, hi, ends in (("preambular", 1, 8, (",",)), ("operative", 2, 12, (";", "."))):
        clauses = res.get(kind)
        if not isinstance(clauses, list) or not lo <= len(clauses) <= hi:
            e.append(f"resolution.{kind}: {lo} to {hi} clauses.")
            continue
        for i, cl in enumerate(clauses, 1):
            text = _text((cl or {}).get("text"), f"resolution.{kind}[{i}].text", 20, 400, e)
            if text and not text.endswith(ends):
                e.append(f"resolution.{kind}[{i}].text: a {kind} clause ends with {' or '.join(ends)}")
            ctags = (cl or {}).get("tags", [])
            if not isinstance(ctags, list) or (kind == "operative" and not ctags):
                e.append(f"resolution.{kind}[{i}].tags: a list of tag codes{' (at least one)' if kind == 'operative' else ''}.")
                ctags = []
            for t in ctags:
                if t not in tags:
                    e.append(f"resolution.{kind}[{i}].tags: \"{t}\" isn't one of the pack's tags.")
    positions = pack.get("positions") or {}
    if not isinstance(positions, dict):
        e.append("positions: {\"ISO3\": {\"tag\": -2 to 2}}.")
        positions = {}
    sources = pack.get("sources") or {}
    for iso, pos in positions.items():
        if iso not in countries:
            e.append(f"positions.{iso}: not one of the pack's countries.")
        if not isinstance(pos, dict):
            e.append(f"positions.{iso}: {{\"tag\": -2 to 2}}.")
            continue
        for t, v in pos.items():
            if t not in tags:
                e.append(f"positions.{iso}.{t}: not one of the pack's tags.")
            if not isinstance(v, int) or isinstance(v, bool) or not -2 <= v <= 2:
                e.append(f"positions.{iso}.{t}: a whole number from -2 (strongly oppose) to 2 (strongly support).")
        if fictional is False and not source_links(sources.get(iso)):
            e.append(f"sources.{iso}: a real topic needs a source link for every country with a position (or leave the position out).")
    for iso, s in sources.items():
        links = s if isinstance(s, list) else [s]
        if not 1 <= len(links) <= 4 or not all(isinstance(x, str) and URL.match(x) for x in links):
            e.append(f"sources.{iso}: one http(s) link, or a list of up to four.")
    news = pack.get("news") or []
    if not isinstance(news, list) or len(news) > 8:
        e.append("news: at most 8 updates.")
        news = []
    if news and fictional is not True:
        e.append("news: breaking news is only for fictional scenarios (invented news about real events would mislead).")
    for i, n in enumerate(news, 1):
        _text((n or {}).get("headline"), f"news[{i}].headline", 5, 100, e)
        _text((n or {}).get("body"), f"news[{i}].body", 20, 400, e)
    _text(pack.get("author"), "author", 2, 80, e)
    return e


def load(code: str) -> dict:
    if not CODE.match(code or ""):
        raise UserError("That isn't a pack.", 404)
    f = PACK_DIR / f"{code}.json"
    if not f.exists():
        raise UserError("That pack isn't installed.", 404)
    pack = json.loads(f.read_text(encoding="utf-8"))
    errors = validate(pack, code)
    if errors:
        raise UserError(f"The pack {code} has problems: " + " ".join(errors[:3]))
    return pack


def available() -> list[dict]:
    """The packs that pass validation, for the pickers (files starting with _ are templates, not packs)."""
    out = []
    for f in sorted(PACK_DIR.glob("*.json")):
        if f.name.startswith("_"):
            continue
        try:
            pack = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if not validate(pack, f.stem):
            out.append({"code": pack["code"], "title": pack["title"], "summary": pack["summary"], "level": pack["level"],
                        "type": pack["committee"]["type"], "fictional": pack["fictional"], "countries": pack["countries"]})
    return out


def closest_vote(conn, paragraph_ids: list[int]) -> int:
    """The operative clause whose vote the engine finds closest to a coin toss. A solo run starts there, so the first
    vote is a real contest: neither one that passes untouched nor one no lobbying could save (a Security Council clause
    a permanent member is sure to veto)."""
    from app.modules.mun.predict import run_prediction
    best, gap = paragraph_ids[0], 2.0
    for pid in paragraph_ids:
        p = run_prediction(conn, "paragraph", pid, runs=300, seed=7)["result"].p_pass
        if abs(p - 0.5) < gap:
            best, gap = pid, abs(p - 0.5)
    return best


def install(w: Writer, code: str, class_id: int | None = None, name_suffix: str = "", solo_student_id: int | None = None) -> dict:
    """Make a committee from a pack, ready to open as a session or play alone."""
    from app.modules.mun import service
    pack = load(code)
    t = pack["topic"]
    topic_id = scalar(w.conn, "SELECT id FROM topic WHERE code = ?", (t["code"],))
    if not topic_id:
        topic_id = w.insert("topic", {"code": t["code"], "name": t["name"], "notes": t.get("notes") or (
            "Fictional scenario. Every country position is invented and labelled Unverified demo." if pack["fictional"] else "")})
    have = {r["code"] for r in rows(w.conn, "SELECT code FROM tag WHERE topic_id = ?", (topic_id,))}
    for tag, label in pack["tags"].items():
        if tag not in have:
            w.insert("tag", {"topic_id": topic_id, "code": tag, "label": label})
    if pack["fictional"] and pack.get("news") and not one(w.conn, "SELECT 1 FROM crisis_script WHERE topic_code = ?", (t["code"],)):
        for i, n in enumerate(pack["news"], 1):
            w.insert("crisis_script", {"topic_code": t["code"], "position": i, "headline": n["headline"], "body": n["body"]})
    com = pack["committee"]
    ct = one(w.conn, "SELECT * FROM committee_type WHERE code = ?", (com["type"],))
    conf = service.create_conference(w, com["conference"], organiser=com.get("organiser") or "South Oakleigh College",
                                     notes=com.get("notes") or "")
    cid = service.create_committee(w, conf, com["name"] + name_suffix, ct["id"], None, topic_id, class_id)
    if solo_student_id:
        w.update("committee", cid, {"solo_student_id": solo_student_id}, service.committee_channel(cid))
    dels = dict(zip(pack["countries"], service.add_delegations(w, cid, pack["countries"])))
    res = service.create_resolution(w, cid, pack["resolution"]["title"])
    paras = []
    for kind in ("preambular", "operative"):
        for cl in pack["resolution"][kind]:
            paras.append(service.add_paragraph(w, res, kind, cl["text"], ",".join(cl.get("tags") or [])))
    n = 0
    for iso, positions in (pack.get("positions") or {}).items():
        cname = scalar(w.conn, "SELECT name FROM country WHERE iso3 = ?", (iso,)) or iso
        for tag, pos in positions.items():
            if pack["fictional"]:
                service.add_evidence(w, subject_kind="country", iso3=iso, target_kind="tag", tag_code=tag, topic_id=topic_id,
                                     position=pos, strength="moderate", source_type="demo_unverified", summary=UNVERIFIED.format(name=cname))
            else:
                service.add_evidence(w, subject_kind="country", iso3=iso, target_kind="tag", tag_code=tag, topic_id=topic_id,
                                     position=pos, strength="weak", source_type="ai_estimate", source=" ; ".join(source_links(pack["sources"][iso])),
                                     summary=ESTIMATE.format(name=cname))
            n += 1
    return {"conference_id": conf, "committee_id": cid, "resolution_id": res, "delegations": dels, "paragraphs": paras, "evidence": n,
            "pack": code}
