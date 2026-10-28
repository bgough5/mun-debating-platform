"""Debating draws (spec Phase 3 exit): no repeat pairings where avoidable, side balance, determinism, byes, houses."""
import random

import pytest

from app.engine.draw import Adj, Room, TeamState, allocate_adjudicators, allocate_rooms, make_draw, plan_practice, rank_key


def teams(n, houses=4):
    return [TeamState(i, f"T{i}", house=i % houses) for i in range(1, n + 1)]


def play(ts, pairs, rng):
    by = {t.id: t for t in ts}
    for p in pairs:
        a = by[p.aff]
        if p.neg is None:
            a.byes += 1
            a.wins += 1
            continue
        n = by[p.neg]
        a.aff += 1
        n.neg += 1
        a.opponents.add(n.id)
        n.opponents.add(a.id)
        win = a if rng.random() < 0.5 else n
        win.wins += 1
        a.points += rng.randint(180, 230)
        n.points += rng.randint(180, 230)


def run_event(n, rounds, seed, houses=4):
    ts = teams(n, houses)
    rng = random.Random(seed)
    history = []
    for r in range(1, rounds + 1):
        pairs = make_draw(ts, "random" if r == 1 else "power", seed * 100 + r)
        history.append(pairs)
        play(ts, pairs, rng)
    return ts, history


def test_same_seed_same_draw():
    a = make_draw(teams(12), "random", 42)
    b = make_draw(list(reversed(teams(12))), "random", 42)
    assert [(p.aff, p.neg) for p in a] == [(p.aff, p.neg) for p in b]
    assert [(p.aff, p.neg) for p in make_draw(teams(12), "random", 43)] != [(p.aff, p.neg) for p in a]


def test_everyone_debates_once_per_round():
    for n in (2, 3, 7, 16, 33, 108, 109):
        pairs = make_draw(teams(n), "random", n)
        ids = [p.aff for p in pairs] + [p.neg for p in pairs if p.neg]
        assert sorted(ids) == list(range(1, n + 1))
        assert sum(1 for p in pairs if p.neg is None) == n % 2


@pytest.mark.parametrize("seed", range(40))
def test_no_repeat_pairings_when_avoidable(seed):
    # 16 teams, 5 rounds: there are always unused opponents, so no repeats should occur.
    ts, history = run_event(16, 5, seed)
    seen = set()
    for pairs in history:
        for p in pairs:
            if p.neg is None:
                continue
            key = frozenset((p.aff, p.neg))
            assert key not in seen, (seed, key)
            seen.add(key)


def test_side_balance():
    worst = []
    within_one = total = 0
    for seed in range(100):
        ts, _ = run_event(16, 4, seed)
        for t in ts:
            total += 1
            within_one += abs(t.aff - t.neg) <= 1
            worst.append(abs(t.aff - t.neg))
    assert max(worst) <= 2
    assert within_one / total >= 0.95, within_one / total


def test_byes_rotate():
    ts, history = run_event(7, 7, 3)
    assert all(t.byes == 1 for t in ts)   # 7 teams, 7 rounds: each team sits out exactly once


def test_same_house_avoided_in_house_carnival():
    ts = teams(32, houses=4)
    for seed in range(20):
        pairs = make_draw(ts, "random", seed, avoid_house=True)
        by = {t.id: t for t in ts}
        assert not [p for p in pairs if p.neg and by[p.aff].house == by[p.neg].house]


def test_relaxed_rules_are_reported():
    # Two teams from the same house and nobody else: the rule must break, and the draw says so.
    ts = [TeamState(1, house=1), TeamState(2, house=1)]
    pairs = make_draw(ts, "random", 1)
    assert pairs[0].relaxed == ["same house"]


def test_power_pairing_pairs_by_wins():
    ts = teams(8)
    for t in ts:
        t.wins = 1 if t.id <= 4 else 0
    pairs = make_draw(ts, "power", 9, avoid_house=False)
    by = {t.id: t for t in ts}
    for p in pairs:
        assert by[p.aff].wins == by[p.neg].wins


def test_rank_ties_broken_by_id():
    a, b = TeamState(5, wins=2, points=100), TeamState(3, wins=2, points=100)
    assert sorted([a, b], key=rank_key)[0].id == 3


def test_rooms_and_accessibility():
    ts = {i: TeamState(i) for i in range(1, 7)}
    ts[6].needs_accessible = True
    pairs = make_draw(list(ts.values()), "random", 1, avoid_house=False)
    rooms = [Room(1, accessible=False, priority=100), Room(2, True, 90), Room(3, False, 80)]
    assert allocate_rooms(pairs, rooms, ts) == []
    for p in pairs:
        if 6 in (p.aff, p.neg):
            assert p.room == 2


def test_adjudicators_avoid_house_conflicts_and_best_to_top():
    ts = {i: TeamState(i, house=(i - 1) // 2, wins=4 - (i - 1) // 2) for i in range(1, 9)}   # houses 0..3
    pairs = make_draw(list(ts.values()), "power", 1, avoid_house=False)
    adjs = [Adj(1, 9, house=pairs[0].aff and ts[pairs[0].aff].house), Adj(2, 8), Adj(3, 7), Adj(4, 6), Adj(5, 4)]
    problems = allocate_adjudicators(pairs, adjs, ts)
    assert problems == []
    for p in pairs:
        chair = p.adjudicators[0][0]
        a = next(x for x in adjs if x.id == chair)
        assert a.house not in (ts[p.aff].house, ts[p.neg].house)
    assert sum(len(p.adjudicators) for p in pairs) == 5


@pytest.mark.parametrize("n", range(1, 26))
def test_practice_plan_uses_everyone(n):
    plan = plan_practice(n)
    used = sum(r.get("speakers", 0) + r.get("aff", 0) + r.get("neg", 0) + r.get("adjudicators", 0) for r in plan)
    assert used == n
    for r in plan:
        if r["format"] != "solo":
            assert r["aff"] == r["neg"] >= 1
