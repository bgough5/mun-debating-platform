"""Phase 7 item 3: evidence quality — 'estimate only' is reported, not hidden as 0% unknown (D-065)."""
from app.engine.model import CountryInput, Source, evidence_quality
from app.modules.mun import service as M
from app.modules.mun.predict import run_prediction
from tests.api.helpers import ga
from tests.conftest import db_one, db_rows


def test_quality_rule():
    est = Source(1.0, 1.0, "model_estimate", "Model estimate", "archetype")
    sourced = Source(2.0, 4.0, "official_statement", "Official statement", "evidence:1")
    assert evidence_quality(CountryInput("AAA", "A", (), "", 0)) == "unknown"
    assert evidence_quality(CountryInput("AAA", "A", (est,), "", 0)) == "estimate"
    assert evidence_quality(CountryInput("AAA", "A", (est, Source(1, 1, "ai_estimate", "AI", "x")), "", 0)) == "estimate"
    assert evidence_quality(CountryInput("AAA", "A", (est, sourced), "", 0)) == "sourced"


def _para(app, com):
    return db_one(app, "SELECT p.id FROM paragraph p JOIN resolution r ON r.id = p.resolution_id JOIN paragraph_version v ON "
                       "v.id = p.current_version_id WHERE r.committee_id = ? AND p.kind = 'operative' ORDER BY p.position LIMIT 1",
                  (com["id"],))["id"]


def test_archetype_only_committee_is_almost_all_estimate(app, coord):
    """A committee whose countries have only archetype priors (and pack notes, which are unsourced) is reported as
    ~100% estimate only, not 0% unknown."""
    com = ga(app)
    pid = _para(app, com)
    with app.state.db.write(__import__("app.db", fromlist=["SYSTEM"]).SYSTEM) as w:
        # the demo pack's notes are unsourced; remove any sourced evidence so only estimates remain
        for e in db_rows(app, "SELECT id FROM evidence WHERE source_type NOT IN ('model_estimate', 'unsourced_note', 'demo_unverified', 'ai_estimate') AND deleted_at IS NULL"):
            w.soft_delete("evidence", e["id"])
    with app.state.db.read() as conn:
        pred = run_prediction(conn, "paragraph", pid, runs=500, with_swing=False)
    assert pred["unknown_share"] == 0.0                      # the old figure: misleadingly confident
    assert pred["quality_shares"]["estimate"] > 0.99          # the new figure tells the truth
    assert set(pred["quality"].values()) == {"estimate"}
    page = coord.get(f"/mun/predict/paragraph/{pid}").text
    assert "only on unsourced estimates" in page and "Estimate only" in page


def test_one_sourced_statement_makes_a_country_sourced(app, coord):
    com = ga(app)
    pid = _para(app, com)
    with app.state.db.read() as conn:
        before = run_prediction(conn, "paragraph", pid, runs=500, with_swing=False)
    iso = next(k for k, v in before["quality"].items() if v == "estimate")
    with app.state.db.write(__import__("app.db", fromlist=["SYSTEM"]).SYSTEM) as w:
        M.add_evidence(w, subject_kind="country", iso3=iso, target_kind="paragraph", target_id=pid, position=1,
                       source_type="official_statement", source="Statement in GA debate, fake test source", summary="Supports")
    with app.state.db.read() as conn:
        after = run_prediction(conn, "paragraph", pid, runs=500, with_swing=False)
    assert after["quality"][iso] == "sourced"
    assert after["quality_shares"]["estimate"] < before["quality_shares"]["estimate"]
    assert abs(sum(after["quality_shares"].values()) - 1) < 1e-9
