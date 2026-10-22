"""Phase 4: licence-gated import, voting-history prior, backtest, AI provider rules."""
from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.ai import FakeProvider, get_provider
from app.ai.base import PositionRequest
from tests.api.helpers import join_as
from tests.conftest import db_one, db_rows

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "synthetic_un_votes.csv"


def _src(app, code):
    return db_one(app, "SELECT * FROM data_source WHERE code = ?", (code,))


def test_real_import_locked_until_licence_confirmed(coord, app):
    undl = _src(app, "undl")
    r = coord.post(f"/intel/sources/{undl['id']}/import", {"preset": "generic"}, files={"file": ("v.csv", FIXTURE.read_bytes(), "text/csv")})
    assert r.status_code == 403 and "locked" in r.text
    r = coord.post(f"/intel/sources/{undl['id']}/confirm", {"licence_text": "Copyright, United Nations; Non commercial use, with attribution.",
                                                            "confirm": "yes"})
    assert r.status_code == 200
    s = _src(app, "undl")
    assert s["licence_confirmed"] == 1 and s["confirmed_by"] == "Coordinator"
    bad = b"a,b,c\n1,2,3\n"
    r = coord.post(f"/intel/sources/{undl['id']}/import", {"preset": "undl"}, files={"file": ("v.csv", bad, "text/csv")})
    assert r.status_code == 400 and "don't match" in r.text
    r = coord.post(f"/intel/sources/{undl['id']}/import", {"preset": "generic"}, files={"file": ("v.csv", FIXTURE.read_bytes(), "text/csv")})
    assert r.status_code == 200 and "Imported 8" in r.text


def test_synthetic_only_in_demo(tmp_path):
    from app.main import create_app
    from tests.conftest import login_coordinator, make_settings, new_client
    app = create_app(make_settings(tmp_path, dataset="real"))
    with new_client(app) as c:
        login_coordinator(c)
        r = c.post(f"/intel/sources/{_src(app, 'synthetic')['id']}/load-synthetic")
        assert r.status_code == 400 and "demo" in r.text


def _load_synthetic(coord, app):
    sid = _src(app, "synthetic")["id"]
    r = coord.post(f"/intel/sources/{sid}/load-synthetic")
    assert r.status_code == 200, r.text[:300]
    return sid


def test_history_prior_used_and_labelled(coord, app):
    _load_synthetic(coord, app)
    tagged = db_one(app, "SELECT COUNT(*) AS n FROM un_resolution WHERE tags != ''")["n"]
    assert tagged == 120                       # keyword rules tagged every synthetic resolution
    com = db_one(app, "SELECT id FROM committee WHERE name LIKE 'United Nations General Assembly%'")["id"]
    para = db_one(app, "SELECT p.id FROM paragraph p JOIN resolution r ON r.id = p.resolution_id WHERE r.committee_id = ? AND p.kind='operative' LIMIT 1", (com,))["id"]
    r = coord.get(f"/mun/predict/paragraph/{para}")
    assert "Voting history (SYNTHETIC test data)" in r.text


def test_backtest_beats_naive_baseline_on_synthetic(coord, app):
    sid = _load_synthetic(coord, app)
    r = coord.post(f"/intel/backtest/{sid}")
    assert r.status_code == 200 and "Synthetic data" in r.text
    import json
    res = json.loads(db_one(app, "SELECT results_json FROM backtest_report ORDER BY id DESC LIMIT 1")["results_json"])
    assert res["synthetic"] and res["n"] > 2000
    yes = next(b for b in res["baselines"] if b["name"] == "Everyone votes yes")
    assert yes["beats"]                        # the history prior recovers the known signal


def test_default_provider_is_offline_and_approval_required():
    s = SimpleNamespace(get=lambda k, d=None: {"ai": {"provider": "anthropic", "school_approved": False}}.get(k, d))
    assert isinstance(get_provider(s), FakeProvider)        # no approval -> never the real service
    assert FakeProvider.sends_data_off_device is False


def test_position_request_carries_no_student_data():
    names = {f.name for f in fields(PositionRequest)}
    assert not names & {"student", "student_name", "first_name", "student_text"}


def test_ai_estimate_without_source_is_stored_as_unknown(coord, app):
    com = db_one(app, "SELECT id FROM committee WHERE name LIKE 'United Nations General Assembly%'")["id"]
    para = db_one(app, "SELECT p.id FROM paragraph p JOIN resolution r ON r.id = p.resolution_id WHERE r.committee_id = ? AND p.kind='operative' AND p.position = 5", (com,))["id"]
    r = coord.post("/intel/ai/estimate", {"committee_id": com, "iso3": "KEN", "paragraph_id": para})
    assert r.status_code == 200 and "stored as unknown" in r.text
    e = db_one(app, "SELECT * FROM evidence WHERE source_type = 'ai_estimate' ORDER BY id DESC LIMIT 1")
    assert e["position"] is None and e["source"] == ""
    # it does not move the prediction: no ai_estimate source is counted for KEN
    from app.modules.mun.predict import run_prediction
    with app.state.db.read() as conn:
        pred = run_prediction(conn, "paragraph", para, runs=300)
    assert not [s for s in pred["detail"]["KEN"]["sources"] if s.kind == "ai_estimate"]


def test_ai_estimate_with_sources_is_labelled_estimate(coord, app):
    com = db_one(app, "SELECT id FROM committee WHERE name LIKE 'United Nations General Assembly%'")["id"]
    para = db_one(app, "SELECT p.id FROM paragraph p JOIN resolution r ON r.id = p.resolution_id WHERE r.committee_id = ? AND p.kind='operative' AND p.position = 1", (com,))["id"]
    # Unsourced notes don't count as sources; an official statement with a citation does.
    coord.post(f"/mun/committees/{com}/evidence", {"subject_kind": "country", "iso3": "USA", "target_kind": "paragraph",
                                                  "target_id_paragraph": para, "position": "-2", "source_type": "official_statement",
                                                  "source": "https://example.org/statement (test)", "summary": "Withdrawal statement"})
    r = coord.post("/intel/ai/estimate", {"committee_id": com, "iso3": "USA", "paragraph_id": para})
    e = db_one(app, "SELECT e.*, st.shown_as FROM evidence e JOIN source_type st ON st.code = e.source_type WHERE e.source_type = 'ai_estimate' ORDER BY e.id DESC LIMIT 1")
    assert e["position"] == -2 and "example.org" in e["source"] and e["shown_as"] == "AI estimate — verify"


def test_anthropic_adapter_with_mock_client():
    from app.ai.anthropic_provider import AnthropicProvider

    class Msg:
        def __init__(self, text, stop="end_turn"):
            self.content = [SimpleNamespace(type="text", text=text)]
            self.stop_reason = stop

    class Client:
        def __init__(self, reply):
            self.reply, self.calls = reply, []
            self.messages = self

        def create(self, **kw):
            self.calls.append(kw)
            return self.reply

    req = PositionRequest("FJI", "Fiji", "Climate", "Urges all nations...", ["binding"])
    c = Client(Msg('{"position": 2, "rationale": "Frontline state", "sources": ["A/RES/77/276"]}'))
    sug = AnthropicProvider(client=c).suggest_position(req)
    assert sug.position == 2 and sug.sources == ["A/RES/77/276"]
    assert c.calls[0]["model"] == "claude-opus-5-5"
    sug = AnthropicProvider(client=Client(Msg('{"position": 2, "rationale": "x", "sources": []}'))).suggest_position(req)
    assert sug.sources == []                   # -> stored as unknown by the service
    assert AnthropicProvider(client=Client(Msg("", "refusal"))).suggest_position(req).position is None


def test_student_ai_practice_labelled_and_private(app):
    com = db_one(app, "SELECT * FROM committee WHERE name LIKE 'United Nations General Assembly%'")
    studs = db_rows(app, "SELECT id FROM student WHERE class_id = ? ORDER BY id LIMIT 2", (com["class_id"],))
    a = join_as(app, studs[0]["id"])
    para = db_one(app, "SELECT p.id FROM paragraph p JOIN resolution r ON r.id = p.resolution_id WHERE r.committee_id = ? AND p.kind='operative' LIMIT 1", (com["id"],))["id"]
    r = a.post("/me/ai-practice", {"iso3": "SAU", "paragraph_id": str(para)})
    assert r.status_code == 200 and "AI" in r.text and "estimates, not facts" in r.text
    pid = db_one(app, "SELECT id FROM ai_practice ORDER BY id DESC LIMIT 1")["id"]
    r = a.post(f"/me/ai-practice/{pid}", {"message": "We could support a softer verb if you accept a review in 2030."})
    assert r.status_code == 200 and "Saudi Arabia" in r.text
    msgs = db_rows(app, "SELECT role FROM ai_practice_message WHERE practice_id = ?", (pid,))
    assert [m["role"] for m in msgs] == ["student", "ai"]
    b = join_as(app, studs[1]["id"])
    assert b.get(f"/me/ai-practice/{pid}").status_code == 403


def test_coaching_points_to_rubric_without_rewriting(app):
    sid = db_one(app, "SELECT id FROM student ORDER BY id LIMIT 1")["id"]
    c = join_as(app, sid)
    crit = db_rows(app, "SELECT rc.id FROM rubric_criterion rc JOIN rubric r ON r.id = rc.rubric_id WHERE r.kind = 'speech'")
    c.post("/me/practice", {"topic": "That zoos do more harm than good", "target_seconds": "180", "reflection": "More examples",
                            **{f"c_{x['id']}": "2" for x in crit}})
    ps = db_one(app, "SELECT id FROM practice_speech WHERE student_id = ?", (sid,))["id"]
    r = c.get(f"/me/practice/{ps}/coach")
    assert r.status_code == 200 and "The next level up is" in r.text
