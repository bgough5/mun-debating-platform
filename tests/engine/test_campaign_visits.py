"""D-101, phase 13: delegates come to talk to you (rivals pressing, allies, questions with truth or lies, intelligence,
the caucus, your capital, the press, follow-ups, persuasion), your reputation, the whip sheet, clause histories."""
import pytest

from app.db import SYSTEM
from app.modules.sim import play
from app.modules.sim.campaign import engine as E
from app.modules.sim.campaign import visits as V
from app.modules.sim.campaign.scenario import load


@pytest.fixture
def scn(app):
    with app.state.db.write(SYSTEM) as w:
        cid = play.guest_committee(w, "comet_halcyon")
    with app.state.db.read() as conn:
        yield load(conn, cid, "comet_halcyon")


def test_delegates_come_to_talk_and_cost_no_actions(scn):
    kinds = set()
    for seed in range(1, 30):
        g = E.new_game(scn, scn.isos[seed % len(scn.isos)], seed=seed)
        g, _ = E.apply(scn, g, {"do": "end_turn"})
        assert 1 <= len(g["visits"]) <= 8
        for v in list(g["visits"]):
            kinds.add(v["kind"])
            ap = g["ap"]
            g["influence"] = 20
            g, _ = E.apply(scn, g, {"do": "visit", "id": v["id"], "choice": v["options"][0]["code"]})
            assert g["ap"] == ap                                              # talking costs no actions
    assert len(kinds) >= 4 and "capital" in kinds, kinds                     # a variety of conversations


def test_a_lie_can_be_found_out(scn):
    g = E.new_game(scn, scn.isos[0], seed=3)
    iso = next(i for i in scn.isos if i not in E._others(g) and i != g["iso3"])
    g["visits"] = [V._make(scn, g, "ask", iso, V._rng(g, "t"))]
    g, _ = E.apply(scn, g, {"do": "visit", "id": g["visits"][0]["id"], "choice": "lie"})
    assert g["rep"]["bluff"] == 1
    if g.get("lies"):
        r0 = g["respect"]
        for _ in range(12):                                                    # a 35% chance each turn
            g, _ = E.apply(scn, g, {"do": "end_turn"})
            if not g.get("lies") or g["phase"] != "chapter":
                break
        if not g.get("lies") and g["phase"] == "chapter":
            assert any("misled" in x["text"] for x in g["log"]) and g["respect"] <= r0


def test_the_whip_sheet_is_free_and_clause_histories_record_changes(scn):
    g = E.new_game(scn, scn.isos[0], seed=4)
    ap = g["ap"]
    iso = next(i for i in scn.isos if i != g["iso3"])
    g, _ = E.apply(scn, g, {"do": "mark", "iso3": iso, "clause": g["draft"][0]["id"], "vote": "yes"})
    g, _ = E.apply(scn, g, {"do": "mark", "iso3": iso, "clause": "final", "vote": "no"})
    assert g["ap"] == ap and g["sheet"][g["draft"][0]["id"]][iso] == "yes" and g["whip"][iso] == "no"
    c = g["draft"][0]
    add = next(t for t in scn.tags if all(t not in x["tags"] for x in g["draft"]))
    g["influence"] = 10
    g2, out = E.apply(scn, g, {"do": "amend", "clause": c["id"], "add": add})
    if out.get("accepted"):
        c2 = next(x for x in g2["draft"] if x["id"] == c["id"])
        assert c2["history"][-1]["who"] == "you" and c2["text_stale"]
    taken = next(t for t in c["tags"])
    other = next(x for x in g["draft"] if x["id"] != c["id"] and taken not in x["tags"])
    with pytest.raises(E.GameError):
        E.apply(scn, g, {"do": "amend", "clause": other["id"], "add": taken})   # a commitment can't go in twice
