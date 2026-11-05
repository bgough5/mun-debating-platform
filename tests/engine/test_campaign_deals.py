"""D-101, phase 9: country dossiers from real World Bank figures, the deal table, and your capital's confidence
(telegrams, and a recall that costs a turn, or ends the session on Hard)."""
import pytest

from app.db import SYSTEM
from app.modules.sim import play
from app.modules.sim.campaign import econ as X
from app.modules.sim.campaign import engine as E
from app.modules.sim.campaign.scenario import load


@pytest.fixture
def scn(app):
    with app.state.db.write(SYSTEM) as w:
        cid = play.guest_committee(w, "comet_halcyon")
    with app.state.db.read() as conn:
        yield load(conn, cid, "comet_halcyon")


def test_every_figure_has_a_year_and_a_source(scn):
    assert X.data()["licence"].startswith("Creative Commons Attribution 4.0")
    for iso in scn.isos:
        p = X.profile(iso)
        assert p["known"], iso                                           # every member of the committee has a dossier
        assert p["source"] and "World Bank" in p["source"]
        for r in p["rows"]:
            assert r["value"] and (r["year"] is None or 1990 <= r["year"] <= 2030)
    assert not X.profile("XXX")["known"] and X.traits("XXX")["known"] is False   # an unknown country says so
    assert X.budget("USA") > X.budget("FJI")                              # a bigger, richer economy can pledge more


def _ready(scn, seed=4, difficulty="standard"):
    g = E.new_game(scn, scn.isos[seed % len(scn.isos)], seed=seed, difficulty=difficulty)
    g["influence"], g["ap"], g["chapter"] = 30, 3, 2             # the deal table opens in Bloc meetings (phase 12)
    free = [i for i in scn.isos if i not in E._others(g)]
    return g, free


def test_a_deal_buys_a_binding_vote(scn):
    g, free = _ready(scn)
    iso = next(i for i in free if "yes" in E.deal_terms(scn, g, i)["get"])
    t = E.deal_terms(scn, g, iso)
    give = sorted(t["give"], key=lambda k: -t["give"][k])
    g2, out = E.apply(scn, g, {"do": "deal", "stage": "open", "iso3": iso, "get": ["yes"]})
    for _ in range(4):                                                   # pay their price (phase 12: haggling in rounds)
        if not g2.get("talks"):
            break
        g2, out = E.apply(scn, g2, {"do": "deal", "stage": "offer", "give": g2["talks"]["asks"]})
    if not out.get("deal"):
        pytest.skip("they walked away")
    assert g2["ap"] == g["ap"] - E.R["deal_ap"] and g2["deal_votes"][iso] == "yes"
    assert E.projection(scn, g2)["votes"][iso] == "yes"                  # the bar counts it
    final = E.final_clause(g2)
    if not E.red_line(scn, iso, final["tags"]):
        assert E.votes_on(scn, g2, final)[iso] == "yes"                   # and it holds at the vote
    with pytest.raises(E.GameError):
        E.apply(scn, g2, {"do": "deal", "iso3": iso, "give": give, "get": ["influence"]})     # once a chapter
    other = next(i for i in free if i != iso)
    with pytest.raises(E.GameError):
        E.apply(scn, g2, {"do": "deal", "iso3": other, "give": give, "get": ["influence"]})   # one deal a turn
    with pytest.raises(E.GameError):
        E.apply(scn, g, {"do": "deal", "iso3": g["rivals"][0]["iso3"], "give": give, "get": ["yes"]})   # rivals don't deal


def test_a_poor_offer_is_countered_and_a_pledge_is_not_paid(scn):
    g, free = _ready(scn)
    iso = next(i for i in free if "funding" in E.deal_terms(scn, g, i)["give"] and "sponsor" in E.deal_terms(scn, g, i)["get"])
    g2, _ = E.apply(scn, g, {"do": "deal", "stage": "open", "iso3": iso, "get": ["sponsor"]})
    t = g2["talks"]
    low = min(t["give_vals"], key=lambda k: t["give_vals"][k])
    if t["give_vals"][low] >= t["price"]:
        pytest.skip("even the smallest item covers their price")
    g3, out = E.apply(scn, g2, {"do": "deal", "stage": "offer", "give": [low]})
    assert not out.get("deal") and (out.get("counter") is not None or out.get("walked") == "them")
    assert g3["influence"] == g["influence"] and g3["pledged"] == 0 and g3["ap"] == g["ap"] - E.R["deal_ap"]   # nothing paid for a refusal


def test_the_capital_objects_to_a_promise_on_your_red_line(scn):
    for seed in range(1, 60):
        g, free = _ready(scn, seed)
        red = g["mandate"]["red"]
        c = next((c for c in g["draft"] if red in c["tags"]), None)
        iso = c and next((i for i in free if scn.dist(c["tags"]).get(i, (0, 1))[0] >= 0.4), None)
        if iso:
            break
    else:
        pytest.skip("no draft clause with the red line")
    before = g["capital"]
    g2, _ = E.apply(scn, g, {"do": "promise", "iso3": iso, "clause": c["id"]})
    assert g2["capital"] == before - 2
    tele = [x for x in g2["log"] if x["kind"] == "telegram"]
    assert tele and tele[-1]["mood"] in ("furious", "grumble") and "red line" in tele[-1]["text"]


def test_a_recall_costs_a_turn_or_ends_the_session_on_hard(scn):
    g, _ = _ready(scn, difficulty="standard")
    g["capital"] = 1
    E._capital(scn, g, -2, "Enough.")
    assert g["capital"] == 3 and g["recall"] == 1 and g["phase"] == "chapter"
    g, _ = E.apply(scn, g, {"do": "end_turn"})
    if g["phase"] == "chapter":
        assert g["ap"] == 0                                              # a turn in the capital
    h, _ = _ready(scn, difficulty="hard")
    h["capital"] = 1
    E._capital(scn, h, -2, "Enough.")
    assert h["phase"] == "done" and h["result"]["recalled"] and h["result"]["grade"] == 0
    assert "recalled" in E.half_loaf(scn, h)["verdict"]
    with pytest.raises(E.GameError):
        E.apply(scn, h, {"do": "end_turn"})


def test_the_capital_judges_each_chapter(scn):
    g, _ = _ready(scn)
    c0 = g["capital"]
    E._capital_chapter(scn, g, True)
    assert g["capital"] >= c0 - 1
    g2, _ = _ready(scn)
    g2["draft"] = [{"id": "x", "text": "t", "tags": [g2["mandate"]["red"]], "author": "draft", "amended_by": []}]
    E._capital_chapter(scn, g2, False)
    assert g2["capital"] == c0 - 2                                       # goal missed, and the red line is in the draft
