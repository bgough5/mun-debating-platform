"""D-099: single player on the board. Anyone can play from the sign-in page with no code; a guest's game is never
stored (it travels with each move), and a signed-in student's game is saved as they go and is theirs alone."""
from tests.api.helpers import join_as
from tests.conftest import Client, db_one, db_rows


def guest(app) -> Client:
    return Client(app, base_url="http://testserver").__enter__()


def api(c, game, **kw):
    return c.request("POST", "/play/api", json={**game, **kw}, headers={"X-CSRF-Token": c.csrf()})


def start_guest(c, pack="comet_halcyon", iso="NZL"):
    r = c.post("/play/start", {"pack": pack, f"iso3_{pack}": iso}, follow_redirects=False)
    assert r.status_code in (302, 303) and r.headers["location"].startswith("/play/g/")
    _, _, _, code, iso3, seed, pid = r.headers["location"].split("/")
    return r.headers["location"], {"mode": "guest", "code": code, "iso3": iso3, "seed": int(seed), "paragraph_id": int(pid), "lobbies": []}


def test_a_guest_plays_without_a_code_and_nothing_is_kept(app):
    c = guest(app)
    assert "Play solo as a guest" in c.get("/join").text and "/play" in c.get("/").text
    page = c.get("/play").text
    assert "playing as a guest" in page and "Comet Halcyon-7" in page and "Migration" in page.replace("migration", "Migration")
    practices_before = db_one(app, "SELECT COUNT(*) AS n FROM sim_practice")["n"]
    url, g = start_guest(c)
    board = c.get(url).text
    assert 'id="b-map"' in board and 'id="p-initial"' in board and "Guest: nothing is saved" in board
    tags = db_one(app, "SELECT v.tags FROM paragraph p JOIN paragraph_version v ON v.id = p.current_version_id WHERE p.id = ?",
                  (g["paragraph_id"],))["tags"].split(",")
    g["tags"] = tags
    ch = api(c, g, action="chance").json()
    assert 0 <= ch["p_pass"] <= 1 and ch["yes_lo"] <= ch["yes_hi"]
    heard = api(c, g, action="lobby", iso3_target="USA").json()["heard"]
    assert heard
    g["lobbies"] = [{"iso3": "USA", "heard": heard, "position": 1, "tags": ",".join(tags)}]
    res = api(c, g, action="vote", my_vote="no").json()
    assert set(res) >= {"passed", "summary", "votes", "readings"} and res["votes"]["NZL"] == "no" and res["readings"][0]["iso3"] == "USA"
    assert db_one(app, "SELECT COUNT(*) AS n FROM sim_practice")["n"] == practices_before            # nothing kept
    assert not db_rows(app, "SELECT id FROM sim_practice_lobby")
    start_guest(guest(app))                                                                          # another guest: same committee
    assert db_one(app, "SELECT COUNT(*) AS n FROM committee WHERE guest_pack = 'comet_halcyon'")["n"] == 1


def test_a_guest_game_cant_be_bent(app):
    c = guest(app)
    _, g = start_guest(c)
    assert api(c, g, action="vote", my_vote="maybe").status_code == 400
    other = db_one(app, "SELECT id FROM paragraph WHERE id != ? ORDER BY id LIMIT 1", (g["paragraph_id"],))["id"]
    r = api(c, {**g, "paragraph_id": other}, action="chance")
    assert r.status_code == 404 and "error" in r.json()                                              # only the scenario's clauses
    assert api(c, {**g, "iso3": "XXX"}, action="chance").status_code == 400
    assert api(c, g, action="lobby", iso3_target=g["iso3"]).status_code == 400                      # not your own country
    six = [{"iso3": i, "heard": "x", "position": 0, "tags": ""} for i in ("USA", "CHN", "RUS", "IND", "JPN", "FRA")]
    assert api(c, {**g, "lobbies": six}, action="lobby", iso3_target="GBR").status_code == 400       # five conversations
    assert api(c, {**g, "mode": "saved", "pid": 1}, action="chance").status_code == 403             # saved games need sign-in
    assert c.request("POST", "/play/api", json={**g, "action": "chance"}).status_code == 403         # and every move its CSRF token
    assert "guest play" not in Client(app, base_url="http://testserver").__enter__().get("/play").text


def test_a_signed_in_students_game_is_saved_and_theirs(app, coord):
    st = db_one(app, "SELECT id FROM student WHERE active = 1 ORDER BY id DESC LIMIT 1")["id"]
    a = join_as(app, st)
    assert "Play solo" in a.get("/me").text
    r = a.post("/play/start", {"pack": "veloria", "iso3_veloria": "FRA"}, follow_redirects=False)
    assert r.headers["location"].startswith("/play/s/")
    pid = int(r.headers["location"].rsplit("/", 1)[1])
    page = a.get(f"/play/s/{pid}").text
    assert "Saved as you play" in page and 'id="b-map"' in page
    game = {"mode": "saved", "pid": pid}
    lob = api(a, game, action="lobby", iso3_target="USA").json()
    assert lob["heard"] and db_one(app, "SELECT COUNT(*) AS n FROM sim_practice_lobby WHERE practice_id = ?", (pid,))["n"] == 1
    assert api(a, game, action="read", id=lob["id"], position=1).json() == {"ok": True}
    assert api(a, game, action="chance").json()["p_pass"] >= 0
    res = api(a, game, action="vote", my_vote="yes").json()
    assert "passed" in res and db_one(app, "SELECT stage FROM sim_practice WHERE id = ?", (pid,))["stage"] == "voted"
    assert f"/play/s/{pid}" in a.get("/play").text                                                   # listed under Your games
    other = join_as(app, db_one(app, "SELECT id FROM student WHERE active = 1 AND id != ? ORDER BY id LIMIT 1", (st,))["id"])
    assert other.get(f"/play/s/{pid}").status_code == 403
    assert api(other, game, action="chance").status_code == 403
    assert "guest play" not in coord.get("/mun").text and "· solo" not in coord.get("/mun").text
