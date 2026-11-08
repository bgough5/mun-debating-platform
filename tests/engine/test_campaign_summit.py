"""D-102: the Summit as the UN runs it (Ben, 8 Nov 2026): statements, the draft read, a caucus, amendments one by
one as edits (debated, then voted), the final text, the final vote. A settled matter stays closed."""
import pytest

from app.db import SYSTEM
from app.modules.sim import play
from app.modules.sim.campaign import engine as E
from app.modules.sim.campaign import summit as SM
from app.modules.sim.campaign.scenario import load


@pytest.fixture
def scn(app):
    with app.state.db.write(SYSTEM) as w:
        cid = play.guest_committee(w, "ga_migration")
    with app.state.db.read() as conn:
        yield load(conn, cid, "ga_migration")


def _summit(scn, seed=3):
    g = E.new_game(scn, scn.isos[seed % len(scn.isos)], "quick", seed=seed)
    E._open_summit(scn, g)
    return g


def test_the_order_of_business(scn):
    g = _summit(scn)
    s = g["summit"]
    assert s["step"] == "statements" and len(s["statements"]) >= len(g["rivals"])     # everyone states a position
    with pytest.raises(E.GameError):
        E.apply(scn, g, {"do": "final", "vote": "yes"})                                # no skipping to the vote
    g, _ = E.apply(scn, g, {"do": "speech", "stance": "bridge"})
    assert g["summit"]["step"] == "reading"
    g, _ = E.apply(scn, g, {"do": "proceed"})
    assert g["summit"]["step"] == "caucus"
    free = [i for i in scn.isos if i not in E._others(g) and i != g["iso3"]][:2]
    before = {i: g["sway"]["you"][i] for i in free}
    g, out = E.apply(scn, g, {"do": "caucus", "kind": "unmoderated", "iso3": free})
    assert all(g["sway"]["you"][i] > before[i] for i in free) and g["summit"]["step"] in ("amendments", "final_reading")


def test_one_amendment_per_delegation_and_settled_matters_stay_closed(scn):
    for seed in range(1, 8):
        g = _summit(scn, seed)
        g, _ = E.apply(scn, g, {"do": "speech", "stance": "open"})
        g, _ = E.apply(scn, g, {"do": "proceed"})
        g, _ = E.apply(scn, g, {"do": "caucus", "kind": "moderated", "tag": SM.caucus_topics(scn, g)[0]})
        while g["summit"]["step"] == "amendments":
            g, _ = E.apply(scn, g, {"do": "debate", "choice": "silent"})
            g, _ = E.apply(scn, g, {"do": "amend_vote", "vote": "abstain"})
        done = g["summit"]["done"]
        movers = [d["by"] for d in done if d["by"] != "you"]
        assert len(movers) == len(set(movers)) and len(done) <= SM.MAX_AMENDMENTS + len(g.get("threats", []))
        keys = [SM._key(d) for d in done]
        assert len(keys) == len(set(keys))                                                # nobody raises a matter twice
        assert all(k in g["summit"]["closed"] for k in keys)
        later = {"by": g["rivals"][0]["iso3"], **done[0]} if done else None
        if later:
            assert not SM._valid(g, later)                                               # and it can't come back


def test_the_final_vote_is_on_the_text_as_amended(scn):
    g = _summit(scn, 5)
    g["draft"][0]["force"] = -1
    assert SM.read_as(g["draft"][0]) != g["draft"][0]["text"]                            # a softer verb
    from tests.engine.test_campaign import _to_final
    g = _to_final(scn, g, vote="abstain")
    assert g["summit"]["step"] == "final" and len(g["summit"]["results"]) == len(g["draft"])
    g, out = E.apply(scn, g, {"do": "final", "vote": "yes"})
    assert set(out["final"]["tags"]) == {t for c in g["draft"] for t in c["tags"]}


def test_a_point_of_order_needs_real_grounds(scn):
    g = _summit(scn, 4)
    g["skills"] = ["point_of_order"]
    c = g["draft"][0]
    gone = next(t for t in scn.tags if all(t not in x["tags"] for x in g["draft"]))
    g["struck"] = [{"id": "z", "tags": [gone], "text": "x", "by": "you"}]
    s = g["summit"]
    s.update({"step": "amendments", "stage": "debate", "queue": [],
              "cur": {"id": "am1", "by": g["rivals"][0]["iso3"], "kind": "add", "clause": c["id"], "tag": gone}})
    if len(c["tags"]) >= 3:
        c["tags"] = c["tags"][:2]
    r0 = g["respect"]
    g2, out = E.apply(scn, g, {"do": "debate", "choice": "point_of_order"})
    assert out["ruled"] == "out of order" and g2["respect"] == min(E.R["respect_max"], r0 + 1)   # the working group struck it
    s["cur"] = {"id": "am2", "by": g["rivals"][0]["iso3"], "kind": "soften", "clause": c["id"]}
    g3, out = E.apply(scn, g, {"do": "debate", "choice": "point_of_order"})
    assert out["ruled"] == "in order" and g3["respect"] == r0 - 1 and g3["summit"]["stage"] == "vote"


def test_a_friendly_amendment_and_a_refused_ultimatum(scn):
    g = _summit(scn, 6)
    c = g["draft"][0]
    c["author"] = "you"
    s = g["summit"]
    s.update({"step": "amendments", "stage": "debate", "queue": [],
              "cur": {"id": "am1", "by": g["rivals"][0]["iso3"], "kind": "strengthen" if SM.rung(c) < 4 else "soften", "clause": c["id"]}})
    g["mandate"]["must"] = c["tags"][0]
    g2, out = E.apply(scn, g, {"do": "debate", "choice": "accept"})
    assert out["accepted"] and next(x for x in g2["draft"] if x["id"] == c["id"])["force"] in (1, -1)
    assert SM.read_as(next(x for x in g2["draft"] if x["id"] == c["id"])) != c["text"]
    h = _summit(scn, 7)
    rv = h["rivals"][0]
    block_clause = next((x for x in h["draft"] if rv["block"] in x["tags"]), None)
    if block_clause:
        h["threats"] = [{"iso3": rv["iso3"], "tag": rv["block"]}]
        q = SM._table_amendments(scn, h)
        assert q and q[0]["by"] == rv["iso3"] and q[0]["threat"]                          # it comes back, first in line
