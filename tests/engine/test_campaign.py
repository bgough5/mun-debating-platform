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


def test_every_scenario_has_a_difficulty_label():
    from app.modules.mun.packfile import available
    from app.modules.sim.campaign.content import LEVEL_NAMES, SCENARIO_LEVEL
    assert {p["code"] for p in available()} <= set(SCENARIO_LEVEL)
    assert set(SCENARIO_LEVEL.values()) <= set(LEVEL_NAMES)


def test_a_pledged_permanent_member_abstains_except_on_its_red_lines(scenarios):
    scn = scenarios["sc_climate_security"]
    me = next(i for i in scn.isos if i not in scn.rule.veto)
    g = E.new_game(scn, me, seed=9)
    p5 = next(i for i in sorted(scn.rule.veto) if i not in E._others(g))
    with pytest.raises(E.GameError):
        E.apply(scn, g, {"do": "abstain", "iso3": p5})                       # no trust yet
    with pytest.raises(E.GameError):
        E.apply(scn, g, {"do": "abstain", "iso3": next(i for i in scn.isos if i not in scn.rule.veto and i not in E._others(g))})
    g["trust"][p5], g["influence"] = 1, 10
    g2, _ = E.apply(scn, g, {"do": "abstain", "iso3": p5})
    assert g2["pledges"] == [p5] and g2["trust"][p5] == -1
    for t in scn.tags:
        clause = {"id": "x", "tags": [t], "author": "you"}
        before, after = E.votes_on(scn, g, clause, my_vote="yes")[p5], E.votes_on(scn, g2, clause, my_vote="yes")[p5]
        if before == "no":
            assert after == ("no" if E.red_line(scn, p5, [t]) else "abstain"), t
        else:
            assert after == before


def _to_final(scn, g):
    g, _ = E.apply(scn, g, {"do": "speech", "stance": "open"})
    while g["summit"]["step"] == "clause":
        g, _ = E.apply(scn, g, {"do": "decide", "choice": "stand", "vote": "no"})
    return g


def test_a_failed_council_resolution_can_become_a_presidential_statement(scenarios):
    scn = scenarios["sc_climate_security"]
    me = next(i for i in scn.isos if i not in scn.rule.veto)
    g = E.new_game(scn, me, "quick", seed=4)
    vetoed = next(t for t in sorted(scn.tags) if any(E.red_line(scn, p5, [t]) for p5 in scn.rule.veto))
    mild = [t for t in sorted(scn.tags) if t != vetoed][:2]
    g["draft"] = [{"id": "d1", "text": "x", "tags": [vetoed], "author": "draft", "amended_by": []},
                  {"id": "d2", "text": "y", "tags": [vetoed] + mild[:1], "author": "draft", "amended_by": []}]
    E._open_summit(scn, g)
    g = _to_final(scn, g)
    g, out = E.apply(scn, g, {"do": "final", "vote": "no"})
    assert not out["final"]["passed"] and out["statement"] and g["phase"] == "summit" and g["summit"]["step"] == "statement"
    agreeable = [t for t in g["summit"]["statement_options"]
                 if "no" not in E.votes_on(scn, g, {"id": "s", "tags": [t], "author": "you"}, my_vote="yes").values()]
    g2, out = E.apply(scn, g, {"do": "statement", "tags": agreeable[:1] or g["summit"]["statement_options"][:1]})
    assert g2["phase"] == "done" and out["statement"]["adopted"] == bool(agreeable)
    r = g2["result"]
    assert r["statement"] == bool(agreeable) and r["paths"]["mandate"] <= 2 and r["paths"]["consensus"] <= 2 and r["paths"]["architect"] <= 1
    g3, out = E.apply(scn, g, {"do": "statement", "skip": True})
    assert not out["statement"]["adopted"] and not g3["result"]["statement"]


def test_no_statement_outside_the_council(scenarios):
    scn = scenarios["comet_halcyon"]
    g = E.new_game(scn, scn.isos[0], "quick", seed=4)
    E._open_summit(scn, g)
    g = _to_final(scn, g)
    g, out = E.apply(scn, g, {"do": "final", "vote": "no"})
    assert g["phase"] == "done" and "statement" not in out


def test_a_scenarios_own_events_come_up_labelled_and_a_spotlight_warms_its_champions(scenarios):
    scn = scenarios["sc_climate_security"]
    me = next(i for i in scn.isos if i not in scn.rule.veto)
    g = E.new_game(scn, me, seed=21)
    must = max(scn.tags, key=lambda t: sum(1 for i in scn.isos if (scn.positions.get(i, {}).get(t) or 0) >= 1))
    g["mandate"]["must"] = must                         # the commitment most delegations support, so the spotlight has fans
    scn.events = [{"id": "s1", "title": "A capital changes its mind", "body": "New instructions arrive for several delegations.",
                   "teaches": "Delegates act on instructions from their capitals.", "effect": {"spotlight": {"tag": must, "amount": 0.2}},
                   "scenario": True}]
    seen = None
    for _ in range(60):                                   # deal turns until the scenario's event comes up
        before = {i: g["sway"]["you"][i] for i in scn.isos if i not in E._others(g)}
        g2 = E.apply(scn, g, {"do": "end_turn"})[0]
        if g2["phase"] != "chapter":
            break
        if g2["event"]["id"] == "s1":
            seen = (g, g2)
            break
        g = g2
    assert seen, "the scenario's event never came up"
    g, g2 = seen
    assert g2["event"]["hypothetical"] is True                                    # a real topic: labelled
    fans = [i for i in scn.isos if i not in E._others(g) and ((scn.positions.get(i, {}).get(must) or 0) >= 1 or scn.dist([must])[i][0] >= 0.4)]
    assert fans and all(g2["sway"]["you"][i] > g["sway"]["you"][i] - 0.001 for i in fans)
    others = [i for i in scn.isos if i not in E._others(g) and i not in fans]
    assert all(abs(g2["sway"]["you"][i] - g["sway"]["you"][i]) < 0.31 for i in others)   # only the usual pulls, no spotlight


def test_every_commitment_can_be_proposed(scenarios):
    for scn in scenarios.values():
        offered = {t for c in scn.cards for t in c["tags"]} | {t for c in scn.draft for t in c["tags"]}
        assert offered == set(scn.tags), scn.code
