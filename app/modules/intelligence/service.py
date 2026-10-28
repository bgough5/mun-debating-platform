"""Intelligence (Phase 4): licence-gated UN voting data, voting-history priors,
backtests against baselines, and AI features through the provider interface.
"""
from __future__ import annotations

import csv
import io
import json
import random
from datetime import date

from app.db import Writer, one, rows, scalar
from app.engine.calibration import CLASSES, Item, point_probs, report
from app.engine.model import CountryInput, ModelParams, Source, distribution
from app.errors import UserError
from app.util import now_iso

VOTE_CODES = {"yes": "yes", "y": "yes", "1": "yes", "no": "no", "n": "no", "3": "no", "abstain": "abstain", "a": "abstain",
              "2": "abstain", "absent": "absent", "x": "absent", "non-voting": "absent", "8": "absent", "": "absent"}

# Column presets. 'generic' is this platform's own format (used by the synthetic fixture).
# 'undl' follows the column names of the UN Digital Library voting CSV as remembered in the
# build session: NOT checked against a real file (the site was unreachable). Check the
# header row before importing; the importer refuses a file whose columns don't match.
PRESETS = {
    "generic": {"resolution": "resolution_id", "date": "date", "title": "title", "subjects": "subjects", "iso3": "iso3",
                "vote": "vote", "session": "session", "symbol": "symbol"},
    "undl": {"resolution": "undl_id", "date": "date", "title": "title", "subjects": "subjects", "iso3": "ms_code",
             "vote": "ms_vote", "session": "session", "symbol": "resolution"},
}


def source(conn, source_id: int) -> dict:
    s = one(conn, "SELECT * FROM data_source WHERE id = ? AND deleted_at IS NULL", (source_id,))
    if not s:
        raise UserError("That data source doesn't exist.", 404)
    return s


def can_import(s: dict) -> tuple[bool, str]:
    if s["synthetic"]:
        return True, "Synthetic test data: allowed, and every report says it is synthetic."
    if not s["licence_confirmed"]:
        return False, ("Import is locked until the coordinator records that this dataset's licence has been checked and "
                       "allows school use (decision D-014).")
    return True, f"Licence confirmed by {s['confirmed_by']} on {s['confirmed_on']}."


def confirm_licence(w: Writer, source_id: int, licence_text: str, note: str) -> None:
    s = source(w.conn, source_id)
    licence_text = (licence_text or "").strip()
    if len(licence_text) < 10:
        raise UserError("Paste the licence or terms of use exactly as the dataset's page states them.")
    w.update("data_source", s["id"], {"licence_found": licence_text[:2000], "licence_confirmed": 1, "confirmed_by": w.actor.label,
                                      "confirmed_on": date.today().isoformat(), "confirmation_note": (note or "")[:1000]})


def map_tags(conn, topic_id: int | None, text: str) -> list[str]:
    if not topic_id:
        return []
    low = (text or "").lower()
    tags = []
    for r in rows(conn, "SELECT tag_code, keyword FROM history_tag_rule WHERE topic_id = ? AND deleted_at IS NULL ORDER BY id", (topic_id,)):
        if r["keyword"].lower() in low and r["tag_code"] not in tags:
            tags.append(r["tag_code"])
    return tags


def import_votes(w: Writer, source_id: int, data: bytes, preset: str = "generic", topic_id: int | None = None) -> dict:
    s = source(w.conn, source_id)
    ok, why = can_import(s)
    if not ok:
        raise UserError(why, 403)
    cols = PRESETS.get(preset)
    if not cols:
        raise UserError("Unknown file format.")
    try:
        reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    except UnicodeDecodeError:
        raise UserError("The file must be UTF-8 CSV.")
    header = set(reader.fieldnames or [])
    needed = {cols["resolution"], cols["iso3"], cols["vote"]}
    if not needed <= header:
        raise UserError(f"The file's columns don't match the “{preset}” format. Missing: {', '.join(sorted(needed - header))}. "
                        f"Found: {', '.join(sorted(header))[:300]}.")
    known = {r["iso3"] for r in rows(w.conn, "SELECT iso3 FROM country")}
    res_ids: dict[str, int] = {}
    n_votes = skipped = 0
    for row in reader:
        ext = (row.get(cols["resolution"]) or "").strip()
        iso = (row.get(cols["iso3"]) or "").strip().upper()
        vote = VOTE_CODES.get((row.get(cols["vote"]) or "").strip().lower())
        if not ext or vote is None or iso not in known:
            skipped += 1
            continue
        if ext not in res_ids:
            existing = one(w.conn, "SELECT id FROM un_resolution WHERE source_id = ? AND external_id = ?", (source_id, ext))
            if existing:
                res_ids[ext] = existing["id"]
            else:
                title = (row.get(cols["title"]) or "")[:500]
                subjects = (row.get(cols["subjects"]) or "")[:1000]
                tags = map_tags(w.conn, topic_id, f"{subjects} {title}")
                sess = row.get(cols["session"]) or ""
                res_ids[ext] = w.conn.execute(
                    "INSERT INTO un_resolution (source_id, external_id, symbol, title, voted_on, session, subjects, tags, topic_id) "
                    "VALUES (?,?,?,?,?,?,?,?,?)", (source_id, ext, (row.get(cols["symbol"]) or "")[:60], title,
                                                   (row.get(cols["date"]) or "")[:10], int(sess) if str(sess).isdigit() else None,
                                                   subjects, ",".join(tags), topic_id)).lastrowid
        w.conn.execute("INSERT OR REPLACE INTO un_vote (resolution_id, iso3, vote) VALUES (?,?,?)", (res_ids[ext], iso, vote))
        n_votes += 1
    w.log("data_source", source_id, "import", None, {"resolutions": len(res_ids), "votes": n_votes, "skipped": skipped})
    return {"resolutions": len(res_ids), "votes": n_votes, "skipped": skipped}


# ---------- voting-history prior ----------

def history_position(votes: list[str]) -> tuple[float, int] | None:
    """Position on the -2..+2 scale from past votes: +2 if always yes, -2 if always no, abstentions pull to 0."""
    cast = [v for v in votes if v in ("yes", "no", "abstain")]
    if not cast:
        return None
    score = sum(1 if v == "yes" else -1 if v == "no" else 0 for v in cast) / len(cast)
    return 2 * score, len(cast)


def history_sources(conn, topic_id: int | None, tags: list[str], isos: list[str], params: ModelParams,
                    before: str | None = None, exclude_resolution: int | None = None) -> dict[str, list[Source]]:
    """Voting-history prior (spec §5.2 source 3): how each country voted on past resolutions sharing a tag."""
    if not tags or not isos or not one(conn, "SELECT 1 FROM sqlite_master WHERE name = 'un_resolution'"):
        return {}
    res = rows(conn, "SELECT r.id, r.tags, r.voted_on, s.synthetic FROM un_resolution r JOIN data_source s ON s.id = r.source_id "
                     "WHERE r.tags != '' AND (s.licence_confirmed = 1 OR s.synthetic = 1)" + (" AND r.topic_id = ?" if topic_id else ""),
               (topic_id,) if topic_id else ())
    synthetic = any(r["synthetic"] for r in res)
    want = set(tags)
    ids = [r["id"] for r in res if want & set(r["tags"].split(",")) and (before is None or r["voted_on"] < before)
           and r["id"] != exclude_resolution]
    if not ids:
        return {}
    out: dict[str, list[Source]] = {}
    marks = ",".join("?" * len(ids))
    imarks = ",".join("?" * len(isos))
    by: dict[str, list[str]] = {}
    for v in rows(conn, f"SELECT iso3, vote FROM un_vote WHERE resolution_id IN ({marks}) AND iso3 IN ({imarks})", ids + list(isos)):
        by.setdefault(v["iso3"], []).append(v["vote"])
    for iso, votes in by.items():
        hp = history_position(votes)
        if hp:
            pos, n = hp
            w = min(params.history_weight_cap, params.history_weight_per_vote * n)
            label = "Voting history (SYNTHETIC test data)" if synthetic else "Voting history (similar resolutions)"
            out[iso] = [Source(pos, w, "voting_history", label, f"history:{n}", False,
                               f"{n} recorded vote(s) on resolutions with tags {', '.join(sorted(want))}")]
    return out


# ---------- backtest (real UN outcomes, kept separate from conference calibration: D-013) ----------

def backtest(conn, source_id: int, train_fraction: float = 0.7, seed: int = 1, params: ModelParams | None = None) -> dict:
    """Train on earlier resolutions, predict each country's vote on later ones from voting history alone,
    and compare with baselines. Leave-one-out within the test set is NOT used: only earlier votes count."""
    s = source(conn, source_id)
    params = params or ModelParams()
    res = rows(conn, "SELECT * FROM un_resolution WHERE source_id = ? ORDER BY voted_on, id", (source_id,))
    if len(res) < 10:
        raise UserError("At least 10 resolutions are needed for a backtest.")
    cut = int(len(res) * train_fraction)
    train, test = res[:cut], res[cut:]
    train_ids = {r["id"] for r in train}
    # per-country history by tag in the training period
    votes_train: dict[tuple[str, str], list[str]] = {}
    overall: dict[str, list[str]] = {}
    tr_marks = ",".join("?" * len(train_ids))
    for v in rows(conn, f"SELECT v.iso3, v.vote, r.tags FROM un_vote v JOIN un_resolution r ON r.id = v.resolution_id "
                        f"WHERE r.id IN ({tr_marks})", list(train_ids)):
        overall.setdefault(v["iso3"], []).append(v["vote"])
        for t in (v["tags"] or "").split(","):
            if t:
                votes_train.setdefault((v["iso3"], t), []).append(v["vote"])
    blocs: dict[str, list[str]] = {}
    for r in rows(conn, "SELECT b.code, bm.iso3 FROM bloc_member bm JOIN bloc b ON b.id = bm.bloc_id WHERE b.kind = 'regional_group'"):
        blocs.setdefault(r["iso3"], []).append(r["code"])
    items, base_yes, base_rate, base_bloc = [], [], [], []
    for r in test:
        tags = [t for t in (r["tags"] or "").split(",") if t]
        actual = {v["iso3"]: v["vote"] for v in rows(conn, "SELECT iso3, vote FROM un_vote WHERE resolution_id = ?", (r["id"],))
                  if v["vote"] != "absent"}
        for iso, vote in sorted(actual.items()):
            hist = [x for t in tags for x in votes_train.get((iso, t), [])] or overall.get(iso, [])
            hp = history_position(hist)
            srcs = (Source(hp[0], min(params.history_weight_cap, params.history_weight_per_vote * hp[1]), "voting_history", "h"),) if hp else ()
            d = distribution(CountryInput(iso, iso, srcs), params)
            items.append(Item((d.p_yes, d.p_abstain, d.p_no), vote, str(r["id"])))
            base_yes.append(Item(point_probs("yes"), vote, str(r["id"])))
            ov = overall.get(iso, [])
            cast = [x for x in ov if x != "absent"]
            freq = tuple((cast.count(c) + 1) / (len(cast) + 3) for c in CLASSES)        # Laplace-smoothed vote shares
            base_rate.append(Item(freq, vote, str(r["id"])))
            others = [actual[o] for o in actual if o != iso and set(blocs.get(o, [])) & set(blocs.get(iso, []))]
            maj = max(CLASSES, key=lambda c: (others.count(c), -CLASSES.index(c))) if others else None
            base_bloc.append(Item(point_probs(maj) if maj else (1 / 3, 1 / 3, 1 / 3), vote, str(r["id"])))
    rep = report(items, {"Everyone votes yes": base_yes, "Each country's past vote shares": base_rate,
                         "Regional group majority (same vote, leave-one-out)": base_bloc})
    return {"source": s["name"], "synthetic": bool(s["synthetic"]), "train_resolutions": len(train), "test_resolutions": len(test),
            "n": rep.n, "brier": rep.brier, "brier_ci": rep.brier_ci, "log_loss": rep.log_loss, "log_loss_ci": rep.log_loss_ci,
            "ece": rep.ece, "verdict": rep.verdict, "warnings": rep.warnings,
            "reliability": [b.__dict__ for b in rep.reliability], "baselines": rep.baselines,
            "params": params.to_dict(), "train_fraction": train_fraction}


def store_backtest(w: Writer, source_id: int, result: dict) -> int:
    return w.insert("backtest_report", {"source_id": source_id, "created_at": now_iso(),
                                        "params_json": json.dumps({"train_fraction": result["train_fraction"], **result["params"]}),
                                        "results_json": json.dumps(result, default=str), "synthetic": int(result["synthetic"])})


# ---------- AI ----------

def log_ai(conn, provider, purpose, actor_kind, summary, sources, stored_as):
    conn.execute("INSERT INTO ai_call (provider, purpose, actor_kind, summary, sources, stored_as, created_at) VALUES (?,?,?,?,?,?,?)",
                 (provider.name, purpose, actor_kind, summary[:300], sources, stored_as, now_iso()))


def ai_suggest_position(w: Writer, provider, committee_id: int, iso3: str, paragraph_id: int) -> dict:
    """Ask the provider for an estimate and store it as evidence: 'AI estimate — verify' with sources, or unknown."""
    from app.ai.base import PositionRequest
    from app.modules.mun import service as M
    p = M.paragraph(w.conn, paragraph_id)
    if p["committee_id"] != committee_id:
        raise UserError("That paragraph isn't in this committee.")
    c = one(w.conn, "SELECT * FROM country WHERE iso3 = ?", (iso3,))
    if not c:
        raise UserError("Choose a country.")
    topic = scalar(w.conn, "SELECT t.name FROM committee cm LEFT JOIN topic t ON t.id = cm.topic_id WHERE cm.id = ?", (committee_id,)) or ""
    known = [(e["position"], e["source"]) for e in rows(
        w.conn, "SELECT position, source FROM evidence WHERE iso3 = ? AND deleted_at IS NULL AND source != '' "
                "AND source_type NOT IN ('ai_estimate', 'unsourced_note', 'model_estimate') "
                "AND ((target_kind = 'paragraph' AND target_id = ?) OR target_kind = 'topic')", (iso3, paragraph_id))]
    req = PositionRequest(iso3, c["name"], topic, p["text"], [t for t in p["tags"].split(",") if t], known)
    sug = provider.suggest_position(req)
    sources = [s for s in sug.sources if str(s).strip()]
    stored_as = "estimate" if (sources and sug.position is not None) else "unknown"
    eid = M.add_evidence(w, subject_kind="country", iso3=iso3, target_kind="paragraph", target_id=paragraph_id,
                         position=sug.position if stored_as == "estimate" else None, strength="weak",
                         source="; ".join(sources), source_type="ai_estimate",
                         summary=f"[{sug.provider}] {sug.rationale}", channel=f"committee:{committee_id}")
    log_ai(w.conn, provider, "position", w.actor.kind, f"{iso3} on paragraph {paragraph_id}", len(sources), stored_as)
    return {"evidence_id": eid, "stored_as": stored_as, "suggestion": sug}
