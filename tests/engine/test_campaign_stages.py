"""D-101, phase 11 (Ben's phone-session proposal, docs/design/session-progression.md): stages that end at a
breakthrough or a deadline, a delegation whose actions grow, bloc meetings, overtime, and more intel per move."""
import json

import pytest

from app.db import SYSTEM
from app.modules.sim import play
from app.modules.sim.campaign import engine as E
from app.modules.sim.campaign.scenario import load


@pytest.fixture
def scn(app):
    with app.state.db.write(SYSTEM) as w:
        cid = play.guest_committee(w, "comet_halcyon")
    with app.state.db.read() as conn:
        yield load(conn, cid, "comet_halcyon")


def _game(scn, **kw):
    g = E.new_game(scn, scn.isos[2], seed=kw.pop("seed", 11), **kw)
    if g["crisis"]["id"] == "deadline":                     # keep the deadline arithmetic plain
        g["crisis"]["chapter"] = 0
    return g


def test_deadlines_shorten_stage_by_stage(scn):
    g = _game(scn)
    assert [E.LENGTHS["standard"]["deadlines"][i] for i in range(3)] == [6, 5, 4]
    assert E.turns_now(g) == 6
    q = _game(scn, length="quick")
    assert E.LENGTHS["quick"]["chapters"] == 1 and len(E.checklist(scn, q)) == 7   # Quick: all three breakthroughs as one list


def test_pressing_only_end_turn_makes_no_breakthrough(scn):
    """Ben's finding on the phone: a player who only ends turns reached the summit with a passing draft. Now every
    breakthrough needs your own work (a clause of yours, an endorsement, sponsors), and each missed deadline costs Respect."""
    for seed in (1, 2, 3):
        g = _game(scn, seed=seed)
        while g["phase"] == "chapter":
            g, _ = E.apply(scn, g, {"do": "end_turn"})
        assert not any(g["objectives"].values()) and not g.get("breakthroughs")
        assert any(x["kind"] == "objective" and "deadline passed" in x["text"] for x in g["log"])


def test_a_breakthrough_lets_you_move_on_with_momentum(scn):
    g = _game(scn)
    g["ap"], g["influence"], g["turn"] = 9, 20, 2                    # no breakthrough on a stage's first turn (phase 13)
    m = g["mandate"]
    have = {t for c in g["draft"] for t in c["tags"]}
    for card in [c for c in scn.cards if c["id"] in g["cards"] and m["red"] not in c["tags"]]:
        if len(g["draft"]) >= 5 and sum(c["author"] == "you" for c in g["draft"]) >= 2 and m["must"] in have:
            break
        if all(t in have for t in card["tags"]):
            continue
        g["ap"] = 9
        g, _ = E.apply(scn, g, {"do": "propose", "card": card["id"]})
        have = {t for c in g["draft"] for t in c["tags"]}
    if not E._objective(scn, g):
        pytest.skip("this draft doesn't make the breakthrough")
    assert "1" in g["breakthroughs"]
    with pytest.raises(E.GameError):
        E.apply(scn, _game(scn), {"do": "advance"})                       # no breakthrough, no moving on
    respect, influence, left = g["respect"], g["influence"], E.turns_now(g) - g["turn"]
    stayed, _ = E.apply(scn, g, {"do": "stay"})
    assert stayed["chapter"] == 1 and stayed["stayed"]["1"]
    moved, out = E.apply(scn, g, {"do": "advance"})
    assert out["advanced"] and moved["chapter"] == 2 and moved["objectives"]["1"] is True
    assert moved["momentum"] == left and moved["respect"] >= min(E.R["respect_max"], respect + E.R["momentum_respect"])
    assert moved["influence"] >= influence + E.R["momentum_influence"] * left
    assert json.loads(json.dumps(moved)) == moved


def test_missing_a_deadline_costs_respect(scn):
    g = _game(scn)
    g["respect"] = 5
    E._end_stage(scn, g)
    assert g["objectives"]["1"] is False and g["chapter"] == 2
    assert g["respect"] <= 5 - E.R["late_respect"] + 1                   # (a capital telegram may follow)


def test_the_delegation_grows(scn):
    g = _game(scn)
    src = {x["code"]: x for x in E.ap_sources(scn, g)}
    assert src["base"]["n"] == 2 and src["staff"]["n"] == 1 and src["stage"]["n"] == 0   # about three actions at first
    g["chapter"], g["expertise"], g["respect"] = 3, 10, 8
    g["endorse"] = {"AFR": "you", "WEOG": "you"}
    total = sum(x["n"] for x in E.ap_sources(scn, g))
    assert total == 2 + 2 + 1 + 2 + 2 + 1                                 # stage, staff, experience, Respect, coalition
    assert all(x["next"] is None or isinstance(x["next"], str) for x in E.ap_sources(scn, g))


def test_overtime_is_retired(scn):
    """Phase 14 (Ben): actions come only from your delegation, so there is no buying extra ones with Influence."""
    g = _game(scn)
    g["influence"] = 20
    with pytest.raises(E.GameError):
        E.apply(scn, g, {"do": "overtime"})


def test_bloc_meetings_and_more_intel(scn):
    g = _game(scn)
    E._end_stage(scn, g)                                                   # on to Bloc meetings
    assert g["chapter"] == 2 and g["meeting"]
    g["ap"], g["influence"] = 5, 10
    members = [i for i in E._region_members(scn, g["meeting"]) if i not in E._others(g)]
    before = {i: g["sway"]["you"][i] for i in members}
    g, _ = E.apply(scn, g, {"do": "attend"})
    assert all(g["sway"]["you"][i] > before[i] for i in members)
    with pytest.raises(E.GameError):
        E.apply(scn, g, {"do": "attend"})                                # once a turn
    iso = next(i for i in scn.isos if i not in E._others(g) and i != g["iso3"])
    _, out = E.apply(scn, g, {"do": "lobby", "iso3": iso})
    assert set(out["leans"]) == {scn.member(r["iso3"]).name for r in g["rivals"]} and "would_vote" not in out
    E._end_stage(scn, g)
    g["ap"], g["influence"] = 5, 10
    _, out = E.apply(scn, g, {"do": "lobby", "iso3": iso})
    assert out["would_vote"] in ("yes", "no", "abstain")
