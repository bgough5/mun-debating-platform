"""A beta copy of The Session (app/beta.py): it opens on the game, is watermarked with the tester's name, stops after
its date, and the school platform is untouched when there is no beta.json."""
import json
from datetime import date

from app import beta
from app.main import create_app
from tests.conftest import new_client


def test_no_beta_file_means_the_normal_platform(app):
    assert app.state.beta is None
    with new_client(app) as c:
        assert c.get("/", follow_redirects=False).status_code != 303 or "/session" not in c.get("/", follow_redirects=False).headers.get("location", "")


def test_a_beta_copy_opens_on_the_game_and_is_watermarked(settings, tmp_path, monkeypatch):
    f = tmp_path / "beta.json"
    f.write_text(json.dumps({"tester": "Alex P", "until": "2099-01-01"}), encoding="utf-8")
    monkeypatch.setattr(beta, "FILE", f)
    app = create_app(settings)
    try:
        with new_client(app) as c:
            r = c.get("/", follow_redirects=False)
            assert r.status_code == 303 and r.headers["location"] == "/session"
            assert "Beta copy for Alex P" in c.get("/session").text
    finally:
        from app.web.templating import env
        env.globals.pop("beta", None)


def test_a_beta_copy_stops_after_its_date():
    assert beta.expired({"until": "2026-11-30"}, today=date(2026, 12, 1))
    assert not beta.expired({"until": "2026-11-30"}, today=date(2026, 11, 30))
    assert not beta.expired(None)
