"""Simulation: determinism, tie-breaking, unknown handling, accuracy against an exact answer (spec §5.8)."""
import math

from app.engine.model import CountryInput, ModelParams, Source, distribution, unknown_share
from app.engine.rules import GA_SIMPLE, GA_TWO_THIRDS, SC_SUBSTANTIVE
from app.engine.simulate import SwingRow, exact_p_pass, rank, simulate

P = ModelParams()


def dist(iso, pos, weight=2.0, group="", rho=0.0):
    srcs = (Source(pos, weight, "official_statement", "Official statement"),) if weight else ()
    return distribution(CountryInput(iso, iso, srcs, group, rho), P)


def chamber(n=31, group=""):
    # A spread of positions around the cut-points so the outcome is uncertain.
    return [dist(f"C{i:02d}", -1.2 + 2.6 * i / (n - 1), 1.0 + (i % 3), group, 0.3 if group else 0.0)
            for i in range(n)]


def test_same_seed_identical_output():
    ds = chamber(group="G")
    blocs = {"G": ("Group", [d.iso3 for d in ds[:10]])}
    a = simulate(ds, GA_SIMPLE, P, runs=2000, seed=42, blocs=blocs, with_swing=True)
    b = simulate(list(reversed(ds)), GA_SIMPLE, P, runs=2000, seed=42, blocs=blocs, with_swing=True)
    assert repr(a) == repr(b)   # byte-identical, independent of input order


def test_different_seed_differs():
    ds = chamber()
    assert simulate(ds, GA_SIMPLE, P, runs=2000, seed=1).yes_hist != simulate(ds, GA_SIMPLE, P, runs=2000, seed=2).yes_hist


def test_simulation_within_3_se_of_exact_ga():
    ds = chamber()
    exact = exact_p_pass(ds, GA_SIMPLE)
    sim = simulate(ds, GA_SIMPLE, P, runs=20000, seed=5)
    assert 0.05 < exact < 0.95, "test case should be uncertain"
    assert abs(sim.p_pass - exact) <= 3 * math.sqrt(exact * (1 - exact) / sim.runs)


def test_simulation_within_3_se_of_exact_two_thirds_and_sc():
    ds = chamber(15)
    for rule in (GA_TWO_THIRDS, SC_SUBSTANTIVE):
        exact = exact_p_pass(ds, rule)
        sim = simulate(ds, rule, P, runs=20000, seed=9)
        se = math.sqrt(max(exact * (1 - exact), 1e-9) / sim.runs)
        assert abs(sim.p_pass - exact) <= 3 * se + 1e-12, rule.code


def test_correlation_widens_yes_interval():
    ind = chamber()
    cor = [distribution(CountryInput(d.iso3, d.name, (Source(d.mu, d.total_weight, "x", "x"),), "G", 0.6), P)
           for d in ind]
    a = simulate(ind, GA_SIMPLE, P, runs=4000, seed=3)
    b = simulate(cor, GA_SIMPLE, P, runs=4000, seed=3)
    assert (b.yes_hi - b.yes_lo) > (a.yes_hi - a.yes_lo)


def test_unknown_country_reported_and_share_nonzero():
    known = [dist(f"K{i}", 1.0) for i in range(10)]
    unknown = distribution(CountryInput("UNK", "Unknownland", ()), P)
    assert unknown.unknown and unknown.mu == 0 and unknown.sigma == P.sigma_unknown
    assert 0.2 < unknown.p_abstain < 0.3 and unknown.p_yes > 0.3   # wide, not confident
    share = unknown_share(known + [unknown])
    assert share > 0
    assert unknown_share(known) == 0


def test_more_evidence_narrows_sigma():
    one = dist("A", 1.0, weight=1.0)
    many = dist("A", 1.0, weight=10.0)
    assert many.sigma < one.sigma < P.sigma_unknown


def test_rank_ties_break_by_iso3():
    rows = [SwingRow("country", k, k, 0.1, 1.0, 0.1) for k in ("ZAF", "AUS", "FJI")]
    rows.append(SwingRow("country", "BRA", "BRA", 0.2, 1.0, 0.2))
    assert [r.key for r in rank(rows)] == ["BRA", "AUS", "FJI", "ZAF"]


def test_swing_identical_countries_tie_on_iso3():
    ds = [dist(f"X{i}", 0.0) for i in range(5)] + [dist("AAA", 0.0), dist("ZZZ", 0.0)]
    res = simulate(ds, GA_SIMPLE, P, runs=3000, seed=4, with_swing=True)
    # Simulated scores differ by noise; whatever they are, the order must follow (score desc, iso3 asc).
    for a, b in zip(res.swing, res.swing[1:]):
        assert (-a.score, a.key) <= (-b.score, b.key)


def test_swing_finds_the_pivotal_country():
    # 7 certain yes, 7 certain no, one undecided: it is the only lever.
    ds = [dist(f"Y{i}", 2.0, 50) for i in range(7)] + [dist(f"N{i}", -2.0, 50) for i in range(7)]
    ds.append(dist("MID", 0.0, 0.5))
    res = simulate(ds, GA_SIMPLE, P, runs=4000, seed=1, with_swing=True)
    assert res.swing[0].key == "MID" and res.swing[0].delta_p > 0.2
