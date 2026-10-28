"""Builds engine inputs from the database and stores prediction snapshots (spec §5)."""
from __future__ import annotations

import json
from dataclasses import asdict

from app.db import one, rows
from app.engine.model import (CountryDist, CountryInput, ModelParams, Source, distribution, evidence_quality, quality_shares,
                              source_weight, unknown_share)
from app.engine.priors.archetype import raw_score
from app.engine.rules import VotingRule
from app.engine.simulate import exact_p_pass, inputs_hash, simulate
from app.errors import UserError
from app.util import days_since, now_iso

DEFAULT_RUNS = 4000


def active_model(conn) -> tuple[int, ModelParams]:
    mv = one(conn, "SELECT * FROM model_version WHERE active = 1 ORDER BY id DESC LIMIT 1")
    return mv["id"], ModelParams.from_dict(json.loads(mv["params_json"]))


def committee_rule(conn, committee_id: int) -> tuple[dict, VotingRule]:
    c = one(conn, "SELECT c.*, r.code AS rule_code FROM committee c JOIN voting_rule r ON r.id = c.voting_rule_id "
                  "WHERE c.id = ?", (committee_id,))
    if not c:
        raise UserError("That committee doesn't exist.", 404)
    rule = VotingRule.from_row(one(conn, "SELECT * FROM voting_rule WHERE id = ?", (c["voting_rule_id"],)))
    return c, rule


def split_tags(s: str) -> list[str]:
    return [t.strip() for t in (s or "").split(",") if t.strip()]


def describe_target(conn, kind: str, tid: int) -> dict:
    """What is being predicted: tags, the paragraph/resolution it belongs to, and a label."""
    if kind == "paragraph":
        p = one(conn, "SELECT p.*, v.text, v.tags, r.committee_id, r.id AS resolution_id FROM paragraph p "
                      "JOIN paragraph_version v ON v.id = p.current_version_id JOIN resolution r ON r.id = p.resolution_id "
                      "WHERE p.id = ?", (tid,))
        if not p:
            raise UserError("That paragraph doesn't exist.", 404)
        return {"kind": kind, "id": tid, "tags": split_tags(p["tags"]), "paragraph_id": tid, "amendment_id": None,
                "resolution_id": p["resolution_id"], "committee_id": p["committee_id"], "negate": False,
                "label": f"Paragraph {p['position']} as it stands"}
    if kind == "amendment":
        a = one(conn, "SELECT a.*, p.position, p.resolution_id, r.committee_id, v.tags AS base_tags FROM amendment a "
                      "JOIN paragraph p ON p.id = a.paragraph_id JOIN resolution r ON r.id = p.resolution_id "
                      "JOIN paragraph_version v ON v.id = a.base_version_id WHERE a.id = ?", (tid,))
        if not a:
            raise UserError("That amendment doesn't exist.", 404)
        if a["kind"] == "delete":
            # Supporting a deletion = opposing the paragraph: positions are negated.
            return {"kind": kind, "id": tid, "tags": split_tags(a["base_tags"]), "paragraph_id": a["paragraph_id"],
                    "amendment_id": tid, "resolution_id": a["resolution_id"], "committee_id": a["committee_id"],
                    "negate": True, "label": f"Amendment {tid}: delete paragraph {a['position']}"}
        return {"kind": kind, "id": tid, "tags": split_tags(a["tags"]), "paragraph_id": a["paragraph_id"],
                "amendment_id": tid, "resolution_id": a["resolution_id"], "committee_id": a["committee_id"],
                "negate": False,
                "label": f"Paragraph {a['position']} as amended (amendment {tid}, {a['kind']})"}
    if kind == "resolution":
        r = one(conn, "SELECT * FROM resolution WHERE id = ?", (tid,))
        if not r:
            raise UserError("That resolution doesn't exist.", 404)
        tags: list[str] = []
        for p in rows(conn, "SELECT v.tags FROM paragraph p JOIN paragraph_version v ON v.id = p.current_version_id "
                            "WHERE p.resolution_id = ? AND p.kind = 'operative' AND p.deleted_at IS NULL ORDER BY p.position",
                      (tid,)):
            for t in split_tags(p["tags"]):
                if t not in tags:
                    tags.append(t)
        return {"kind": kind, "id": tid, "tags": tags, "paragraph_id": None, "amendment_id": None,
                "resolution_id": tid, "committee_id": r["committee_id"], "negate": False,
                "label": f"Whole resolution: {r['title']}"}
    raise UserError("Predictions can be made for a paragraph, an amendment or a whole resolution.")


def _archetype_tables(conn, topic_id):
    aff: dict[str, dict[str, float]] = {}
    for r in rows(conn, "SELECT a.code AS arch, t.code AS tag, aa.value FROM archetype_affinity aa "
                        "JOIN archetype a ON a.id = aa.archetype_id JOIN tag t ON t.id = aa.tag_id "
                        "WHERE t.topic_id = ? AND aa.deleted_at IS NULL", (topic_id,)):
        aff.setdefault(r["arch"], {})[r["tag"]] = r["value"]
    blends: dict[str, dict[str, float]] = {}
    for r in rows(conn, "SELECT ca.iso3, a.code AS arch, ca.weight FROM country_archetype ca "
                        "JOIN archetype a ON a.id = ca.archetype_id WHERE ca.topic_id = ? AND ca.deleted_at IS NULL "
                        "ORDER BY ca.id", (topic_id,)):
        blends.setdefault(r["iso3"], {})[r["arch"]] = r["weight"]
    return aff, blends


def build_inputs(conn, target: dict, params: ModelParams, extra_sources: dict | None = None) -> tuple[list[CountryInput], dict]:
    """Returns engine inputs plus display detail (each country's sources and notes)."""
    committee = one(conn, "SELECT * FROM committee WHERE id = ?", (target["committee_id"],))
    topic_id = committee["topic_id"]
    members = rows(conn, "SELECT d.id AS delegation_id, d.iso3, c.name, "
                         "(SELECT COUNT(*) FROM delegation_member dm WHERE dm.delegation_id = d.id AND dm.deleted_at IS NULL) AS students "
                         "FROM delegation d JOIN country c ON c.iso3 = d.iso3 "
                         "WHERE d.committee_id = ? AND d.deleted_at IS NULL ORDER BY d.iso3", (committee["id"],))
    isos = [m["iso3"] for m in members]
    aff, blends = _archetype_tables(conn, topic_id) if topic_id else ({}, {})
    stypes = {r["code"]: r for r in rows(conn, "SELECT * FROM source_type WHERE deleted_at IS NULL")}

    # Blocs, membership and cohesion (for correlation and bloc evidence)
    bloc_rows = rows(conn, "SELECT b.id, b.code, b.name, b.cohesion, bm.iso3 FROM bloc b JOIN bloc_member bm ON bm.bloc_id = b.id "
                           "WHERE b.deleted_at IS NULL AND bm.deleted_at IS NULL")
    blocs_of: dict[str, list[dict]] = {}
    bloc_members: dict[str, tuple[str, list[str]]] = {}
    for r in bloc_rows:
        blocs_of.setdefault(r["iso3"], []).append(r)
        if r["iso3"] in isos:
            bloc_members.setdefault(r["code"], (r["name"], []))[1].append(r["iso3"])
    bloc_members = {k: (v[0], sorted(v[1])) for k, v in bloc_members.items() if len(v[1]) >= 2}

    # Matching evidence
    ev = rows(conn, "SELECT e.*, b.code AS bloc_code, b.name AS bloc_name, b.cohesion FROM evidence e "
                    "LEFT JOIN bloc b ON b.id = e.bloc_id WHERE e.deleted_at IS NULL ORDER BY e.id")

    def applies(e) -> float:
        """Returns a weight factor (0 = doesn't apply)."""
        tk = e["target_kind"]
        if tk == "paragraph":
            return 1.0 if target["paragraph_id"] and e["target_id"] == target["paragraph_id"] else 0.0
        if tk == "amendment":
            return 1.0 if target["amendment_id"] and e["target_id"] == target["amendment_id"] else 0.0
        if tk == "resolution":
            if e["target_id"] != target["resolution_id"]:
                return 0.0
            return 1.0 if target["kind"] == "resolution" else params.conditional_factor
        if tk == "tag":
            return 1.0 if e["tag_code"] in target["tags"] and (e["topic_id"] in (None, topic_id)) else 0.0
        if tk == "topic":
            return 1.0 if e["topic_id"] == topic_id else 0.0
        return 0.0

    hist: dict = {}
    if one(conn, "SELECT 1 FROM sqlite_master WHERE name = 'un_resolution'"):
        from app.modules.intelligence.service import history_sources
        hist = history_sources(conn, topic_id, target["tags"], isos, params)

    inputs: list[CountryInput] = []
    detail: dict[str, dict] = {}
    for m in members:
        iso = m["iso3"]
        srcs: list[Source] = []
        notes: list[dict] = []
        # 1. archetype prior
        raw = raw_score(blends.get(iso, {}), target["tags"], aff) if blends.get(iso) else None
        if raw is not None and params.archetype_weight > 0:
            srcs.append(Source(-raw if target["negate"] else raw, params.archetype_weight, "model_estimate",
                               "Model estimate (archetype)", "archetype", False,
                               "Weighted archetype affinity for tags: " + ", ".join(target["tags"])))
        # 2. evidence on the country, or on a bloc it belongs to
        my_blocs = {b["id"]: b for b in blocs_of.get(iso, [])}
        for e in ev:
            if e["subject_kind"] == "country" and e["iso3"] != iso:
                continue
            if e["subject_kind"] == "bloc" and e["bloc_id"] not in my_blocs:
                continue
            factor = applies(e)
            if factor == 0:
                continue
            st = stypes.get(e["source_type"])
            if e["position"] is None or st is None:
                notes.append(e)
                continue
            if st["requires_source"] and not (e["source"] or "").strip():
                notes.append({**e, "excluded": "No source given, so it is not counted (stored as unknown)."})
                continue
            age = days_since(e["stated_on"] or e["recorded_on"])
            stale = age is not None and age > params.stale_days
            w = source_weight(st["weight"], e["strength"], params, bool(e["conditional"]), stale) * factor
            label = st["shown_as"]
            if e["subject_kind"] == "bloc":
                w *= float(e["cohesion"] or 0)
                label += f" ({e['bloc_name']})"
            pos = -e["position"] if target["negate"] else e["position"]
            srcs.append(Source(float(pos), w, e["source_type"], label, f"evidence:{e['id']}", stale,
                               e["summary"] or e["condition_text"]))
        for h in hist.get(iso, []):    # 3. voting history on similar resolutions (Phase 4)
            srcs.append(Source(-h.position if target["negate"] else h.position, h.weight, h.kind, h.label, h.ref, h.stale, h.note))
        for x in (extra_sources or {}).get(iso, []):
            srcs.append(x)
        best = sorted(my_blocs.values(), key=lambda b: (-b["cohesion"], b["code"]))
        group, rho = (best[0]["code"], float(best[0]["cohesion"])) if best else ("", 0.0)
        ci = CountryInput(iso, m["name"], tuple(srcs), group, rho)
        inputs.append(ci)
        detail[iso] = {"sources": srcs, "notes": notes, "students": m["students"], "delegation_id": m["delegation_id"]}
    return inputs, {"detail": detail, "blocs": bloc_members, "members": len(members)}


def run_prediction(conn, target_kind: str, target_id: int, runs: int = DEFAULT_RUNS, with_swing: bool = True,
                   seed: int | None = None, tags_override: list[str] | None = None, extra_sources: dict | None = None) -> dict:
    """Compute (not store) a prediction. Returns a dict for display and storage.
    `tags_override` and `extra_sources` are for practice runs (D-060): a hypothetical amendment and practice-only
    lobbying readings, which never touch the class's own evidence."""
    target = describe_target(conn, target_kind, target_id)
    if tags_override is not None:
        target = {**target, "tags": list(tags_override), "label": target["label"] + " (practice amendment)"}
    committee, rule = committee_rule(conn, target["committee_id"])
    mv_id, params = active_model(conn)
    inputs, ctx = build_inputs(conn, target, params, extra_sources)
    if not inputs:
        raise UserError("This committee has no delegations yet. Add delegations before predicting.")
    dists = [distribution(ci, params) for ci in inputs]
    payload = {
        "target": {k: target[k] for k in ("kind", "id", "tags", "negate")},
        "rule": asdict(rule) | {"veto": sorted(rule.veto)},
        "params": params.to_dict(), "runs": runs, "members": ctx["members"],
        "countries": [{"iso3": ci.iso3, "group": ci.corr_group, "rho": ci.rho,
                       "sources": [[s.position, s.weight, s.kind, s.ref] for s in ci.sources]} for ci in inputs],
    }
    h = inputs_hash(payload)
    seed = seed if seed is not None else int(h[:8], 16)
    res = simulate(dists, rule, params, runs=runs, seed=seed, members=ctx["members"], blocs=ctx["blocs"],
                   with_swing=with_swing)
    quality = {ci.iso3: evidence_quality(ci) for ci in inputs}
    return {
        "target": target, "committee": committee, "rule": rule, "model_version_id": mv_id, "params": params,
        "dists": dists, "result": res, "inputs_hash": h, "seed": seed, "payload": payload,
        "unknown_share": unknown_share(dists), "quality": quality, "quality_shares": quality_shares(dists, quality),
        "estimate_isos": [k for k, v in quality.items() if v == "estimate"], "detail": ctx["detail"], "blocs": ctx["blocs"],
        "exact_independent": exact_p_pass(dists, rule, ctx["members"]) if len(dists) <= 60 else None,
    }


def store_prediction(w, pred: dict, label: str = "") -> int:
    r = pred["result"]
    pid = w.insert("prediction", {
        "target_kind": pred["target"]["kind"], "target_id": pred["target"]["id"],
        "committee_id": pred["committee"]["id"], "rule_id": pred["committee"]["voting_rule_id"],
        "model_version_id": pred["model_version_id"], "seed": pred["seed"], "runs": r.runs,
        "inputs_hash": pred["inputs_hash"], "inputs_json": json.dumps(pred["payload"], sort_keys=True),
        "p_pass": r.p_pass, "mc_se": r.mc_se, "yes_mean": r.yes_mean, "yes_lo": r.yes_lo, "yes_hi": r.yes_hi,
        "unknown_share": pred["unknown_share"], "created_at": now_iso(), "label": label or pred["target"]["label"],
    }, channel=f"committee:{pred['committee']['id']}")
    for d in pred["dists"]:
        w.conn.execute("INSERT INTO prediction_country (prediction_id, iso3, p_yes, p_abstain, p_no, mu, sigma, unknown) "
                       "VALUES (?,?,?,?,?,?,?,?)", (pid, d.iso3, d.p_yes, d.p_abstain, d.p_no, d.mu, d.sigma, int(d.unknown)))
    return pid


def replay(conn, prediction_id: int):
    """Re-run a stored snapshot from its own inputs. Must reproduce p_pass exactly."""
    p = one(conn, "SELECT * FROM prediction WHERE id = ?", (prediction_id,))
    payload = json.loads(p["inputs_json"])
    params = ModelParams.from_dict(payload["params"])
    rr = payload["rule"]
    rule = VotingRule(rr["code"], rr["name"], rr["threshold_num"], rr["threshold_den"], rr["denominator"],
                      rr["at_threshold"], rr["min_yes"], frozenset(rr["veto"]))
    dists = []
    for c in payload["countries"]:
        srcs = tuple(Source(s[0], s[1], s[2], s[2], s[3]) for s in c["sources"])
        dists.append(distribution(CountryInput(c["iso3"], c["iso3"], srcs, c["group"], c["rho"]), params))
    res = simulate(dists, rule, params, runs=payload["runs"], seed=p["seed"], members=payload["members"])
    return p, res, inputs_hash(payload)


def compare(conn, paragraph_id: int, amendment_ids: list[int] | None = None, runs: int = DEFAULT_RUNS) -> dict:
    """Original paragraph vs each tabled amendment: delta P(pass) and which countries move."""
    base = run_prediction(conn, "paragraph", paragraph_id, runs=runs, with_swing=False)
    if amendment_ids is None:
        amendment_ids = [a["id"] for a in rows(conn, "SELECT id FROM amendment WHERE paragraph_id = ? AND deleted_at IS NULL "
                                                     "AND status IN ('tabled','friendly') AND submitted_at IS NOT NULL ORDER BY id", (paragraph_id,))]
    out = []
    bd = {d.iso3: d for d in base["dists"]}
    for aid in amendment_ids:
        pa = run_prediction(conn, "amendment", aid, runs=runs, with_swing=False, seed=base["seed"])  # common random numbers
        movers = []
        for d in pa["dists"]:
            b = bd[d.iso3]
            if b.modal_vote != d.modal_vote or abs(d.p_yes - b.p_yes) >= 0.10:
                movers.append({"iso3": d.iso3, "name": d.name, "from": b.modal_vote, "to": d.modal_vote,
                               "dp_yes": d.p_yes - b.p_yes})
        movers.sort(key=lambda m: (-abs(m["dp_yes"]), m["iso3"]))
        out.append({"amendment_id": aid, "pred": pa, "delta": pa["result"].p_pass - base["result"].p_pass,
                    "movers": movers})
    return {"base": base, "amendments": out}


def modal_votes(dists: list[CountryDist]) -> dict[str, str]:
    return {d.iso3: d.modal_vote for d in dists}
