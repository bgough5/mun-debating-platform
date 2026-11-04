"""D-101, phase 7: the dynamic hour. Every chapter opens with a crisis, delegations bring offers to your door, rivals
play to a personality, and delegations' positions shift during the session (and the shift reaches the vote)."""
import json

import pytest

from app.db import SYSTEM
from app.modules.sim import play
from app.modules.sim.campaign import content as K
from app.modules.sim.campaign import engine as E
from app.modules.sim.campaign.scenario import load


@pytest.fixture
def scn(app):
    with app.state.db.write(SYSTEM) as w:
        cid = play.guest_committee(w, "comet_halcyon")
    with app.state.db.read() as conn:
        yield load(conn, cid, "comet_halcyon")


def _games(scn, n=30, **kw):
    return [E.new_game(scn, scn.isos[i % len(scn.isos)], seed=s, **kw) for i, s in enumerate(range(1, n + 1))]


def test_every_chapter_opens_with_a_crisis(scn):
    for g in _games(scn, 8):
        assert g["crisis"]["chapter"] == 1 and g["crisis"]["id"] in {c["id"] for c in K.CRISES}
        assert "{" not in g["crisis"]["title"] + g["crisis"]["body"]                  # every blank filled in
        assert any(x["kind"] == "crisis" for x in g["log"])
        while g["phase"] == "chapter" and g["chapter"] == 1:
            g, _ = E.apply(scn, g, {"do": "end_turn"})
        assert g["crisis"]["chapter"] == 2                                            # the next chapter has its own
        assert json.loads(json.dumps(g)) == g


def test_a_deadline_brought_forward_closes_the_chapter_a_turn_early(scn):
    g = next(g for g in _games(scn, 200) if g["crisis"]["id"] == "deadline")
    assert E.turns_now(g) == E.LENGTHS["standard"]["turns"] - 1
    for _ in range(E.turns_now(g)):
        g, _ = E.apply(scn, g, {"do": "end_turn"})
    assert g["chapter"] == 2 and g["turn"] == 1


def test_a_new_government_shifts_a_position_and_the_shift_reaches_the_vote(scn):
    g = next(g for g in _games(scn, 200) if g["crisis"]["id"] == "new_government")
    iso, tag = g["crisis"]["iso"], g["crisis"]["tag"]
    assert g["drift"][iso][tag] != 0
    clause = {"id": "x", "tags": [tag], "author": "draft"}
    moved = E.latent(scn, g, iso, clause, mood=False)
    g2 = json.loads(json.dumps(g)); g2["drift"] = {}
    assert moved - E.latent(scn, g2, iso, clause, mood=False) == pytest.approx(g["drift"][iso][tag])
    f = E.country_file(scn, g, iso)
    assert any(x["label"] == scn.tags[tag] for x in f["shifts"])                        # the file says it changed


def test_offers_come_to_your_door_and_lapse_at_the_end_of_the_turn(scn):
    games = _games(scn, 30)
    assert sum(1 for g in games if g["offers"]) >= 20                                  # most turns bring someone to the door
    g = next(g for g in games if any(o["kind"] == "back" for o in g["offers"]))
    o = next(o for o in g["offers"] if o["kind"] == "back")
    ap, trust = g["ap"], g["trust"][o["iso3"]]
    g2, out = E.apply(scn, g, {"do": "offer", "id": o["id"], "answer": "accept"})
    assert out["accepted"] and g2["ap"] == ap                                          # answering costs no action
    assert {"iso3": o["iso3"], "clause": o["clause"], "kept": None} in g2["promises"]
    assert g2["trust"][o["iso3"]] == min(E.R["trust_max"], trust + 1) and g2["deals"] == 1
    with pytest.raises(E.GameError):
        E.apply(scn, g2, {"do": "offer", "id": o["id"], "answer": "accept"})          # once only
    g3, out = E.apply(scn, g, {"do": "offer", "id": o["id"], "answer": "refuse"})
    assert not out["accepted"] and not any(x["id"] == o["id"] for x in g3["offers"]) and g3["deals"] == 0
    left = [x for x in g["offers"] if x["id"] != o["id"]]
    g4, _ = E.apply(scn, g, {"do": "end_turn"})
    assert not any(x["id"] in {y["id"] for y in left} for x in g4["offers"])         # offers lapse with the turn


def test_a_favour_offer_costs_influence_and_earns_a_favour(scn):
    for g in _games(scn, 200):
        g["trust"] = {i: 1 for i in g["trust"]}
        g["n"] += 1
        E._make_offers(scn, g)
        o = next((x for x in g["offers"] if x["kind"] == "favour"), None)
        if o:
            break
    assert o, "no favour offer in 200 games"
    inf = g["influence"]
    g2, _ = E.apply(scn, g, {"do": "offer", "id": o["id"], "answer": "accept"})
    assert g2["influence"] == inf - 2 and o["iso3"] in g2["favours"]


def test_rivals_have_personalities(scn):
    for g in _games(scn, 10, difficulty="hard"):
        styles = [r["style"] for r in g["rivals"]]
        assert set(styles) <= set(K.RIVAL_STYLES) and len(set(styles)) == len(styles)  # three rivals, three personalities


def test_the_spoiler_goes_after_your_own_clauses_and_saves_a_floor_amendment(scn):
    g = next(g for g in _games(scn, 60) if any(r["style"] == "spoiler" for r in g["rivals"]))
    card = g["cards"][0]
    g, out = E.apply(scn, g, {"do": "propose", "card": card})
    g, _ = E.apply(scn, g, {"do": "end_turn"})
    spoiler = next(r for r in g["rivals"] if r["style"] == "spoiler")
    name = scn.member(spoiler["iso3"]).name
    assert any(x["who"] == spoiler["iso3"] and "your clause" in x["text"] for x in g["log"]) or \
        any(name in x["text"] and "your clause" in x["text"] for x in g["log"] if x["kind"] == "intel")
    plain = json.loads(json.dumps(g))
    for r in plain["rivals"]:
        r["style"] = "hawk"
    E._open_summit(scn, g)
    E._open_summit(scn, plain)
    assert g["summit"]["amendments_left"] == plain["summit"]["amendments_left"] + 1
