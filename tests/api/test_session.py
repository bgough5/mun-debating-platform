"""D-101, phase 2: The Session's shell. Anyone can open the title screen and set up a session. A guest's session is
signed by the server and kept in their browser, never stored; it can't be edited. A signed-in student's session is
saved on every move, is theirs alone, and goes when the student is erased."""
import json

from app.db import SYSTEM
from tests.api.helpers import join_as
from tests.conftest import Client, db_one


def api(c, body):
    return c.request("POST", "/session/api", json=body, headers={"X-CSRF-Token": c.csrf()})


def guest(app) -> Client:
    return Client(app, base_url="http://testserver").__enter__()


def test_anyone_can_open_the_title_and_set_up(app):
    c = guest(app)
    t = c.get("/session")
    assert t.status_code == 200 and "<h1" in t.text and "The Session" in t.text and "New session" in t.text and "Quick vote" in t.text
    n = c.get("/session/new").text
    assert "Comet Halcyon-7" in n and "Beginner" in n and "Expert" in n and "Take your seat" in n
    seats = c.get("/session/seats/comet_halcyon").text
    assert 'data-pick="iso3"' in seats and 'id="b-map"' in seats and ("Easier" in seats or "Balanced" in seats or "Harder" in seats)
    assert c.get("/session/seats/nope").status_code == 404


def test_a_guest_session_is_signed_kept_in_the_browser_and_cant_be_edited(app):
    c = guest(app)
    before = db_one(app, "SELECT COUNT(*) AS n FROM campaign_save")["n"]
    r = api(c, {"do": "new", "pack": "comet_halcyon", "iso3": "NZL", "length": "quick", "difficulty": "easy", "path": "consensus"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["url"] == "/session/guest/comet_halcyon" and j["state"]["iso3"] == "NZL" and len(j["sig"]) == 64
    assert j["view"]["you"]["name"] == "New Zealand" and j["view"]["mandate"]["must"]["label"]
    page = c.get("/session/guest/comet_halcyon").text
    assert 'data-mode="guest"' in page and 'id="b-map"' in page
    as_js = json.loads(json.dumps(j["state"]), parse_float=lambda t: int(float(t)) if float(t).is_integer() else float(t))
    assert json.dumps(as_js) != json.dumps(j["state"])      # a browser keeps 0.0 as 0: the signature must still hold
    m = api(c, {"do": "move", "state": as_js, "sig": j["sig"], "action": {"do": "end_turn"}})
    assert m.status_code == 200 and m.json()["view"]["turn"] == 2 and m.json()["sig"] != j["sig"]
    rich = {**j["state"], "influence": 99}
    bad = api(c, {"do": "move", "state": rich, "sig": j["sig"], "action": {"do": "end_turn"}})
    assert bad.status_code == 400 and "changed outside" in bad.json()["error"]
    illegal = api(c, {"do": "move", "state": j["state"], "sig": j["sig"], "action": {"do": "lobby", "iso3": "NZL"}})
    assert illegal.status_code == 400 and "another delegation" in illegal.json()["error"]
    assert c.request("POST", "/session/api", json={"do": "view", "state": j["state"], "sig": j["sig"]}).status_code == 403   # CSRF
    assert db_one(app, "SELECT COUNT(*) AS n FROM campaign_save")["n"] == before          # nothing about a guest is kept


def test_a_students_session_is_saved_and_theirs_alone(app):
    from app.retention import erase_student
    st = db_one(app, "SELECT id FROM student WHERE active = 1 ORDER BY id DESC LIMIT 1")["id"]
    a = join_as(app, st)
    j = api(a, {"do": "new", "pack": "comet_halcyon", "iso3": "FRA", "length": "standard", "difficulty": "standard", "path": "mandate"}).json()
    assert j["url"].startswith("/session/s/") and "state" not in j
    sid = int(j["url"].rsplit("/", 1)[1])
    assert db_one(app, "SELECT student_id, phase FROM campaign_save WHERE id = ?", (sid,)) == {"student_id": st, "phase": "chapter"}
    assert 'data-mode="saved"' in a.get(j["url"]).text and "Comet" in a.get("/session").text
    m = api(a, {"do": "move", "save_id": sid, "action": {"do": "end_turn"}}).json()
    assert m["view"]["turn"] == 2 and db_one(app, "SELECT chapter FROM campaign_save WHERE id = ?", (sid,))["chapter"] == 1
    other = join_as(app, db_one(app, "SELECT id FROM student WHERE active = 1 AND id != ? ORDER BY id LIMIT 1", (st,))["id"])
    assert other.get(j["url"]).status_code == 403
    assert api(other, {"do": "view", "save_id": sid}).status_code == 403
    assert api(guest(app), {"do": "view", "save_id": sid}).status_code == 403
    with app.state.db.write(SYSTEM) as w:
        erase_student(w, st)
    assert db_one(app, "SELECT COUNT(*) AS n FROM campaign_save WHERE student_id = ?", (st,))["n"] == 0


def test_a_guest_plays_a_quick_session_to_the_end(app):
    """Phase 4: four turns, the summit (speech, every clause, the whole resolution) and the result, all through the API."""
    c = guest(app)
    j = api(c, {"do": "new", "pack": "comet_halcyon", "iso3": "NZL", "length": "quick", "difficulty": "easy", "path": "mandate"}).json()
    st, sig = j["state"], j["sig"]

    def move(action):
        nonlocal st, sig
        r = api(c, {"do": "move", "state": st, "sig": sig, "action": action})
        assert r.status_code == 200, r.text
        r = r.json()
        st, sig = r["state"], r["sig"]
        return r
    r = {"view": j["view"]}
    while r["view"]["phase"] == "chapter":                      # four turns, or three if the deadline is brought forward
        r = move({"do": "end_turn"})
    assert r["view"]["phase"] == "summit" and r["view"]["summit"]["step"] == "speech"
    r = move({"do": "speech", "stance": "bridge"})
    while r["view"]["summit"]["step"] == "clause":
        cur = r["view"]["summit"]["current"]
        assert 0 <= cur["chance"]["p_pass"] <= 1 and cur["n"] <= cur["of"]
        r = move({"do": "decide", "choice": "stand", "vote": "yes"})
        assert set(r["out"]["votes"]) >= {"NZL"} and r["out"]["votes"]["NZL"] == "yes"
    assert r["view"]["summit"]["step"] == "final" and len(r["view"]["summit"]["results"]) >= 1
    r = move({"do": "final", "vote": "yes"})
    assert r["view"]["phase"] == "done" and r["view"]["result"]["grade"] in (0, 1, 2, 3)
    assert set(r["view"]["result"]["paths"]) == {"mandate", "consensus", "architect", "kingmaker"}
    after = api(c, {"do": "move", "state": st, "sig": sig, "action": {"do": "end_turn"}})
    assert after.status_code == 400 and "over" in after.json()["error"]


def test_the_almanac_the_debrief_and_teachers_results(app, coord):
    """Phase 6: the Almanac is open to all; a finished session has a debrief; teachers see paths and grades, not words."""
    c = guest(app)
    assert "Comet Halcyon-7" in c.get("/session/almanac").text
    alm = c.get("/session/almanac/ga_migration").text
    assert "How a vote is decided" in alm and "estimates from the linked sources" in alm and "Country files" in alm
    assert "invented for practice" in c.get("/session/almanac/comet_halcyon").text
    assert c.get("/session/almanac/nope").status_code == 404
    st = db_one(app, "SELECT id FROM student WHERE active = 1 ORDER BY id DESC LIMIT 1")["id"]
    a = join_as(app, st)
    j = api(a, {"do": "new", "pack": "comet_halcyon", "iso3": "NZL", "length": "quick", "difficulty": "easy", "path": "kingmaker"}).json()
    sid = int(j["url"].rsplit("/", 1)[1])
    body = {"do": "move", "save_id": sid}
    a_text = "Calls on every observatory to publish its readings at once, a private sentence of mine;"
    card = j["view"]["cards"][0]["id"]
    api(a, {**body, "action": {"do": "propose", "card": card, "text": a_text}})
    r = {"view": j["view"]}
    while r["view"]["phase"] == "chapter":
        r = api(a, {**body, "action": {"do": "end_turn"}}).json()
    r = api(a, {**body, "action": {"do": "speech", "stance": "open"}}).json()
    while r["view"]["summit"]["step"] == "clause":
        r = api(a, {**body, "action": {"do": "decide", "choice": "stand", "vote": "yes"}}).json()
    r = api(a, {**body, "action": {"do": "final", "vote": "yes"}}).json()
    d = r["view"]["debrief"]
    assert d and {t["path"] for t in d["tips"]} == {"mandate", "consensus", "architect", "kingmaker"}
    if r["view"]["summit"]["final"]["tags"]:
        row = d["countries"][0]
        assert {"model", "yours", "rivals", "group", "mood", "vote", "turned"} <= set(row)
    page = coord.get("/session/results").text
    assert "New Zealand" in page and "Kingmaker" in page and "private sentence" not in page
    assert guest(app).get("/session/results", follow_redirects=False).status_code in (302, 303, 401, 403)


def test_the_view_shows_the_crisis_offers_and_rival_personalities(app):
    """Phase 7: the chapter's crisis, the offers at the door (answered through the API) and each rival's style."""
    c = guest(app)
    for seed_iso in ("NZL", "IND", "BRA", "JPN", "DEU", "NGA"):
        j = api(c, {"do": "new", "pack": "comet_halcyon", "iso3": seed_iso, "length": "standard", "difficulty": "hard", "path": "mandate"}).json()
        v = j["view"]
        assert v["crisis"]["chapter"] == 1 and v["crisis"]["title"] and v["crisis"]["teaches"]
        assert all(r["style_name"] and r["style_what"] for r in v["rivals"]) and len({r["style"] for r in v["rivals"]}) == 3
        assert v["turns"] in (5, 6)                                                   # stage 1 lasts 6 turns; a deadline crisis takes one off
        for _ in range(4):                                                            # none on the first turn
            j = api(c, {"do": "move", "state": j["state"], "sig": j["sig"], "action": {"do": "end_turn"}}).json()
            v = j["view"]
            if any(x["kind"] == "offer" for x in v["visits"]):
                break
        if any(x["kind"] == "offer" for x in v["visits"]):
            break
    o = next(x for x in v["visits"] if x["kind"] == "offer")                       # an offer comes in person (phase 14)
    assert o["name"] and o["text"].startswith(o["name"]) and len(v["visits"]) <= 2
    m = api(c, {"do": "move", "state": j["state"], "sig": j["sig"], "action": {"do": "visit", "id": o["id"], "choice": "refuse"}})
    assert m.status_code == 200 and all(x["id"] != o["id"] for x in m.json()["view"]["visits"])
    again = api(c, {"do": "move", "state": m.json()["state"], "sig": m.json()["sig"], "action": {"do": "visit", "id": o["id"], "choice": "accept"}})
    assert again.status_code == 400 and "over" in again.json()["error"]



def test_the_view_shows_the_vote_as_it_stands_your_staff_and_counter_moves(app):
    """Phase 8: the tug-of-war projection, advisers (posted and hired through the API), the reserve and securing."""
    c = guest(app)
    j = api(c, {"do": "new", "pack": "comet_halcyon", "iso3": "NZL", "length": "quick", "difficulty": "hard", "path": "mandate"}).json()
    v = j["view"]
    t = v["tug"]
    assert t["yes"] + t["no"] + t["abstain"] == t["of"] and isinstance(t["passed"], bool) and t["summary"]
    assert v["staff"] and all(a["kind_name"] and a["rank"] and a["report"] is None for a in v["staff"])
    assert {k["code"] for k in v["staff_kinds"]} == {"analyst", "regional", "legal"}
    assert v["reserve"] == 0 and v["costs"]["hire"] and v["costs"]["secure"]
    st, sig = j["state"], j["sig"]

    def move(action):
        nonlocal st, sig
        r = api(c, {"do": "move", "state": st, "sig": sig, "action": action})
        assert r.status_code == 200, r.text
        st, sig = r.json()["state"], r.json()["sig"]
        return r.json()["view"]
    rival = v["rivals"][0]["iso3"]
    v = move({"do": "post", "adviser": v["staff"][0]["id"], "iso3": rival})
    assert v["staff"][0]["post"] == rival and v["tokens"][rival]["studied_by"] == v["staff"][0]["name"]
    v = move({"do": "reserve"})
    assert v["reserve"] == 1 and v["ap"] >= 0
    v = move({"do": "end_turn"})
    assert v["staff"][0]["report"]["text"] and v["staff"][0]["report"]["sure"]
    assert v["reserve"] == 0                                       # used against a rival, or lapsed



def test_the_view_shows_dossiers_the_deal_table_and_the_capital(app):
    """Phase 9: every delegation's dossier (real figures with years and the source), the deal terms, your capital's
    confidence and your budget; a deal made through the API."""
    c = guest(app)
    j = api(c, {"do": "new", "pack": "comet_halcyon", "iso3": "NZL", "length": "quick", "difficulty": "easy", "path": "mandate"}).json()
    v = j["view"]
    assert v["respect"] == 4 and "capital" not in v and v["budget"]["total"] >= 1 and v["deal_ready"]
    you = v["tokens"]["NZL"]["dossier"]
    assert you["known"] and "World Bank" in you["source"] and any(r["label"] == "Economy (GDP)" for r in you["rows"])
    free = [i for i, t in v["tokens"].items() if t.get("deal")]
    assert free and all(not v["tokens"][r["iso3"]].get("deal") for r in v["rivals"])          # no deals with rivals
    iso = next(i for i in free if "influence" in v["tokens"][i]["deal"]["get"])
    t = v["tokens"][iso]["deal"]
    give = sorted(t["give"], key=lambda k: -t["give"][k])
    r = api(c, {"do": "move", "state": j["state"], "sig": j["sig"], "action": {"do": "deal", "iso3": iso, "give": give, "get": ["influence"]}})
    assert r.status_code == 200, r.text
    out, v2 = r.json()["out"], r.json()["view"]
    assert "deal" in out and not v2["deal_ready"] and v2["ap"] == v["ap"] - v["costs"]["deal_ap"]


def test_scenarios_open_in_order_and_the_record(app):
    """Ben, 8 Nov: the first scenario is open; gold (on any path) in one opens the next. The record is worked out
    from the student's own finished sessions only."""
    from app.modules.sim.campaign import store as S
    cards = S.scenario_cards()
    first, second = cards[0]["code"], cards[1]["code"]
    p = S.profile(cards, [])
    assert not p["scenarios"][0]["locked"] and all(x["locked"] for x in p["scenarios"][1:])
    easy = {"pack": first, "iso3": "NZL", "country": "New Zealand", "path": "mandate", "difficulty": "easy",
            "result": {"paths": {"mandate": 3, "consensus": 0, "architect": 0, "kingmaker": 0}, "passed": True}}
    p = S.profile(cards, [easy])
    assert p["scenarios"][0]["medal"] == "Gold" and p["scenarios"][1]["locked"]           # gold on Easy doesn't open the next
    won = {"pack": first, "iso3": "NZL", "country": "New Zealand", "path": "mandate", "difficulty": "standard",
           "result": {"paths": {"mandate": 2, "consensus": 3, "architect": 0, "kingmaker": 0}, "passed": True}}
    p = S.profile(cards, [won])
    assert not p["scenarios"][1]["locked"] and p["scenarios"][2]["locked"] and p["scenarios"][0]["medal"] == "Gold"
    assert p["countries"][0] == {"iso3": "NZL", "name": "New Zealand", "best": 3, "medal": "Gold"}
    assert {x["code"]: x["best"] for x in p["paths"]}["consensus"] == 3 and p["medals"]["Gold"] == 1
    assert not any(x["locked"] for x in S.profile(cards, [], everything_open=True)["scenarios"])   # staff
    st = db_one(app, "SELECT id FROM student WHERE active = 1 ORDER BY id LIMIT 1")["id"]
    a = join_as(app, st)
    r = api(a, {"do": "new", "pack": second, "iso3": "NZL", "length": "quick", "difficulty": "standard", "path": "mandate"})
    assert r.status_code == 403 and "gold" in r.json()["error"]                    # locked until gold in the first
    page = a.get("/session/new").text
    assert "Locked: win gold on Standard or Hard in" in page
    rec = a.get("/session/profile")
    assert rec.status_code == 200 and "Your record" in rec.text and '"locked": true' in rec.text
    g = guest(app).get("/session/profile")
    assert g.status_code == 200 and '"profile": null' in g.text                    # a guest's record is in their browser
