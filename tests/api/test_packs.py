"""D-097: scenario packs as data files, played alone or with a class. Every pack in app/db/seed/packs/ must pass the
validator and install; the validator catches what a careless or delegated author might get wrong; a student can play any
pack on their own without a teacher setting anything up."""
import copy
import json

import pytest

from app.db import SYSTEM
from app.modules.mun import packfile as PF
from tests.api.helpers import join_as
from tests.conftest import db_one, db_rows

PACKS = sorted(p for p in PF.PACK_DIR.glob("*.json") if not p.name.startswith("_"))


@pytest.mark.parametrize("path", PACKS, ids=[p.stem for p in PACKS])
def test_every_pack_validates_and_installs(app, path):
    pack = json.loads(path.read_text(encoding="utf-8"))
    assert PF.validate(pack, path.stem) == []
    with app.state.db.write(SYSTEM) as w:
        info = PF.install(w, path.stem)
    n_paras = len(pack["resolution"]["preambular"]) + len(pack["resolution"]["operative"])
    assert len(info["paragraphs"]) == n_paras and set(info["delegations"]) == set(pack["countries"])
    kind = "demo_unverified" if pack["fictional"] else "ai_estimate"
    ev = db_rows(app, "SELECT source_type, summary FROM evidence WHERE topic_id = (SELECT topic_id FROM committee WHERE id = ?)",
                 (info["committee_id"],))
    assert ev and all(e["source_type"] == kind for e in ev)
    assert all("not" in e["summary"] for e in ev)                 # every position says what it isn't


def test_veloria_is_the_evatt_demo(app, coord):
    ids = [r["id"] for r in db_rows(app, "SELECT id FROM student WHERE active = 1 ORDER BY id LIMIT 3")]
    r = coord.post("/start", {"op": "start", "kind": "evatt", "student_id": [str(i) for i in ids]}, follow_redirects=False)
    sid = int(r.headers["location"].rsplit("/", 1)[1])
    com = db_one(app, "SELECT cm.name FROM committee cm JOIN live_session s ON s.committee_id = cm.id WHERE s.id = ?", (sid,))
    assert com["name"] == "Security Council: the situation in Veloria (demo)"


def test_the_validator_catches_what_authors_get_wrong():
    good = json.loads((PF.PACK_DIR / "veloria.json").read_text(encoding="utf-8"))
    assert PF.validate(good, "veloria") == []

    def broken(change):
        p = copy.deepcopy(good)
        change(p)
        return " ".join(PF.validate(p, "veloria"))

    assert "match the file name" in broken(lambda p: p.update(code="other"))
    assert "exactly 15 members" in broken(lambda p: p["countries"].pop())
    assert "isn't a country" in broken(lambda p: p["countries"].__setitem__(5, "XXX"))
    assert "isn't one of the pack's tags" in broken(lambda p: p["resolution"]["operative"][0].__setitem__("tags", ["nope"]))
    assert "ends with" in broken(lambda p: p["resolution"]["preambular"][0].__setitem__("text", "Recalling a thing without a comma"))
    assert "-2 (strongly oppose)" in broken(lambda p: p["positions"]["USA"].__setitem__("ceasefire", 5))
    assert "no markup" in broken(lambda p: p.update(summary="<script>alert(1)</script> a scenario summary that is long enough"))
    assert "no links" in broken(lambda p: p.update(summary="See https://example.com for this scenario summary text here"))
    assert "source link" in broken(lambda p: p.update(fictional=False, news=[]))         # a real topic needs sources
    assert "up to four" in broken(lambda p: p["sources"].update(USA=["https://a.example/x"] * 5))
    assert "only for fictional" in broken(lambda p: p.update(fictional=False, positions={}))  # and no invented news
    template = json.loads((PF.PACK_DIR / "_template.json").read_text(encoding="utf-8"))
    assert PF.validate(template, "replace_with_file_name") == []                          # the template's shape is valid
    assert "veloria" in {p["code"] for p in PF.available()} and "_template" not in {p["code"] for p in PF.available()}


def test_the_tool_rejects_an_unfilled_template(tmp_path):
    from tools.validate_pack import check
    t = tmp_path / "my_pack.json"
    t.write_text((PF.PACK_DIR / "_template.json").read_text(encoding="utf-8"), encoding="utf-8")
    assert "REPLACE" in check(t)[0]
    assert check(PF.PACK_DIR / "veloria.json") == []


def test_a_student_plays_a_pack_alone(app, coord):
    st = db_one(app, "SELECT id FROM student WHERE active = 1 ORDER BY id DESC LIMIT 1")["id"]
    a = join_as(app, st)
    page = a.get("/me/sim").text
    assert "Play a scenario on your own" in page and "href=\"/play\"" in page          # the board game is the way in (D-099)
    r = a.post("/me/sim/scenario", {"pack": "veloria", "iso3_veloria": "FRA"}, follow_redirects=False)
    assert r.status_code in (302, 303)
    pid = int(r.headers["location"].rsplit("/", 1)[1])
    run = db_one(app, "SELECT sp.committee_id, m.iso3 FROM sim_practice sp JOIN sim_practice_member m ON m.practice_id = sp.id WHERE sp.id = ?", (pid,))
    assert run["iso3"] == "FRA"
    para = db_one(app, "SELECT paragraph_id FROM sim_practice WHERE id = ?", (pid,))["paragraph_id"]
    ops = [r["id"] for r in db_rows(app, "SELECT p.id FROM paragraph p JOIN resolution r ON r.id = p.resolution_id "
                                         "WHERE r.committee_id = ? AND p.kind = 'operative' ORDER BY p.position", (run["committee_id"],))]
    with app.state.db.read() as conn:
        assert para == PF.closest_vote(conn, ops)                                          # starts on the closest vote
    com = db_one(app, "SELECT * FROM committee WHERE id = ?", (run["committee_id"],))
    assert com["solo_student_id"] == st and com["class_id"] is None
    assert a.get(f"/me/sim/{pid}").status_code == 200
    assert "· solo" not in coord.get("/mun").text and "· solo" not in coord.get("/chair").text   # not in teachers' lists
    other = join_as(app, db_one(app, "SELECT id FROM student WHERE active = 1 AND id != ? ORDER BY id LIMIT 1", (st,))["id"])
    assert other.get(f"/mun/committees/{com['id']}").status_code in (303, 403)              # nobody else can open it
    assert a.post("/me/sim/scenario", {"pack": "veloria", "iso3_veloria": "AUS"}).status_code >= 400   # not on the Council


def test_teachers_can_pick_a_pack_on_start(app, coord):
    page = coord.get("/start").text
    assert 'name="pack"' in page and "The situation in Veloria" in page
    ids = [r["id"] for r in db_rows(app, "SELECT id FROM student WHERE active = 1 ORDER BY id LIMIT 2")]
    r = coord.post("/start", {"op": "start", "kind": "unaa", "pack": "veloria", "student_id": [str(i) for i in ids]},
                   follow_redirects=False)
    sid = int(r.headers["location"].rsplit("/", 1)[1])
    com = db_one(app, "SELECT cm.name FROM committee cm JOIN live_session s ON s.committee_id = cm.id WHERE s.id = ?", (sid,))
    assert com["name"].startswith("Security Council: the situation in Veloria (demo)")


def test_the_validator_checks_the_campaign_section():
    """D-101 phase 5: extra clause cards and the scenario's own events for The Session."""
    good = json.loads((PF.PACK_DIR / "veloria.json").read_text(encoding="utf-8"))
    tag = sorted(good["tags"])[0]

    def with_campaign(c):
        return " ".join(PF.validate({**good, "campaign": c}, "veloria"))
    ok = {"cards": [{"text": "Calls upon all parties to agree a ceasefire within one week;", "tags": [tag]}],
          "events": [{"title": "A regional group meets", "body": "The group's ministers meet on the sidelines and compare instructions.",
                      "teaches": "Regional groups coordinate positions before big votes.", "effect": {"spotlight": {"tag": tag, "amount": 0.15}}}]}
    assert with_campaign(ok) == ""
    assert "one to three of the pack's tags" in with_campaign({"cards": [{"text": ok["cards"][0]["text"], "tags": ["nope"]}]})
    assert "ends with ; or ." in with_campaign({"cards": [{"text": "Calls upon all parties to agree a ceasefire", "tags": [tag]}]})
    assert "exactly one of" in with_campaign({"events": [{**ok["events"][0], "effect": {"ap": 1, "influence": 2}}]})
    assert "0.1 to 0.25" in with_campaign({"events": [{**ok["events"][0], "effect": {"spotlight": {"tag": tag, "amount": 0.9}}}]})
    assert "(not 0)" in with_campaign({"events": [{**ok["events"][0], "effect": {"ap": 0}}]})
    assert "isn't an effect" in with_campaign({"events": [{**ok["events"][0], "effect": {"win": 1}}]})
