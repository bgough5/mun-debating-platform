"""D-101, phase 8: rivals that play to win, your staff of advisers, counter-moves (reserve, secure, right of reply)
and the golden rule of the UN: don't vote down progress because it isn't everything you wanted."""
import json

import pytest

from app.db import SYSTEM
from app.modules.sim import play
from app.modules.sim.campaign import engine as E
from app.modules.sim.campaign.scenario import load


@pytest.fixture
def scenarios(app):
    with app.state.db.write(SYSTEM) as w:
        ids = {code: play.guest_committee(w, code) for code in ("comet_halcyon", "sc_climate_security")}
    with app.state.db.read() as conn:
        yield {code: load(conn, cid, code) for code, cid in ids.items()}


def test_big_delegations_bring_more_but_greener_staff(scenarios):
    scn = scenarios["sc_climate_security"]
    p5 = next(m for m in scn.members if m.p5)
    minor = next(m for m in scn.members if not m.p5 and not m.major)
    assert [a["stars"] for a in E.new_game(scn, p5.iso3, seed=1)["staff"]] == [1, 1, 1, 1]
    assert [a["stars"] for a in E.new_game(scn, minor.iso3, seed=1)["staff"]] == [2, 2]
    major = next((m for m in scn.members if m.major and not m.p5), None)
    if major:
        assert [a["stars"] for a in E.new_game(scn, major.iso3, seed=1)["staff"]] == [1, 1, 2]
    for m in scn.members:                                              # every mission starts with four stars in all
        assert sum(a["stars"] for a in E.new_game(scn, m.iso3, seed=2)["staff"]) == 4


def test_hiring_and_posting_advisers(scenarios):
    scn = scenarios["comet_halcyon"]
    g = E.new_game(scn, scn.isos[0], seed=3, length="quick")   # every tool open at once
    g["influence"] = 40
    while len(g["staff"]) < E.R["staff_max"]:
        g, out = E.apply(scn, g, {"do": "hire", "kind": "legal"})
        assert g["staff"][-1]["stars"] == 1 and g["staff"][-1]["kind"] == "legal"
    assert g["influence"] == 40 - E.R["hire_cost"] * (E.R["staff_max"] - len(E.new_game(scn, scn.isos[0], seed=3)["staff"]))
    with pytest.raises(E.GameError):
        E.apply(scn, g, {"do": "hire", "kind": "analyst"})                       # no more than five
    rival = g["rivals"][0]["iso3"]
    a1, a2 = g["staff"][0]["id"], g["staff"][1]["id"]
    g, _ = E.apply(scn, g, {"do": "post", "adviser": a1, "iso3": rival})
    with pytest.raises(E.GameError):
        E.apply(scn, g, {"do": "post", "adviser": a2, "iso3": rival})            # one adviser per delegation
    with pytest.raises(E.GameError):
        E.apply(scn, g, {"do": "post", "adviser": a2, "iso3": g["iso3"]})        # not your own
    assert g["staff"][0]["report"] is None
    g, _ = E.apply(scn, g, {"do": "end_turn"})
    rep = g["staff"][0]["report"]
    assert rep and rep["sure"] in ("a hunch", "fairly sure", "certain") and rep["at"] == rival   # a report after a full turn
    assert any(x["kind"] == "staff" for x in g["log"])


def test_a_three_star_adviser_is_always_right_and_a_right_report_earns_promotion(scenarios):
    scn = scenarios["comet_halcyon"]
    for seed in range(1, 25):
        g = E.new_game(scn, scn.isos[seed % len(scn.isos)], seed=seed, length="quick")
        adv = g["staff"][0]
        adv.update(stars=3, kind="analyst")
        rival = g["rivals"][0]["iso3"]
        g, _ = E.apply(scn, g, {"do": "post", "adviser": adv["id"], "iso3": rival})
        g, _ = E.apply(scn, g, {"do": "end_turn"})
        cl = g["staff"][0]["claim"]
        if cl:
            assert cl["right"] and cl["target"] == g["intent"][rival]["target"]
    adv = {"name": "Reyes", "stars": 1, "xp": 0}
    g = {"log": [], "phase": "chapter", "chapter": 1, "turn": 1}
    for _ in range(E.PROMOTE[2]):
        E._xp(g, adv, "Their warning proved right.")
    assert adv["stars"] == 2 and any(x["kind"] == "promote" for x in g["log"])


def test_rivals_plan_for_their_own_instructions_and_hard_ones_answer_your_last_turn(scenarios):
    scn = scenarios["comet_halcyon"]
    g = E.new_game(scn, scn.isos[0], difficulty="hard", seed=5)
    rv = g["rivals"][0]
    opts = E._rival_options(scn, g, rv)
    assert opts and all(o[0] >= opts[i + 1][0] for i, o in enumerate(opts[:-1]))     # best first
    for v, (kind, target), cost in opts:
        if kind == "propose":
            assert rv["want"] in next(c for c in scn.cards if c["id"] == target)["tags"]
        if kind in ("amend", "strike") and next(c for c in g["draft"] if c["id"] == target)["author"] != "you":
            assert rv["block"] in next(c for c in g["draft"] if c["id"] == target)["tags"]
    lobbies = [o for o in opts if o[1][0] == "lobby"]
    if lobbies:
        iso = lobbies[-1][1][1]
        g["last_touched"] = [iso]
        calm = {o[1]: o[0] for o in E._rival_options(scn, g, rv, react=False)}
        hard = {o[1]: o[0] for o in E._rival_options(scn, g, rv, react=True)}
        assert hard[("lobby", iso)] > calm[("lobby", iso)]                    # it goes after the delegation you just worked on


def test_a_reserve_answers_the_first_rival_move_against_you(scenarios):
    scn = scenarios["comet_halcyon"]
    g = E.new_game(scn, scn.isos[0], seed=6, length="quick")
    rv = g["rivals"][0]
    friend = next(i for i in scn.isos if i not in E._others(g))
    g["sway"]["you"][friend] = 1.0
    g, _ = E.apply(scn, g, {"do": "reserve"})
    assert g["reserve"] == 1
    with pytest.raises(E.GameError):
        E.apply(scn, g, {"do": "reserve"})                                       # one at a time
    before = g["sway"][rv["iso3"]][friend]
    rv["influence"] = 10
    assert E._rival_act(scn, g, rv, "lobby", friend, 1, 0.3)
    assert g["sway"][rv["iso3"]][friend] == before and g["reserve"] == 0      # the move came to nothing
    assert any(x["kind"] == "counter" for x in g["log"])


def test_a_secured_delegation_is_twice_as_hard_to_move(scenarios):
    """A signed commitment now comes from the deal table (8 Nov); it still halves a rival's push."""
    scn = scenarios["comet_halcyon"]
    g = E.new_game(scn, scn.isos[0], seed=7, length="quick")
    rv = g["rivals"][0]
    iso = next(i for i in scn.isos if i not in E._others(g))
    with pytest.raises(E.GameError):
        E.apply(scn, g, {"do": "secure", "iso3": iso})                          # no longer an action of its own
    g["trust"][iso], g["sway"]["you"][iso] = 2, 1.2
    assert "commit" in E.deal_terms(scn, g, iso)["get"]                         # ask for it at the deal table
    g["secured"].append(iso)
    rv["influence"] = 10
    E._rival_act(scn, g, rv, "lobby", iso, 2, 0.3)
    assert g["sway"][rv["iso3"]][iso] == pytest.approx(0.15)                    # half the push

def test_the_golden_rule(scenarios):
    scn = scenarios["comet_halcyon"]
    g = E.new_game(scn, scn.isos[0], seed=8, difficulty="easy")
    rv = g["rivals"][0]
    both = {"id": "final", "tags": [rv["want"], rv["block"]], "author": "draft"}
    assert E.stance(scn, g, rv["iso3"], both) == 0                              # a rival that got its wish won't sink the text
    assert E.stance(scn, g, rv["iso3"], {**both, "id": "c"}) == -1             # clause by clause it still votes the red line down
    m = g["mandate"]
    g["draft"] = [{"id": "x1", "text": "t", "tags": [m["must"]], "author": "draft", "amended_by": []}]
    E._open_summit(scn, g)                       # straight to the final vote on a text with your main aim, not your red line
    g["summit"].update(step="final", results=[{"clause": "x1", "tags": [m["must"]], "passed": True, "yes": 1, "no": 0,
                                                "abstain": 0, "votes": {}, "summary": ""}])
    if True:
        respect = g["respect"]
        no, _ = E.apply(scn, g, {"do": "final", "vote": "no"})
        assert no["golden"] == "broke" and no["respect"] == max(0, respect - E.R["golden_respect"])
        hl = E.half_loaf(scn, no)
        assert "Half a loaf" in hl["verdict"] and hl["golden"] == "broke"
        yes, _ = E.apply(scn, g, {"do": "final", "vote": "yes"})
        assert yes["golden"] in ("kept", None) and E.half_loaf(scn, yes)["gained"]
        assert len(E.rival_outcomes(scn, yes)) == len(yes["rivals"])


def test_a_rival_speaks_against_your_clause_and_a_reply_answers_it(scenarios):
    scn = scenarios["comet_halcyon"]
    for seed in range(1, 40):
        g = E.new_game(scn, scn.isos[seed % len(scn.isos)], seed=seed)
        while g["phase"] == "chapter":
            g, _ = E.apply(scn, g, {"do": "end_turn"})
        g, _ = E.apply(scn, g, {"do": "speech", "stance": "open"})
        while g["summit"]["step"] == "clause" and not g["summit"].get("attack"):
            g, _ = E.apply(scn, g, {"do": "decide", "choice": "stand", "vote": "yes"})
        if g["summit"].get("attack"):
            break
    else:
        pytest.skip("no attack in 40 games")
    foe = g["summit"]["attack"]["by"]
    g["respect"] = 0
    with pytest.raises(E.GameError):
        E.apply(scn, g, {"do": "decide", "choice": "reply", "vote": "yes"})        # the Chair grants it only with Respect
    unanswered, out = E.apply(scn, g, {"do": "decide", "choice": "stand", "vote": "yes"})
    assert out["attack"] == foe and sum(unanswered["sway"][foe].values()) > sum(g["sway"][foe].values())
    g["respect"] = E.R["reply_respect"]
    answered, out = E.apply(scn, g, {"do": "decide", "choice": "reply", "vote": "yes"})
    assert out.get("reply") and sum(answered["sway"][foe].values()) == pytest.approx(sum(g["sway"][foe].values()))


def test_the_projection_is_the_vote_without_moods(scenarios):
    scn = scenarios["sc_climate_security"]
    g = E.new_game(scn, scn.isos[0], seed=9)
    p = E.projection(scn, g)
    assert p["yes"] + p["no"] + p["abstain"] == len(scn.members)
    g2 = json.loads(json.dumps(g))
    g2["moods"] = {i: 3.0 for i in g2["moods"]}
    assert E.projection(scn, g2)["votes"] == p["votes"]                           # the hidden mood isn't in it
