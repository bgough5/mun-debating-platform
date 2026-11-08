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


def test_answers_depend_on_what_you_know(scn):
    """Ben: "what if the delegate doesn't know? What does tell the truth mean?" You can only tell what you know."""
    g = E.new_game(scn, scn.isos[0], seed=5)
    iso = next(i for i in scn.isos if i not in E._others(g) and i != g["iso3"])
    g["read"], g["whip"] = [], {}
    for adv in g.get("staff", []):
        adv["post"] = None
    unknown = V._make(scn, g, "ask", iso, V._rng(g, "k"))
    assert V.knows(g, unknown["about"]) is None
    assert {o["code"] for o in unknown["options"]} == {"guess", "dunno", "lie"}      # no "truth" when you don't know it
    g["read"] = list(scn.isos)
    known = V._make(scn, g, "ask", iso, V._rng(g, "k"))
    assert V.knows(g, known["about"]) == "its file"
    assert {o["code"] for o in known["options"]} == {"truth", "lie", "decline"}
    assert any("Tell them what you know" in o["label"] for o in known["options"])


def test_some_conversations_go_on_for_more_than_one_exchange(scn):
    g = E.new_game(scn, scn.isos[0], seed=6)
    g["visits"] = [{"id": "vx-media", "kind": "media", "iso3": g["iso3"], "who": "press", "clause": g["draft"][0]["id"], "text": "?",
                    "options": [{"code": "evasive", "label": "No comment", "cost": 0}]}]
    g, out = E.apply(scn, g, {"do": "visit", "id": "vx-media", "choice": "evasive"})
    assert out["continues"] and g["visits"][0]["step"] == 2
    r0 = g["respect"]
    g, out = E.apply(scn, g, {"do": "visit", "id": g["visits"][0]["id"], "choice": "walk"})
    assert not out.get("continues") and g["respect"] == max(0, r0 - 1)
    rv = g["rivals"][0]
    rv["style"] = "broker"
    tag = next(t for t in scn.tags if t != g["mandate"]["must"])
    g["visits"] = [{"id": "vx-press", "kind": "press", "iso3": rv["iso3"], "tag": tag, "text": "?",
                    "options": [{"code": "counter", "label": "Counter", "cost": 0}]}]
    g, out = E.apply(scn, g, {"do": "visit", "id": "vx-press", "choice": "counter"})
    nxt = g["visits"][0]
    assert {o["code"] for o in nxt["options"]} == {"agree_both", "refuse"}
    g, _ = E.apply(scn, g, {"do": "visit", "id": nxt["id"], "choice": "agree_both"})
    rv = next(r for r in g["rivals"] if r["iso3"] == rv["iso3"])
    assert rv["spare"] == g["mandate"]["must"]


def test_options_do_not_give_away_their_consequences(scn):
    for seed in range(1, 15):
        g = E.new_game(scn, scn.isos[seed % len(scn.isos)], seed=seed)
        g, _ = E.apply(scn, g, {"do": "end_turn"})
        g, _ = E.apply(scn, g, {"do": "end_turn"})
        for v in g["visits"]:
            for o in v["options"]:
                assert "(" not in o["label"] or "Influence" in o["label"] or "its file" in o["label"] or "adviser" in o["label"] or "whip sheet" in o["label"], o["label"]
        assert all(len(V.likeness(i).split()) in (4, 5) for i in scn.isos)


def test_talking_is_a_conversation(scn):
    """Ben, 6 Nov: you open with an argument, they react, and where you take it decides how far they move."""
    from app.modules.sim.campaign import talks as T
    g = E.new_game(scn, scn.isos[0], seed=8)
    g["influence"], g["ap"] = 20, 5
    iso = next(i for i in scn.isos if i not in E._others(g) and i != g["iso3"]
               and E.mu_of(scn, g, i, [g["mandate"]["must"]]) > E.R["redline"])
    r = T.receptive(scn, g, iso)
    best = max(r, key=lambda k: (r[k], k)); worst = min(r, key=lambda k: (r[k], k))
    ap = g["ap"]
    g1, out = E.apply(scn, g, {"do": "talk", "step": "open", "iso3": iso, "arg": best})
    assert g1["ap"] == ap - 1 and out["conv"]["reply"] and g1["conv"]["iso3"] == iso
    assert {"press", "ask", "close"} <= {o["code"] for o in out["conv"]["options"]}
    with pytest.raises(E.GameError):
        E.apply(scn, g1, {"do": "talk", "step": "open", "iso3": iso, "arg": worst})    # one conversation at a time
    pressed, o1 = E.apply(scn, g1, {"do": "talk", "step": "follow", "choice": "press"})
    closed, o2 = E.apply(scn, g1, {"do": "talk", "step": "follow", "choice": "close"})
    asked, o3 = E.apply(scn, g1, {"do": "talk", "step": "follow", "choice": "ask"})
    assert o1["moved"] > o2["moved"] > o3["moved"] and "leans" in o3 and not pressed.get("conv")   # pressing a strong point pays
    g2, _ = E.apply(scn, g, {"do": "talk", "step": "open", "iso3": iso, "arg": worst})
    _, weak = E.apply(scn, g2, {"do": "talk", "step": "follow", "choice": "press"})
    assert weak["moved"] < o1["moved"]                                                      # pressing a weak one doesn't
    g3, _ = E.apply(scn, g2, {"do": "end_turn"})
    assert not g3.get("conv") and any("talked with" in x["text"] for x in g3["log"])          # left open, it ends politely


def test_delegates_remember_your_talks(scn):
    from app.modules.sim.campaign import talks as T
    g = E.new_game(scn, scn.isos[0], seed=9)
    g["influence"], g["ap"] = 30, 9
    iso = next(i for i in scn.isos if i not in E._others(g) and i != g["iso3"]
               and E.mu_of(scn, g, i, [g["mandate"]["must"]]) > E.R["redline"])
    r = T.receptive(scn, g, iso)
    best = max(r, key=lambda k: (r[k], k))
    g1, _ = E.apply(scn, g, {"do": "talk", "step": "open", "iso3": iso, "arg": best})
    g1, first = E.apply(scn, g1, {"do": "talk", "step": "follow", "choice": "press"})
    g2, out = E.apply(scn, g1, {"do": "talk", "step": "open", "iso3": iso, "arg": best})
    assert "before" in out["conv"]["reply"]                                                  # they remember
    g2, again = E.apply(scn, g2, {"do": "talk", "step": "follow", "choice": "press"})
    assert again["moved"] < first["moved"] and len(g2["talked"][iso]) == 2                   # the same point counts for less
    other = next(k for k in T.ARGS if k != best)
    g3, out = E.apply(scn, g1, {"do": "talk", "step": "open", "iso3": iso, "arg": other})
    assert "forgotten" in out["conv"]["reply"] or "Last time" in out["conv"]["reply"]


def test_approaches_are_trade_offs(scn):
    """Ben, 8 Nov: an approach chosen before the game; each a trade-off, never simply better."""
    from app.modules.sim.campaign import content as K
    base = E.new_game(scn, scn.isos[0], seed=12)
    iso = next(i for i in scn.isos if i not in E._others(base) and i != base["iso3"])
    ling = E.new_game(scn, scn.isos[0], seed=12, approach="linguist")
    assert E.lobby_cost(scn, ling, iso) == max(0, E.lobby_cost(scn, base, iso) - 1)          # talks cost less
    vet = E.new_game(scn, scn.isos[0], seed=12, approach="veteran")
    assert vet["staff"][0]["stars"] == 2 and K.STAFF_SKILLS[vet["staff"][0]["kind"]][2][0] in vet["skills"]
    assert sum(x["n"] for x in E.ap_sources(scn, vet)) == sum(x["n"] for x in E.ap_sources(scn, base)) - 1   # one fewer action, early on
    vet["turn"] = 4
    assert not any(x["code"] == "approach" for x in E.ap_sources(scn, vet))
    with pytest.raises(E.GameError):
        E.new_game(scn, scn.isos[0], seed=12, approach="superhero")
    assert set(K.APPROACHES) == {"diplomat", "linguist", "veteran", "envoy"}
