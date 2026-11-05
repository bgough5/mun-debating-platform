"""D-101, phase 12: pitches (two arguments, matched to the delegation), haggling at the deal table (a price that comes
down if you hold out, a walk-away point, patience), compromise with rivals (peace, a merged text, co-sponsorship),
one commitments ledger, and systems that unlock by stage."""
import pytest

from app.db import SYSTEM
from app.modules.sim import play
from app.modules.sim.campaign import engine as E
from app.modules.sim.campaign import talks as T
from app.modules.sim.campaign.scenario import load


@pytest.fixture
def scn(app):
    with app.state.db.write(SYSTEM) as w:
        cid = play.guest_committee(w, "comet_halcyon")
    with app.state.db.read() as conn:
        yield load(conn, cid, "comet_halcyon")


def _game(scn, seed=21, **kw):
    g = E.new_game(scn, scn.isos[1], seed=seed, **kw)
    g["ap"], g["influence"] = 9, 40
    return g


def _free(scn, g):
    return [i for i in scn.isos if i not in E._others(g) and i != g["iso3"] and E.mu_of(scn, g, i, [g["mandate"]["must"]]) > E.R["redline"]]


def test_a_matched_pitch_moves_a_delegation_further(scn):
    g = _game(scn)
    iso = _free(scn, g)[0]
    r = T.receptive(scn, g, iso)
    assert sorted(r.values()) == [T.WEAK, T.WEAK, T.SOME, T.STRONG, T.STRONG]       # two land fully, one half, two barely
    best = sorted(r, key=lambda k: -r[k])[:2]
    worst = sorted(r, key=lambda k: r[k])[:2]
    good, out = E.apply(scn, g, {"do": "lobby", "iso3": iso, "args": best})
    bad, _ = E.apply(scn, g, {"do": "lobby", "iso3": iso, "args": worst})
    assert good["sway"]["you"][iso] > bad["sway"]["you"][iso] * 2
    assert set(out["landed"].values()) == {"strong"}
    with pytest.raises(E.GameError):
        E.apply(scn, g, {"do": "lobby", "iso3": iso, "args": ["values"]})              # a pitch is two arguments
    f = E.country_file(scn, g, iso)
    assert f["listens_to"] == T.listens_to(scn, g, iso) and len(f["listens_to"]) == 2  # the file tells you what lands


def test_systems_unlock_by_stage(scn):
    g = _game(scn)
    iso = _free(scn, g)[0]
    for action in ({"do": "deal", "stage": "open", "iso3": iso, "get": ["influence"]}, {"do": "post", "adviser": "a1", "iso3": iso},
                   {"do": "reserve"}, {"do": "secure", "iso3": iso}, {"do": "compromise", "iso3": g["rivals"][0]["iso3"]}):
        with pytest.raises(E.GameError, match="opens in"):
            E.apply(scn, g, action)
    q = _game(scn, length="quick")
    assert all(T.locked(q, k) is None for k in T.UNLOCK)                              # a Quick session has everything at once
    g["chapter"] = 2
    assert T.locked(g, "deal") is None and T.locked(g, "reserve")
    g["chapter"] = 3
    assert T.locked(g, "reserve") is None


def _talks(scn, g):
    g["chapter"] = 2
    for iso in _free(scn, g):
        t = E.deal_terms(scn, g, iso)
        if "influence" in t["get"] and len(t["give"]) >= 2:
            g2, _ = E.apply(scn, g, {"do": "deal", "stage": "open", "iso3": iso, "get": ["influence"]})
            return g2, iso
    pytest.skip("no delegation to talk to")


def test_haggling_holding_out_brings_the_price_down(scn):
    for seed in range(1, 30):
        g, iso = _talks(scn, _game(scn, seed=seed))
        t = g["talks"]
        assert t["price"] >= t["walk"] and t["asks"] and g["ap"] == 9 - E.R["deal_ap"]
        offer = [k for k in t["asks"][:-1]] or [min(t["give_vals"], key=lambda k: t["give_vals"][k])]   # hold out: less than they ask
        if sum(t["give_vals"][k] for k in offer) >= t["price"]:
            continue
        g2, out = E.apply(scn, g, {"do": "deal", "stage": "offer", "give": offer})
        if out.get("counter") is not None:
            assert out["counter"] < out["was"] and g2["talks"]["price"] >= t["walk"] and g2["ap"] == g["ap"]   # rounds cost no actions
            return
    pytest.skip("no counter in 30 games")


def test_paying_the_price_closes_the_deal_and_walking_ends_the_talks(scn):
    g, iso = _talks(scn, _game(scn, seed=4))
    inf = g["influence"]
    done, out = E.apply(scn, g, {"do": "deal", "stage": "offer", "give": g["talks"]["asks"]})
    assert out["deal"] and done["talks"] is None and iso in done["dealt"]
    assert done["influence"] >= inf + E.R["deal_influence"] - (E.R["deal_funding"] if "funding" in g["talks"]["asks"] else 0)
    left, out = E.apply(scn, g, {"do": "deal", "stage": "walk"})
    assert out["walked"] == "you" and left["talks"] is None and iso in left["dealt"]
    with pytest.raises(E.GameError):
        E.apply(scn, left, {"do": "deal", "stage": "offer", "give": ["trade"]})
    g2, _ = E.apply(scn, g, {"do": "end_turn"})
    assert g2.get("talks") is None                                                  # talks lapse with the turn


def test_a_rival_makes_peace_for_a_concession(scn):
    peace = None
    for seed in range(1, 80):
        g = _game(scn, seed=seed)
        g["chapter"] = 2
        rv = next((r for r in g["rivals"] if T.compromise_terms(scn, g, r) and r.get("style") != "hawk"), None)
        if not rv:
            continue
        g, _ = E.apply(scn, g, {"do": "compromise", "iso3": rv["iso3"]})
        asks = g["talks"]["asks"]
        for _ in range(4):                                                          # pay its price, round by round
            if not g.get("talks"):
                break
            g, out = E.apply(scn, g, {"do": "compromise", "stage": "offer", "give": g["talks"]["asks"]})
            if out.get("peace"):
                peace = g
                break
        if peace:
            break
    assert peace, "no rival made peace in 80 games"
    r2 = next(r for r in peace["rivals"] if r["iso3"] == rv["iso3"])
    assert r2["truce"] and rv["iso3"] in peace["sponsors"] and not any(peace["sway"][rv["iso3"]].values())
    final = E.final_clause(peace)
    if rv["block"] not in final["tags"]:
        assert E.stance(scn, peace, rv["iso3"], final) == 1                         # it backs the merged text
    assert any(x["kind"] == "truce" for x in T.ledger(scn, peace))
    before = len([x for x in peace["log"] if x["who"] == rv["iso3"] and x["kind"] == "rival"])
    peace["ap"] = 0
    after, _ = E.apply(scn, peace, {"do": "end_turn"})
    assert len([x for x in after["log"] if x["who"] == rv["iso3"] and x["kind"] == "rival"]) == before   # it stops working against you
    assert asks


def test_one_ledger_holds_every_commitment(scn):
    g = _game(scn)
    a, b = _free(scn, g)[:2]
    g["promises"].append({"iso3": a, "clause": g["draft"][0]["id"], "kept": None})
    g["favours"].append(b)
    g["deal_votes"] = {b: "yes"}
    kinds = {x["kind"] for x in T.ledger(scn, g)}
    assert kinds == {"promise", "favour", "deal"}
    assert [x["kind"] for x in T.ledger(scn, g, a)] == ["promise"]
