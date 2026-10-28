"""Phase 1 API tests: setup, sign-in, CSRF, admin tables, CSV, history and undo, demo mode."""
from app.config import Settings
from tests.conftest import COORD_PASS, db_one, db_rows, login_coordinator, new_client


def test_first_run_setup_then_login(tmp_path):
    from app.main import create_app
    s = Settings(data_dir=tmp_path / "d").load()
    app = create_app(s)
    with new_client(app) as c:
        r = c.get("/", follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/setup"
        r = c.post("/setup", {"passphrase": "short", "passphrase2": "short"})
        assert r.status_code == 400 and "at least 10" in r.text
        r = c.post("/setup", {"passphrase": "four random words here", "passphrase2": "four random words here"})
        assert r.status_code == 200 and "Getting started" in r.text      # Phase 6: first run opens the wizard
        assert s.get("coordinator_hash").startswith("scrypt$")
        # setup can't be repeated
        r = c.post("/setup", {"passphrase": "another long passphrase", "passphrase2": "another long passphrase"})
        assert r.status_code == 409


def test_wrong_passphrase_and_throttle(client):
    for _ in range(5):
        r = client.post("/login", {"who": "coordinator", "passphrase": "nope nope nope"})
        assert r.status_code in (401, 429)
    r = client.post("/login", {"who": "coordinator", "passphrase": COORD_PASS})
    assert r.status_code == 429 and "Wait" in r.text


def test_csrf_required(client):
    login_coordinator(client)
    r = client.post("/people/classes", {"name": "X", "csrf": "wrong"})
    assert r.status_code == 403 and "expired" in r.text


def test_admin_requires_coordinator(client):
    r = client.get("/admin", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/login")


def test_admin_edit_history_restore_and_undo(coord, app):
    r = coord.get("/admin/t/voting_rule")
    assert r.status_code == 200 and "Security Council substantive" in r.text
    rule = db_one(app, "SELECT * FROM voting_rule WHERE code = 'ga_simple'")
    form = {k: rule[k] for k in ("code", "name", "threshold_num", "threshold_den", "denominator", "at_threshold", "min_yes", "veto_iso3", "notes")}
    form["name"] = "GA simple majority (edited)"
    r = coord.post(f"/admin/t/voting_rule/{rule['id']}", form)
    assert r.status_code == 200 and "Saved" in r.text
    assert db_one(app, "SELECT name FROM voting_rule WHERE id = ?", (rule["id"],))["name"].endswith("(edited)")
    # undo my last change
    r = coord.post("/admin/undo")
    assert db_one(app, "SELECT name FROM voting_rule WHERE id = ?", (rule["id"],))["name"] == "GA simple majority"
    # restore the edited version from history
    ev = db_one(app, "SELECT seq FROM event_log WHERE entity = 'voting_rule' AND action = 'update' ORDER BY seq DESC LIMIT 1")
    coord.post(f"/admin/history/{ev['seq']}/restore")
    assert db_one(app, "SELECT name FROM voting_rule WHERE id = ?", (rule["id"],))["name"].endswith("(edited)")


def test_admin_validation_plain_english(coord):
    r = coord.post("/admin/t/country/new", {"iso3": "XX", "name": "Nowhere"})
    assert r.status_code == 400 and "three letters" in r.text


def test_soft_delete_needs_confirmation_and_restores(coord, app):
    r = coord.post("/admin/t/country/FJI/delete", {})
    assert r.status_code == 400
    coord.post("/admin/t/country/FJI/delete", {"confirm": "yes"})
    assert db_one(app, "SELECT deleted_at FROM country WHERE iso3 = 'FJI'")["deleted_at"]
    coord.post("/admin/t/country/FJI/restore")
    assert db_one(app, "SELECT deleted_at FROM country WHERE iso3 = 'FJI'")["deleted_at"] is None


def test_csv_export_import_roundtrip(coord, app):
    r = coord.get("/admin/csv/bloc.csv")
    assert r.status_code == 200 and r.content.startswith(b"\xef\xbb\xbf")
    text = r.content.decode("utf-8-sig")
    assert text.splitlines()[0].startswith("id,code,name")
    edited = text.replace("Alliance of Small Island States", "AOSIS (renamed)")
    r = coord.post("/admin/import/bloc", files={"file": ("bloc.csv", edited.encode("utf-8-sig"), "text/csv")})
    assert r.status_code == 200 and "1 changed" in r.text
    assert db_one(app, "SELECT name FROM bloc WHERE code = 'AOSIS'")["name"] == "AOSIS (renamed)"


def test_csv_import_all_or_nothing(coord, app):
    bad = "code,name,kind,cohesion\nNEW1,New bloc,negotiating_bloc,0.3\nNEW2,Bad,not_a_kind,0.3\n"
    r = coord.post("/admin/import/bloc", files={"file": ("b.csv", bad.encode(), "text/csv")})
    assert r.status_code == 400 and "Row 3" in r.text
    assert db_one(app, "SELECT 1 AS x FROM bloc WHERE code = 'NEW1'") is None


def test_secrets_never_exported(coord):
    r = coord.get("/admin/csv/student.csv")
    assert r.status_code == 200
    assert "pass_hash" not in r.text and "token_hash" not in r.text


def test_demo_banner_and_switch(coord, app):
    assert "DEMO" in coord.get("/").text
    r = coord.post("/admin/data/switch", {"dataset": "real"})
    assert r.status_code == 200 and "Switched to the real dataset" in r.text
    assert "DEMO —" not in coord.get("/").text
    assert db_one(app, "SELECT COUNT(*) AS n FROM student")["n"] == 0     # real dataset starts empty
    coord.post("/admin/data/switch", {"dataset": "demo"})
    assert db_one(app, "SELECT COUNT(*) AS n FROM student")["n"] > 0


def test_model_version_create_and_activate(coord, app):
    r = coord.post("/admin/model", {"name": "v2.1-test", "params": '{"sigma_unknown": 1.4}', "notes": "test"})
    assert r.status_code == 200
    mid = db_one(app, "SELECT id FROM model_version WHERE name = 'v2.1-test'")["id"]
    coord.post(f"/admin/model/{mid}/activate")
    act = db_rows(app, "SELECT name FROM model_version WHERE active = 1")
    assert act == [{"name": "v2.1-test"}]
    r = coord.post("/admin/model", {"name": "broken", "params": "{not json"})
    assert r.status_code == 400


def test_practice_game_linked(coord):
    r = coord.get("/practice-game")
    assert r.status_code == 200 and "8000/client/player.html" in r.text
    r = coord.get("/practice-game/solo")
    assert r.status_code == 200 and "<html" in r.text.lower()
