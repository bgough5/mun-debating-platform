"""Phase 7 item 4: the offline practice partner is never called AI; "AI delegation" only with an approved provider (D-066)."""
from types import SimpleNamespace

from app.ai import FakeProvider, ai_live, negotiation_label
from tests.api.helpers import join_as
from tests.conftest import db_one


def _settings(ai):
    return SimpleNamespace(get=lambda k, d=None: {"ai": ai}.get(k, d))


def test_label_rule():
    assert not ai_live(_settings({"provider": "fake", "school_approved": True}))
    assert not ai_live(_settings({"provider": "anthropic", "school_approved": False}))
    assert not ai_live(_settings({"provider": "off", "school_approved": True}))
    assert ai_live(_settings({"provider": "anthropic", "school_approved": True}))
    assert negotiation_label(_settings({})) == "Practice negotiation (rule-based)"


def _student(app):
    com = db_one(app, "SELECT * FROM committee WHERE name LIKE 'United Nations General Assembly%'")
    return join_as(app, db_one(app, "SELECT id FROM student WHERE class_id = ? ORDER BY id LIMIT 1", (com["class_id"],))["id"])


def test_offline_partner_is_labelled_rule_based_not_ai(app):
    s = _student(app)
    home = s.get("/me").text
    assert "Practice negotiation (rule-based)" in home and "AI delegation" not in home
    r = s.get("/me/ai-practice").text
    assert "<title>Practice negotiation (rule-based)" in r and "This is not AI." in r
    assert 'class="label-ai"' not in r
    s.post("/me/ai-practice", {"iso3": "SAU", "paragraph_id": ""})
    pid = db_one(app, "SELECT id FROM ai_practice ORDER BY id DESC LIMIT 1")["id"]
    chat = s.post(f"/me/ai-practice/{pid}", {"message": "We could support a softer verb if you accept a review in 2030."}).text
    assert "not AI" in chat and "rule-based" in chat and 'class="label-ai"' not in chat


def test_approved_provider_is_labelled_ai_delegation(app, monkeypatch):
    import app.modules.intelligence.routes as R
    monkeypatch.setattr(R, "get_provider", lambda settings: FakeProvider())      # no network in tests
    cfg = dict(app.state.settings.get("ai", {}) or {})
    app.state.settings.set("ai", {**cfg, "provider": "anthropic", "school_approved": True})
    try:
        s = _student(app)
        assert "AI delegation" in s.get("/me").text
        r = s.get("/me/ai-practice").text
        assert "<title>AI delegation" in r and 'class="label-ai"' in r and "approved" in r and "This is not AI." not in r
    finally:
        app.state.settings.set("ai", cfg)
