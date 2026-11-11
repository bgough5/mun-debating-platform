"""The vote on the day (Ben's playtest, 10 Nov 2026; design doc section 35): what the player is shown is honest about
its uncertainty. A firm reading can only change for a reason the player can see; a reading near the line is never
certain; and the chance is seeded, so the same game replays the same way."""
import json

import pytest

from app.db import SYSTEM
from app.modules.sim import play
from app.modules.sim.campaign import engine as E
from app.modules.sim.campaign.scenario import load

SEEDS = range(60)


@pytest.fixture
def scn(app):
    with app.state.db.write(SYSTEM) as w:
        cid = play.guest_committee(w, "ga_migration")
    with app.state.db.read() as conn:
        yield load(conn, cid, "ga_migration")


def _room(scn, seed=3):
    """A game ready for its Summit, with three free delegations placed by hand: one just over the line for yes, one
    clearly for, and one clearly against. Nothing is known of anyone's mood (no adviser is posted)."""
    g = E.new_game(scn, scn.isos[seed % len(scn.isos)], "quick", seed=seed)
    for adv in g["staff"]:
        adv["post"] = None
    final = E.final_clause(g)
    free = [i for i in scn.isos if i not in E._others(g) and i != g["iso3"]]
    edge, friend, foe = free[:3]

    def place(iso, x):                                       # move its own position (drift) until it stands at x
        g["drift"][iso] = {}
        gap = x - E.latent(scn, g, iso, final, mood=False)
        g["drift"][iso] = {t: gap for t in final["tags"]}
        assert E.latent(scn, g, iso, final, mood=False) == pytest.approx(x)

    reach = 2 * max(E.doubt(scn, g, i, final) for i in (edge, friend, foe))   # the furthest the hidden part can carry a vote
    place(edge, scn.c_yes + 0.05)
    place(friend, scn.c_yes + reach + 0.3)
    place(foe, scn.c_no - reach - 0.3)
    return g, final, edge, friend, foe


def _on_the_day(scn, g, seed):
    """The same room as the player sees it, on a different day: other moods, another change of heart."""
    g = json.loads(json.dumps(g))
    g["seed"] = seed
    g["moods"] = E._moods(scn, seed)
    E._open_summit(scn, g)
    return g


def test_an_undecided_vote_is_not_fixed_by_what_the_player_sees(scn):
    g, final, edge, _friend, _foe = _room(scn)
    seen = E.reading(scn, g, edge, final)
    assert seen == {"vote": "yes", "sure": "open"}
    assert E.reading_words(seen)["word"].startswith("Wavering")
    votes = []
    for k in SEEDS:
        day = _on_the_day(scn, g, k)
        assert E.reading(scn, day, edge, E.final_clause(day)) == seen          # the player is shown exactly the same
        votes.append(E.votes_on(scn, day, E.final_clause(day))[edge])
    share = votes.count("yes") / len(votes)
    assert 0.25 < share < 0.85                               # it goes the way it leaned more often than not, never surely
    assert len(set(votes)) > 1


def test_a_clear_vote_does_not_flip_without_a_cause(scn):
    g, final, _edge, friend, foe = _room(scn)
    assert E.reading(scn, g, friend, final) == {"vote": "yes", "sure": "firm"}
    assert E.reading(scn, g, foe, final) == {"vote": "no", "sure": "firm"}
    for k in SEEDS:
        day = _on_the_day(scn, g, k)
        votes = E.votes_on(scn, day, E.final_clause(day))
        assert votes[friend] == "yes" and votes[foe] == "no"
    # and for the whole room: no firm reading is ever wrong on the day, whatever the moods
    for k in range(12):
        day = _on_the_day(scn, g, k)
        fc = E.final_clause(day)
        votes = E.votes_on(scn, day, fc)
        for iso in scn.isos:
            if iso in E._others(day) or iso == day["iso3"]:
                continue
            rd = E.reading(scn, day, iso, fc)
            if rd["sure"] == "firm":
                assert votes[iso] == rd["vote"], (k, iso)
    # a cause the player can see does move it: the text turns against it
    turned = json.loads(json.dumps(g))
    turned["drift"][friend] = {t: v - 3.0 for t, v in turned["drift"][friend].items()}
    assert E.reading(scn, turned, friend, final)["vote"] != "yes"


def test_working_the_room_narrows_the_doubt_but_never_to_nothing(scn):
    g, final, edge, _friend, _foe = _room(scn)
    plain = E.doubt(scn, g, edge, final)
    g["sway"]["you"][edge] = 1.0
    st = {**E._stances(scn, g, final), "you": 1}
    talked = E.doubt(scn, g, edge, final, st)
    assert talked > plain                                    # goodwill alone is soft: it can slip on the day
    g["sponsors"].append(edge)
    signed = E.doubt(scn, g, edge, final, st)
    assert E.R["doubt_min"] <= signed < plain                # its own word on paper holds far better, but not perfectly
    g["sponsors"].remove(edge)
    g["sway"]["you"][edge] = 0.0
    assert not E.knows_mood(g, edge)
    g["staff"][0].update(post=edge, since=g.get("tick", 0) - 1)
    assert E.knows_mood(g, edge)                             # an adviser in post learns its mood...
    g["moods"][edge] = -1.5
    rd = E.reading(scn, g, edge, final)
    assert rd["vote"] == "abstain"                           # ...so the reading moves with it
    g["moods"][edge] = 0.0
    assert E.reading(scn, g, edge, final)["sure"] != "firm"  # ...and what is left is the chance on the day


def test_the_projection_counts_the_votes_that_could_still_move(scn):
    g, final, edge, friend, foe = _room(scn)
    p = E.projection(scn, g)
    assert p["votes"][edge] == "yes" and p["votes"][friend] == "yes" and p["votes"][foe] == "no"
    free = [i for i in scn.isos if i not in E._others(g) and i != g["iso3"]]
    assert p["unsure"] == sum(1 for i in free if E.reading(scn, g, i, final)["sure"] != "firm") >= 1


def test_the_chance_is_seeded_so_a_game_replays_the_same(scn):
    def play_it():
        g, _final, edge, _friend, _foe = _room(scn, seed=5)
        before = json.dumps(g, sort_keys=True)
        E._open_summit(scn, g)
        for a in ({"do": "speech", "stance": "bridge"}, {"do": "proceed"},
                  {"do": "caucus", "kind": "unmoderated", "iso3": [edge]}):
            g2, _ = E.apply(scn, g, a)
            g = g2
        guard = 0
        while g["phase"] == "summit" and g["summit"]["step"] == "amendments" and guard < 40:
            guard += 1
            a = {"do": "debate", "choice": "silent"} if g["summit"]["stage"] == "debate" else {"do": "amend_vote", "vote": "abstain"}
            g, _ = E.apply(scn, g, a)
        if g["summit"]["step"] == "final_reading":
            g, _ = E.apply(scn, g, {"do": "proceed"})
        frozen = json.dumps(g, sort_keys=True)
        done, _ = E.apply(scn, g, {"do": "final", "vote": "yes"})
        assert json.dumps(g, sort_keys=True) == frozen       # apply is pure: the game it was given is untouched
        return before, done

    b1, g1 = play_it()
    b2, g2 = play_it()
    assert b1 == b2 and json.dumps(g1, sort_keys=True) == json.dumps(g2, sort_keys=True)
    assert set(g1["summit"]["day"]) == set(scn.isos)
