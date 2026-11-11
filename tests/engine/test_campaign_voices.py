"""The Session: every delegation has its own voice (Ben's playtest, 10 Nov 2026). A delegation keeps one register all
game; different kinds of delegation speak differently; what is said never contradicts where they stand; and nothing
about a game's numbers or its replay changes."""
import json
import random
import re

import pytest

from app.db import SYSTEM
from app.modules.sim import play
from app.modules.sim.campaign import engine as E
from app.modules.sim.campaign import econ as X
from app.modules.sim.campaign import talks as T
from app.modules.sim.campaign import voices as VO
from app.modules.sim.campaign.bots import Bot

PACKS = ("comet_halcyon", "ga_climate_transition", "sc_ai_cyber")


def _load(app, code):
    from app.modules.sim.campaign.scenario import load
    with app.state.db.write(SYSTEM) as w:
        cid = play.guest_committee(w, code)
    with app.state.db.read() as conn:
        scn = load(conn, cid, code)
        scn.warm(1)
        return scn


@pytest.fixture
def scn(app):
    from app.modules.sim.campaign.scenario import load
    with app.state.db.write(SYSTEM) as w:
        cid = play.guest_committee(w, "ga_climate_transition")
    with app.state.db.read() as conn:
        yield load(conn, cid, "ga_climate_transition")


def _others(scn, g):
    return [i for i in scn.isos if i != g["iso3"]]


def _strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from _strings(v)
    elif isinstance(x, (list, tuple)):
        for v in x:
            yield from _strings(v)


def test_every_register_has_every_line_and_reads_plainly():
    banks = (VO.REACT, VO.VERDICT, VO.BUT, VO.STILL, VO.STANCE, VO.RED, VO.GREET, VO.VISIT, VO.REPLY, VO.CAUCUS, VO.FLOOR, VO.STATEMENT)
    assert all(set(b) == set(VO.REGISTERS) for b in banks) and set(VO.MANNER) == set(VO.REGISTERS)
    for reg in VO.REGISTERS:
        for level in ("strong", "some", "weak"):
            assert len(set(VO.REACT[reg][level])) >= 3 and len(set(VO.VERDICT[reg][level])) >= 3
        assert set(VO.STANCE[reg]) == {2, 1, 0, -1, -2} and all(len(set(v)) >= 3 for v in VO.STANCE[reg].values())
        assert len(set(VO.BUT[reg])) >= 3 and len(set(VO.STILL[reg])) >= 3
        assert len(set(VO.GREET[reg])) >= 3 and len(set(VO.FLOOR[reg])) >= 3
        assert set(VO.VISIT[reg]) == {"ask", "ally", "info", "persuade", "collect", "olive", "leak"}
        assert set(VO.STATEMENT[reg]) == {"for", "toofar", "against", "wait", "truce"}
        for speech in ("rally", "reassure", "demand"):
            for how in ("pleased", "unmoved", "annoyed"):
                assert len(set(VO.CAUCUS[reg][speech][how] + [VO.CAUCUS[reg]["any"][how]])) >= 3
        assert all("red line" in x for when in ("open", "close") for x in VO.RED[reg][when])    # the term is always taught
    lines = [s for b in banks for s in _strings(b)]
    assert len(lines) == len(set(lines)) or len(lines) - len(set(lines)) <= 12            # registers share very few lines
    for s in lines:
        assert len(s) <= 170, s                                  # short: the game types them out
        assert not re.search(r"\b(color|honor|favor|organiz|recogniz)", s), s     # British and Australian spelling
        assert "  " not in s and s == s.strip() and s[-1] in ".?!:", s
    # no line names a country, a people or a place: a voice comes from a delegation's role, never its culture
    for s in lines:
        for word in re.findall(r"(?<=[a-z,;:] )[A-Z][a-z]+", s.replace("{", " ").replace("}", " ")):
            assert word in ("Ambassador", "President", "I", "Go", "Or"), (word, s)


def test_a_delegation_keeps_one_register_all_game(scn):
    g = E.new_game(scn, scn.isos[2], "quick", seed=5)
    start = {i: VO.voice(scn, g, i) for i in _others(scn, g)}
    assert all(v in VO.REGISTERS for v in start.values())
    bot, turns = Bot(scn, "broker", 5), 0
    while g["phase"] == "chapter" and turns < 60:
        g = bot.turn(g)
        turns += 1
        assert {i: VO.voice(scn, g, i) for i in start} == start
    assert g["phase"] == "summit" and turns >= 4                          # a whole session of stages
    g = bot.play(g)
    assert {i: VO.voice(scn, g, i) for i in start} == start
    assert {i: VO.voice(scn, json.loads(json.dumps(g)), i) for i in start} == start       # and survives a save


def test_different_kinds_of_delegation_speak_differently(app):
    grave_p5, urgent_small, seen, per_game = [], [], set(), []
    for code in PACKS:
        scn = _load(app, code)
        for seed in range(1, 9):
            g = E.new_game(scn, scn.isos[seed % len(scn.isos)], seed=seed)
            vs = {i: VO.voice(scn, g, i) for i in _others(scn, g)}
            seen |= set(vs.values())
            per_game.append(len(set(vs.values())))
            for i, v in vs.items():
                m, t = scn.member(i), X.traits(i)
                rival = any(r["iso3"] == i for r in g["rivals"])
                if m.p5:
                    grave_p5.append(v == "grave")
                    assert v != "urgent"
                if t["known"] and t["size"] >= 3:
                    assert v != "urgent", (i, v)                 # a large economy never speaks as an exposed state
                if t["known"] and t["size"] == 1 and (t["aid"] or t["low"]) and not rival:
                    urgent_small.append(v == "urgent")
                    assert v != "grave", (i, v)
    assert seen == set(VO.REGISTERS), seen                       # every register is heard somewhere
    assert min(per_game) >= 3, per_game                          # and no room speaks with one voice
    assert grave_p5 and sum(grave_p5) / len(grave_p5) >= 0.85, sum(grave_p5) / max(1, len(grave_p5))
    if urgent_small:
        assert sum(urgent_small) / len(urgent_small) >= 0.4, sum(urgent_small) / len(urgent_small)


def test_a_rivals_style_colours_its_voice(scn):
    counts = {s: {} for s in ("hawk", "broker", "spoiler")}
    for seed in range(1, 40):
        g = E.new_game(scn, scn.isos[seed % len(scn.isos)], seed=seed)
        for rv in g["rivals"]:
            if scn.member(rv["iso3"]).p5:
                continue
            v = VO.voice(scn, g, rv["iso3"])
            counts[rv["style"]][v] = counts[rv["style"]].get(v, 0) + 1
    assert counts["hawk"].get("warm", 0) < counts["broker"].get("warm", 0) + counts["broker"].get("blunt", 0)
    assert counts["spoiler"].get("guarded", 0) + counts["spoiler"].get("measured", 0) > sum(counts["spoiler"].values()) / 2


def test_an_answer_never_contradicts_the_stance(scn):
    """Ben's coherence rule in every register: a good case that doesn't win them, or a weak case to a friend, is joined
    by a bridge, and the closing line is always the delegation's true stance."""
    found = {}
    for seed in range(3, 30):
        g = E.new_game(scn, scn.isos[1], seed=seed)
        for i in _others(scn, g):
            found.setdefault(VO.voice(scn, g, i), (g, i))
    assert set(found) == set(VO.REGISTERS), set(found)
    for reg, (g, iso) in found.items():
        for level in ("strong", "some", "weak"):
            for b in (2, 1, 0, -1, -2):
                for n in range(12):
                    g["n"] = n
                    said = VO.answer(scn, g, iso, level, b)
                    close = next(x for x in VO.STANCE[reg][b] if said.endswith(x))            # the true stance, last
                    head = said[:-len(close)].strip()
                    lead = next(x for x in VO.VERDICT[reg][level] if head.startswith(x))
                    bridge = head[len(lead):].strip()
                    if level != "weak" and b < 0:
                        assert bridge in VO.BUT[reg], said
                    elif level == "weak" and b > 0:
                        assert bridge in VO.STILL[reg], said
                    else:
                        assert bridge == "", said
                    for other in (2, 1, 0, -1, -2):
                        if other != b:
                            assert not any(x in said for x in VO.STANCE[reg][other]), said
    # the words themselves: support never sounds like refusal, and refusal never like support
    yes = re.compile(r"\b(support|with you|back you|behind your position|we're in|our vote|count on us|in favour|on your side|lean|probably yes|in principle, yes)", re.I)
    no = re.compile(r"\b(cannot|can't|oppose|against|\bno\b|concern|worr|problem|difficulty|reservation|troubl|doubt|uneasy|bad for us|not a text|don't like)", re.I)
    for reg in VO.REGISTERS:
        assert all(yes.search(x) for b in (1, 2) for x in VO.STANCE[reg][b]), reg
        assert all(no.search(x) and not re.search(r"\b(we support|with you|back you|count on us)\b", x) for b in (-1, -2) for x in VO.STANCE[reg][b]), reg
        assert all("abstain" in x or "abstention" in x or "either way" in x for x in VO.STANCE[reg][0]), reg
        assert all(re.search(r"\b(goal|aim|purpose|interest|need|works for us|suits us|answers our problem)", x) for x in VO.STILL[reg]), reg


def test_talks_are_voiced_and_follow_the_same_logic(scn):
    """What a delegation says in a talk is its own register's line for exactly the outcome the engine worked out."""
    heard = {}
    for seed in range(1, 7):
        g = E.new_game(scn, scn.isos[1], seed=seed)
        g["ap"], g["influence"] = 60, 400
        must = g["mandate"]["must"]
        for iso in [i for i in scn.isos if i not in E._others(g)][:14]:
            reg = VO.voice(scn, g, iso)
            red = E.mu_of(scn, g, iso, [must]) <= E.R["redline"]
            arg = sorted(T.ARGS)[(seed + len(heard)) % 5]
            g, out = E.apply(scn, g, {"do": "talk", "iso3": iso, "arg": arg})
            reply = out["conv"]["reply"]
            if red:
                assert reply in VO.RED[reg]["open"]
            else:
                assert reply in VO.REACT[reg][out["conv"]["tone"]]                              # first talk: no memory prefix
            g, out = E.apply(scn, g, {"do": "talk", "step": "follow", "choice": "close"})
            if red:
                assert out["heard"] in VO.RED[reg]["close"]
            else:
                b = E.bucket(E.mu_of(scn, g, iso, [must]) + g["sway"]["you"][iso])
                assert any(out["heard"].endswith(x) for x in VO.STANCE[reg][b]), (out["heard"], b)
                level = "strong" if out["q"] >= 0.9 else "some" if out["q"] >= 0.5 else "weak"
                assert any(out["heard"].startswith(x) for x in VO.VERDICT[reg][level])
            heard.setdefault(reg, set()).add(out["heard"])
    assert len(heard) >= 4 and sum(len(v) for v in heard.values()) >= 20


def test_visits_caucus_and_statements_are_voiced(scn):
    texts, regs = set(), set()
    for seed in range(1, 16):
        g = E.new_game(scn, scn.isos[seed % len(scn.isos)], seed=seed)
        for _ in range(3):
            g, _ = E.apply(scn, g, {"do": "end_turn"})
            for v in g["visits"]:
                if v["kind"] in ("ask", "ally", "info", "persuade", "collect", "olive", "leak") and v.get("step", 1) == 1:
                    reg = VO.voice(scn, g, v["iso3"])
                    quote = v["text"].split("“", 1)[1].rstrip("”")
                    assert any(quote.startswith(x) for x in VO.GREET[reg]), v["text"]
                    assert v["text"].startswith(scn.member(v["iso3"]).name)
                    texts.add(v["kind"] + ":" + reg)
                    regs.add(reg)
            g["visits"] = [v for v in g["visits"] if v["kind"] in ("capital", "caucus")]
            for v in list(g["visits"]):
                g, _ = E.apply(scn, g, {"do": "visit", "id": v["id"], "choice": v["options"][0]["code"]})
    assert len(regs) >= 4 and len(texts) >= 10, texts
    # the Summit: each statement opens the way its delegation takes the floor, and still says where it stands
    g = E.new_game(scn, scn.isos[1], "quick", seed=9)
    assert E.final_clause(g)["tags"]
    E._open_summit(scn, g)
    sts = g["summit"]["statements"]
    assert len(sts) >= len(g["rivals"])
    for s in sts:
        reg = VO.voice(scn, g, s["iso3"])
        assert any(s["text"].startswith(x) for x in VO.FLOOR[reg]), s
        assert "{" not in s["text"]
    rivals = {r["iso3"]: r for r in g["rivals"]}
    final = E.final_clause(g)
    for s in sts:
        rv = rivals.get(s["iso3"])
        if rv and not rv.get("truce"):
            tag = rv["block"] if rv["block"] in final["tags"] else rv["want"]
            assert E._lc(scn.tags[tag]).rstrip(".") in s["text"]                               # the same demand as before
    assert {VO.voice(scn, g, s["iso3"]) for s in sts} != {"grave"} or len(sts) <= 2
    assert E.SM._statements(scn, g) == sts                                                    # the same every time


def test_voices_change_no_numbers_and_games_replay_identically(scn):
    def play_once(seed):
        g = E.new_game(scn, scn.isos[3], "quick", seed=seed)
        bot, said = Bot(scn, "broker", seed), []
        while g["phase"] == "chapter":
            g = bot.turn(g)
            said += [v["text"] for v in g.get("visits", [])]
        said += [s["text"] for s in g["summit"]["statements"]]
        return bot.play(g), said

    a, said_a = play_once(11)
    b, said_b = play_once(11)
    assert a == b and said_a == said_b                            # the same seed: the same game, word for word
    c, said_c = play_once(12)
    assert said_c != said_a
    # choosing a line never draws from the game's own counter
    g = E.new_game(scn, scn.isos[3], seed=11)
    before = json.dumps(g, sort_keys=True)
    state = random.getstate()
    for iso in _others(scn, g):
        VO.voice(scn, g, iso), VO.answer(scn, g, iso, "some", 0), VO.greet(scn, g, iso), VO.caucus(scn, g, iso, "rally", "pleased")
    g.pop("lines_used", None)                                   # the only trace: which lines have been heard (11 Nov)
    assert json.dumps(g, sort_keys=True) == before and random.getstate() == state


def test_the_view_shows_each_delegations_manner(scn):
    from app.modules.sim.campaign import store
    g = E.new_game(scn, scn.isos[1], seed=4)
    v = store.view(scn, g)
    seen = set()
    for iso, t in v["tokens"].items():
        if iso == g["iso3"]:
            continue
        assert t["manner"]["name"] == VO.MANNER[VO.voice(scn, g, iso)][0] and t["manner"]["what"]
        seen.add(t["manner"]["name"])
    assert len(seen) >= 3
