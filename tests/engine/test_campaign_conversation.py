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


def _banks():
    """Every slot of every conversation bank: (name, {register: [lines]})."""
    for kind, by in C.CONCERN.items():
        yield "concern:" + kind, by
    for kind, by in C.CALLBACK.items():
        yield "callback:" + kind, by
    for tone, moods in C.TONE_REPLY.items():
        for mood, by in moods.items():
            yield f"tone:{tone}:{mood}", by
    yield "withhold", C.WITHHOLD
    for mood, by in C.THIRD.items():
        yield "third:" + mood, by


def test_every_bank_has_every_register_with_room_to_vary():
    import re
    assert set(C.CONCERN) == {"betrayed", "redline", "courted", "owed", "dislike", "want", "listening"}
    assert set(C.CALLBACK) == {"kept", "deal", "lied", "capital", "capital_warm", "capital_cool", "offer"}
    assert set(C.TONE_REPLY) == set(C.TONES) | {"address"} and all(set(m) == {"good", "bad"} for m in C.TONE_REPLY.values())
    assert set(C.THIRD) == {"warm", "cold"}
    fields = {"rival": "Freedonia", "n": 3, "label": "sets up a panel of experts"}
    for name, by in _banks():
        assert set(by) == set(VO.REGISTERS), name
        for reg, lines in by.items():
            assert len(lines) >= 5 and len(set(lines)) == len(lines), (name, reg)
            for s in lines:
                said = s.format(**fields)                        # every placeholder is one the game can fill
                assert "{" not in said and "}" not in said, s
                assert len(said) <= 170, s                       # short: the game types them out
                assert "  " not in s and s == s.strip() and s[-1] in ".?!", s
                assert not re.search(r"\b(color|honor|favor|organiz|recogniz)", s), s      # British and Australian spelling
                for word in re.findall(r"(?<=[a-z,;:] )[A-Z][a-z]+", s.replace("{", " ").replace("}", " ")):
                    assert word in ("Ambassador", "President", "I", "Go", "Or"), (word, s)   # no country, people or place
    assert all("{rival}" in s for ls in C.CONCERN["courted"].values() for s in ls)
    assert all("{rival}" in s for ls in C.CALLBACK["offer"].values() for s in ls)
    assert all("{n}" in s for k in ("owed", "dislike") for ls in C.CONCERN[k].values() for s in ls)
    assert all("{label}" in s for ls in C.CONCERN["want"].values() for s in ls)
    assert all("red line" in s for ls in C.CONCERN["redline"].values() for s in ls)   # the term is always taught


def test_a_talk_is_spoken_in_the_delegations_own_register(scn):
    heard = {}
    for seed in range(1, 9):
        g = E.new_game(scn, scn.isos[seed % len(scn.isos)], seed=seed)
        g["ap"], g["influence"] = 40, 200
        for iso in _free(scn, g)[:6]:
            reg = VO.voice(scn, g, iso)
            g1, out = E.apply(scn, g, {"do": "talk", "step": "greet", "iso3": iso})
            c = g1["conv"]["concern"]
            lines = [s.format(**{k: v for k, v in c.items() if k != "kind"}) for s in C.CONCERN[c["kind"]][reg]]
            assert any(out["conv"]["reply"].endswith(s) for s in lines), (reg, out["conv"]["reply"])
            _, out = E.apply(scn, g1, {"do": "talk", "step": "follow", "choice": "tone:empathise"})
            if not g1["conv"]["red"]:
                assert out["conv"]["reply"] in C.TONE_REPLY["empathise"]["good"][reg]
                heard.setdefault(reg, set()).add(out["conv"]["reply"])
            g = {**g1, "conv": None}                             # keep the memory of lines heard, leave the talk
    assert len(heard) >= 3, heard


def test_corridor_news_a_rivals_offer_and_a_pressing_capital(scn):
    g = E.new_game(scn, scn.isos[0], seed=6)
    iso = _free(scn, g)[0]
    rival = g["rivals"][0]["iso3"]
    name = scn.member(rival).name
    g["sway"][rival][iso] = 0.9                                  # a rival is courting them
    cb = C._callback(scn, g, iso, "courted")
    assert not cb or cb["kind"] != "offer"                       # already their concern: it isn't said twice
    g.pop("conv_heard", None)
    cb = C._callback(scn, g, iso, "betrayed")                    # something weighs on them more: the offer is the news
    assert cb == {"kind": "offer", "rival": name}
    assert C._callback(scn, g, iso, "betrayed") != cb            # and it is news only once in a stage
    g["chapter"] += 1
    assert C._callback(scn, g, iso, "betrayed") == cb            # a new stage, and it is worth saying again
    # a position that has shifted: new instructions from home, easier or tighter
    g2 = E.new_game(scn, scn.isos[0], seed=6)
    tag = sorted(scn.tags)[0]
    g2["drift"] = {iso: {tag: 0.5}}
    assert C._callback(scn, g2, iso, "listening")["kind"] == "capital_warm"
    g2["drift"] = {iso: {tag: -0.5}}
    g2.pop("conv_heard")
    assert C._callback(scn, g2, iso, "listening")["kind"] == "capital_cool"

    def pressed(seed):                                           # with nothing else to say, a seeded few are pressed by home
        g3 = E.new_game(scn, scn.isos[0], seed=seed)
        g3["drift"] = {}
        return [i for i in _free(scn, g3) if (C._callback(scn, g3, i, "listening") or {}).get("kind") == "capital"]

    counts = [len(pressed(s)) for s in range(1, 13)]
    assert pressed(4) == pressed(4) and 0 < sum(counts) < 12 * len(_free(scn, g)) / 2
    # and the greeting says it, in their voice, before their concern
    g4 = E.new_game(scn, scn.isos[0], seed=6)
    g4["sway"][rival][iso] = 0.9
    E._betray(scn, g4, iso, "test")
    g4, out = E.apply(scn, g4, {"do": "talk", "step": "greet", "iso3": iso})
    reg = VO.voice(scn, g4, iso)
    assert any(out["conv"]["reply"].startswith(s.format(rival=name)) for s in C.CALLBACK["offer"][reg]), out["conv"]["reply"]
    assert out["conv"]["concern"] == "betrayed"


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
