"""D-101: The Session's rules engine. Countries' positions come from the real vote engine; a game is plain JSON and
replays exactly from its seed; the working group decides on changes to other people's text; bots of every style
can finish a game on every kind of committee."""
import json

import pytest

from app.db import SYSTEM
from app.modules.sim import play
from app.modules.sim.campaign import bots as B
from app.modules.sim.campaign import engine as E
from app.modules.sim.campaign.scenario import load


@pytest.fixture
def scenarios(app):
    with app.state.db.write(SYSTEM) as w:
        ids = {code: play.guest_committee(w, code) for code in ("comet_halcyon", "sc_climate_security")}
    with app.state.db.read() as conn:
        yield {code: load(conn, cid, code) for code, cid in ids.items()}


def test_positions_come_from_the_vote_engine(app, scenarios):
    from app.modules.mun.predict import run_prediction
    scn = scenarios["comet_halcyon"]
    with app.state.db.read() as conn:
        pid = play.operative_ids(conn, scn.committee_id)[0]
        tags = scn.draft[0]["tags"]
        real = {d.iso3: (round(d.mu, 4), round(d.sigma, 4)) for d in run_prediction(conn, "paragraph", pid, runs=50, tags_override=tags)["dists"]}
    assert scn.dist(tags) == real


def test_a_game_is_json_and_replays_exactly(scenarios):
    scn = scenarios["comet_halcyon"]
    iso = scn.isos[0]
    g1 = E.new_game(scn, iso, seed=42)
    assert json.loads(json.dumps(g1)) == g1
    other = next(i for i in scn.isos if i not in E._others(g1))
    moves = [{"do": "lobby", "iso3": other}, {"do": "read", "iso3": other}, {"do": "end_turn"}]
    a, b = g1, E.new_game(scn, iso, seed=42)
    for m in moves:
        before = json.dumps(a, sort_keys=True)
        a, _ = E.apply(scn, a, m)
        assert json.dumps(json.loads(before), sort_keys=True) == before          # apply never changes the game it's given
        b, _ = E.apply(scn, b, m)
    assert a == b and json.loads(json.dumps(a)) == a


def test_instructions_rivals_and_illegal_moves(scenarios):
    scn = scenarios["sc_climate_security"]
    for iso in scn.isos:
        g = E.new_game(scn, iso, difficulty="hard", seed=7)
        m = g["mandate"]
        assert len({m["must"], m["also"], m["red"]}) == 3
        assert not any(r["iso3"] in scn.rule.veto for r in g["rivals"])     # one rival's veto would decide every vote
        assert len(g["rivals"]) == 3 and g["iso3"] not in [r["iso3"] for r in g["rivals"]]
    g = E.new_game(scn, scn.isos[0], seed=7)
    with pytest.raises(E.GameError):
        E.apply(scn, g, {"do": "lobby", "iso3": g["iso3"]})                   # not yourself
    with pytest.raises(E.GameError):
        E.apply(scn, g, {"do": "lobby", "iso3": g["rivals"][0]["iso3"]})      # rivals won't be moved
    with pytest.raises(E.GameError):
        E.apply(scn, g, {"do": "decide", "choice": "stand", "vote": "yes"})   # no summit yet
    with pytest.raises(E.GameError):
        E.new_game(scn, "XXX")


def test_the_working_group_keeps_a_clause_it_wants(scenarios):
    scn = scenarios["comet_halcyon"]
    g = E.new_game(scn, scn.isos[0], seed=3)
    for c in g["draft"]:
        votes = E.votes_on(scn, g, c)
        wanted = E.tally(scn.rule, votes, len(votes)).passed
        g2, out = E.apply(scn, g, {"do": "strike", "clause": c["id"]})
        assert out["accepted"] == (not wanted)
        assert (c["id"] in [x["id"] for x in g2["draft"]]) == bool(wanted)
        assert g2["influence"] == g["influence"] - (0 if wanted else E.R["strike_cost"])
        g2["ap"] = g["ap"]


def test_a_broken_promise_costs_trust_and_respect(scenarios):
    scn = scenarios["comet_halcyon"]
    g = E.new_game(scn, scn.isos[0], seed=5)
    c = g["draft"][0]
    fan = next(i for i in scn.isos if i not in E._others(g) and scn.dist(c["tags"])[i][0] >= 0.4)
    g, _ = E.apply(scn, g, {"do": "promise", "iso3": fan, "clause": c["id"]})
    assert g["trust"][fan] == 1
    other = next(t for t in scn.tags if t not in c["tags"])
    g["influence"] = 10
    g2, out = E.apply(scn, g, {"do": "amend", "clause": c["id"], "add": other})
    if out["accepted"]:
        assert g2["trust"][fan] == -1 and g2["respect"] == g["respect"] - 1
        assert [p["kept"] for p in g2["promises"]] == [False]


@pytest.mark.parametrize("style", sorted(B.STYLES))
@pytest.mark.parametrize("code", ["comet_halcyon", "sc_climate_security"])
def test_every_style_finishes_a_game(scenarios, code, style):
    scn = scenarios[code]
    g = E.new_game(scn, scn.isos[3], "quick", "standard", B.STYLES[style] or "mandate", seed=11)
    g = B.Bot(scn, style, 11).play(g)
    assert g["phase"] == "done"
    r = g["result"]
    assert set(r["paths"]) == set(E.K.PATHS) and all(0 <= v <= 3 for v in r["paths"].values())
    assert r["grade"] == r["paths"][g["path"]]
    assert g["summit"]["final"]["passed"] in (True, False) and json.loads(json.dumps(g)) == g
