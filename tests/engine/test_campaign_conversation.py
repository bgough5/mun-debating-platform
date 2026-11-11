"""Ben's playtest, 11 Nov: talks were predictable and repetitive. A conversation now opens with the delegation's own
concern (free), offers arguments and tones that each have a price, can run to a third exchange, never repeats a line
while fresh ones remain, and tells you only what the delegation is willing to share with you."""
import pytest

from app.db import SYSTEM
from app.modules.sim import play
from app.modules.sim.campaign import conversation as C
from app.modules.sim.campaign import engine as E
from app.modules.sim.campaign import voices as VO
from app.modules.sim.campaign.scenario import load


@pytest.fixture
def scn(app):
    with app.state.db.write(SYSTEM) as w:
        cid = play.guest_committee(w, "comet_halcyon")
    with app.state.db.read() as conn:
        yield load(conn, cid, "comet_halcyon")


def _free(scn, g):
    return [i for i in scn.isos if i not in E._others(g) and i != g["iso3"]]


def test_greeting_is_free_and_they_lead_with_their_concern(scn):
    g = E.new_game(scn, scn.isos[0], seed=5)
    iso, ap, infl = _free(scn, g)[0], g["ap"], g["influence"]
    g1, out = E.apply(scn, g, {"do": "talk", "step": "greet", "iso3": iso})
    assert g1["ap"] == ap and g1["influence"] == infl and out["conv"]["stage"] == "open" and out["conv"]["reply"]
    assert iso not in g1.get("engaged", [])                                       # a greeting alone engages nobody
    codes = {o["code"] for o in out["conv"]["options"]}
    assert {"tone:empathise", "tone:bargain", "tone:warn"} <= codes and any(c.startswith("arg:") for c in codes)
    g2, out = E.apply(scn, g1, {"do": "talk", "step": "follow", "choice": "close"})   # walking away costs nothing
    assert g2["ap"] == ap and not g2.get("conv")


def test_concerns_vary_with_the_game(scn):
    kinds = set()
    for seed in range(1, 15):
        g = E.new_game(scn, scn.isos[seed % len(scn.isos)], seed=seed)
        for iso in _free(scn, g)[:8]:
            kinds.add(C.concern(scn, g, iso)["kind"])
    assert len(kinds) >= 3, kinds
    g = E.new_game(scn, scn.isos[0], seed=3)
    iso = _free(scn, g)[0]
    E._betray(scn, g, iso, "test")
    assert C.concern(scn, g, iso)["kind"] == "betrayed"


def test_tones_have_a_price(scn):
    g = E.new_game(scn, scn.isos[0], seed=7)
    g["influence"], g["ap"] = 20, 6
    iso = _free(scn, g)[1]
    g1, _ = E.apply(scn, g, {"do": "talk", "step": "greet", "iso3": iso})
    infl = g1["influence"] - E.lobby_cost(scn, g1, iso)
    g2, _ = E.apply(scn, g1, {"do": "talk", "step": "follow", "choice": "tone:bargain"})
    assert g2["influence"] == infl - C.BARGAIN_COST                              # an offer costs Influence
    t0 = g1["trust"].get(iso, 0)
    g3, _ = E.apply(scn, g1, {"do": "talk", "step": "follow", "choice": "tone:warn"})
    g3, _ = E.apply(scn, g3, {"do": "talk", "step": "follow", "choice": "close"})
    assert g3["trust"].get(iso, 0) < t0                                          # a warning always costs trust


def test_hostile_and_rival_delegations_keep_their_counsel(scn):
    g = E.new_game(scn, scn.isos[0], seed=4)
    rival = g["rivals"][0]["iso3"]
    friend = _free(scn, g)[0]
    g["trust"][friend], g["trust"][rival] = 3, -3
    assert C.reveal(scn, g, rival) < 0 <= C.reveal(scn, g, friend)
    cold = _free(scn, g)[1]                                                       # rivals can't be lobbied; a hostile delegation
    g["trust"][cold] = -3
    g["sway"]["you"][cold] = -1.0
    assert C.reveal(scn, g, cold) < 0
    g["ap"], g["influence"] = 6, 20
    g1, _ = E.apply(scn, g, {"do": "talk", "step": "greet", "iso3": cold})
    g1, _ = E.apply(scn, g1, {"do": "talk", "step": "follow", "choice": "tone:empathise"})
    _, out = E.apply(scn, g1, {"do": "talk", "step": "follow", "choice": "ask"})
    assert "withheld" in out and "would_vote" not in out and "leans" not in out


def test_no_line_repeats_while_fresh_ones_remain(scn):
    import random
    g = E.new_game(scn, scn.isos[0], seed=2)
    bank = ["a", "b", "c", "d"]
    rng = random.Random(1)
    got = [VO.pick(g, "test", bank, rng) for _ in range(4)]
    assert sorted(got) == bank                                                    # all four before any repeats


def test_the_whip_sheet_locks_when_the_summit_opens(scn):
    """Ben, 11 Nov: predictions are fixed when the Summit opens, so its debate and caucus can catch you out."""
    g = E.new_game(scn, scn.isos[0], seed=6)
    iso = _free(scn, g)[0]
    g, _ = E.apply(scn, g, {"do": "mark", "iso3": iso, "clause": "final", "vote": "yes"})
    assert g["whip"][iso] == "yes"
    g["phase"] = "summit"
    with pytest.raises(E.GameError, match="locked"):
        E.apply(scn, g, {"do": "mark", "iso3": iso, "clause": "final", "vote": "no"})


def test_a_wrong_answer_at_one_standing_never_strands_the_game(scn):
    """Ben, 11 Nov: a procedure question answered wrongly with 1 Standing left broke the game."""
    from app.modules.sim.campaign import content as K
    q = K.QUESTIONS[0]
    wrong = (q["answer"] + 1) % len(q["options"])
    for diff in ("standard", "hard"):
        g = E.new_game(scn, scn.isos[0], difficulty=diff, seed=3)
        g["respect"], g["question"] = 1, q["id"]
        g, _ = E.apply(scn, g, {"do": "answer", "option": wrong})
        if diff == "hard":
            assert g["phase"] == "done" and g["result"]["recalled"]
        else:
            assert g["recall"] == 1 and g["respect"] >= 1                         # recalled for a turn, never stuck at 0
    g = E.new_game(scn, scn.isos[0], seed=3)
    g["respect"], g["recall"], g["question"] = 1, 1, q["id"]                       # already recalled this turn
    g, _ = E.apply(scn, g, {"do": "answer", "option": wrong})
    assert g["respect"] == 1 and g["phase"] == "chapter"
