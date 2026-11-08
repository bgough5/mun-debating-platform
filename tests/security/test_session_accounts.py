"""D-103: The Session's player accounts must be airtight. Open sign-up only with the school's approval recorded;
scrypt passwords never logged; one generic sign-in error and a hash check either way; throttling; tokens stored
hashed, HttpOnly cookies, remember-me for 30 days, rotation, sign-out; an account can never reach another's saves or
any student's; erasure removes everything; the coordinator's tools need the coordinator."""
import json

import pytest

from app.db import SYSTEM
from app.modules.sim import accounts as AC
from tests.conftest import Client, db_one, new_client
from tests.api.helpers import join_as


def api(c, body):
    return c.request("POST", "/session/api", json=body, headers={"X-CSRF-Token": c.csrf()})


def _open(app):
    app.state.settings.set("session_accounts", {"open": True})


def _guest(app) -> Client:
    return new_client(app).__enter__()


def _make(app, name="delegate_one", pw="a quiet lighthouse", remember=False) -> Client:
    _open(app)
    c = _guest(app)
    r = c.post("/session/account/create", {"username": name, "password": pw, "password2": pw, "remember": "1" if remember else ""},
               follow_redirects=False)
    assert r.status_code == 303, r.text
    return c


@pytest.fixture(autouse=True)
def _fresh_throttles():
    for t in (AC.signin_throttle, AC.signup_throttle):
        t.fails.clear()
        t.locked_until.clear()
    yield


def test_sign_up_is_on_unless_the_coordinator_switches_it_off(app):
    """Ben, 9 Nov: new accounts don't need the school's approval; the coordinator can switch sign-up off."""
    assert AC.open_signup(app.state.settings)                                      # on by default
    app.state.settings.set("session_accounts", {"open": False})
    c = _guest(app)
    r = c.post("/session/account/create", {"username": "player_one", "password": "a quiet lighthouse", "password2": "a quiet lighthouse"},
               follow_redirects=False)
    assert r.status_code == 403 and db_one(app, "SELECT COUNT(*) AS n FROM player_account")["n"] == 0
    assert "switched off right now" in c.get("/session/account").text

def test_passwords_are_hashed_and_never_logged(app):
    _make(app, "ledger_test", "spring tide over harbour")
    row = db_one(app, "SELECT pass_hash, username FROM player_account WHERE username_key = 'ledger_test'")
    assert row["pass_hash"].startswith("scrypt$") and "spring" not in row["pass_hash"]
    log = json.dumps([dict(r) for r in app.state.db.connect().execute("SELECT * FROM event_log WHERE entity = 'player_account'")])
    assert "scrypt$" not in log and "spring tide" not in log


def test_weak_passwords_and_bad_usernames_are_refused(app):
    _open(app)
    c = _guest(app)
    for name, pw in [("ab", "a quiet lighthouse"), ("1player", "a quiet lighthouse"), ("admin", "a quiet lighthouse"),
                     ("good_name", "short"), ("good_name", "password123"), ("good_name", "good_name_secret"), ("good_name", "aaaaaaaaaaaa")]:
        r = c.post("/session/account/create", {"username": name, "password": pw, "password2": pw}, follow_redirects=False)
        assert r.status_code == 400, (name, pw)
    assert db_one(app, "SELECT COUNT(*) AS n FROM player_account")["n"] == 0


def test_one_generic_error_and_throttling(app):
    _make(app, "real_user", "copper kettle sings")
    c = _guest(app)
    wrong = c.post("/session/account/signin", {"username": "real_user", "password": "not the one"}, follow_redirects=False)
    nobody = c.post("/session/account/signin", {"username": "no_such_user", "password": "not the one"}, follow_redirects=False)
    assert wrong.status_code == nobody.status_code == 401 and "Username or password is wrong" in wrong.text and "Username or password is wrong" in nobody.text
    for _ in range(5):
        c.post("/session/account/signin", {"username": "real_user", "password": "still wrong"}, follow_redirects=False)
    locked = c.post("/session/account/signin", {"username": "real_user", "password": "copper kettle sings"}, follow_redirects=False)
    assert locked.status_code == 429                                                # even the right password waits


def test_the_cookie_the_token_and_remember_me(app):
    c = _make(app, "cookie_test", "velvet morning fog")
    setc = None
    c2 = _guest(app)
    r = c2.post("/session/account/signin", {"username": "cookie_test", "password": "velvet morning fog", "remember": "1"}, follow_redirects=False)
    setc = r.headers.get("set-cookie", "")
    assert r.status_code == 303 and "soc_player=" in setc and "httponly" in setc.lower() and "samesite=lax" in setc.lower() and "max-age=2592000" in setc.lower()
    token = c2.cookies.get(AC.COOKIE)
    assert not db_one(app, "SELECT 1 AS x FROM player_session WHERE token_hash = ?", (token,))          # only its hash is stored
    r = c2.post("/session/account/signin", {"username": "cookie_test", "password": "velvet morning fog"}, follow_redirects=False)
    assert "max-age" not in r.headers.get("set-cookie", "").lower()                 # without remember me: a browser-session cookie
    assert "Signed in as" in c2.get("/session").text or "cookie_test" in c2.get("/session").text


def test_sign_out_and_password_change_end_sessions(app):
    c = _make(app, "session_end", "orchard after rain")
    other = _guest(app)
    other.post("/session/account/signin", {"username": "session_end", "password": "orchard after rain"})
    assert "session_end" in other.get("/session").text
    c.post("/session/account/password", {"password": "orchard after rain", "new_password": "lantern on the pier", "new_password2": "lantern on the pier"})
    assert "session_end" not in other.get("/session").text                          # the other browser is signed out
    assert "session_end" in c.get("/session").text                                  # this one carries on
    c.post("/session/account/signout")
    assert "session_end" not in c.get("/session").text


def test_an_account_cannot_reach_another_accounts_or_a_students_saves(app):
    a = _make(app, "owner_a", "granite and moss")
    j = api(a, {"do": "new", "pack": "comet_halcyon", "iso3": "NZL", "length": "quick", "difficulty": "standard"}).json()
    assert j["url"].startswith("/session/a/")
    sid = int(j["url"].rsplit("/", 1)[1])
    b = _make(app, "intruder_b", "harbour bells ring")
    assert b.get(f"/session/a/{sid}").status_code == 403
    r = api(b, {"do": "view", "save_id": sid})
    assert r.status_code == 403
    st = db_one(app, "SELECT id FROM student WHERE active = 1 ORDER BY id LIMIT 1")["id"]
    s = join_as(app, st)
    js = api(s, {"do": "new", "pack": "comet_halcyon", "iso3": "NZL", "length": "quick", "difficulty": "standard"}).json()
    ssid = int(js["url"].rsplit("/", 1)[1])
    assert api(b, {"do": "view", "save_id": ssid}).status_code in (403, 404)
    r = b.get(f"/session/s/{ssid}", follow_redirects=False)
    assert r.status_code in (401, 403, 303) and 'data-mode="saved"' not in r.text          # sent to sign in; never the game


def test_erasing_an_account_removes_everything(app):
    c = _make(app, "eraser", "whistle in the dunes")
    api(c, {"do": "new", "pack": "comet_halcyon", "iso3": "NZL", "length": "quick", "difficulty": "standard"})
    aid = db_one(app, "SELECT id FROM player_account WHERE username_key = 'eraser'")["id"]
    assert c.post("/session/account/delete", {"password": "wrong password!"}, follow_redirects=False).status_code == 401
    c.post("/session/account/delete", {"password": "whistle in the dunes"})
    for t in ("player_account WHERE id", "player_session WHERE account_id", "account_save WHERE account_id"):
        assert db_one(app, f"SELECT COUNT(*) AS n FROM {t} = ?", (aid,))["n"] == 0


def test_the_coordinators_tools_need_the_coordinator(app, coord):
    _make(app, "reset_me", "paper boats drift")
    aid = db_one(app, "SELECT id FROM player_account WHERE username_key = 'reset_me'")["id"]
    g = _guest(app)
    assert g.get("/session/accounts", follow_redirects=False).status_code in (401, 303, 403)
    assert g.post(f"/session/accounts/{aid}/delete", follow_redirects=False).status_code in (401, 303, 403)
    page = coord.get("/session/accounts").text
    assert "reset_me" in page and "signed in now" in page and "New accounts" in page
    coord.post("/session/accounts/settings", {})
    assert not AC.open_signup(app.state.settings)                                   # the coordinator can switch it off
    coord.post("/session/accounts/settings", {"open": "1"})
    assert AC.open_signup(app.state.settings)
    with app.state.db.write(SYSTEM) as w:                                          # an account nobody has used for over a year
        w.conn.execute("UPDATE player_account SET last_login_at = '2024-01-01T00:00:00+00:00' WHERE id = ?", (aid,))
    assert "not used for a year" in coord.get("/session/accounts").text
    coord.post("/session/accounts/erase-stale")
    assert db_one(app, "SELECT COUNT(*) AS n FROM player_account WHERE id = ?", (aid,))["n"] == 0
    _make(app, "reset_me", "paper boats drift")
    aid = db_one(app, "SELECT id FROM player_account WHERE username_key = 'reset_me'")["id"]
    reset = coord.post(f"/session/accounts/{aid}/reset").text
    assert "Temporary password" in reset
