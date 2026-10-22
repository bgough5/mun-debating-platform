"""Calibration maths against hand-computed examples, plus synthetic calibrated/over-confident data (spec §5.8)."""
import math
import random

import pytest

from app.engine.calibration import (Item, bootstrap, brier, log_loss, point_probs, reliability, report, verdict,
                                    wilson)


def test_brier_hand_computed():
    # (0.7, 0.2, 0.1) actual yes: (0.3)^2 + 0.2^2 + 0.1^2 = 0.14
    # (0.5, 0.25, 0.25) actual no: 0.25 + 0.0625 + 0.5625 = 0.875
    items = [Item((0.7, 0.2, 0.1), "yes"), Item((0.5, 0.25, 0.25), "no")]
    assert brier(items) == pytest.approx((0.14 + 0.875) / 2)


def test_brier_bounds():
    assert brier([Item((1, 0, 0), "yes")]) == 0
    assert brier([Item((1, 0, 0), "no")]) == 2


def test_log_loss_hand_computed():
    items = [Item((0.7, 0.2, 0.1), "yes"), Item((0.5, 0.25, 0.25), "no")]
    assert log_loss(items) == pytest.approx((-math.log(0.7) - math.log(0.25)) / 2)


def test_log_loss_clips_zero():
    assert math.isfinite(log_loss([Item((1, 0, 0), "no")]))


def test_reliability_bins_hand_computed():
    # Two items, pooled one-vs-rest pairs: 0.7->1, 0.2->0, 0.1->0, 0.5->0, 0.25->0, 0.25->1
    items = [Item((0.7, 0.2, 0.1), "yes"), Item((0.5, 0.25, 0.25), "no")]
    bins = {round(b.lo, 1): b for b in reliability(items, min_n=1)}
    assert bins[0.1].n == 1 and bins[0.1].observed == 0
    assert bins[0.2].n == 3 and bins[0.2].observed == pytest.approx(1 / 3)
    assert bins[0.2].mean_predicted == pytest.approx((0.2 + 0.25 + 0.25) / 3)
    assert bins[0.5].n == 1 and bins[0.7].n == 1 and bins[0.7].observed == 1


def test_wilson_known_value():
    lo, hi = wilson(5, 10)
    assert lo == pytest.approx(0.2366, abs=1e-3) and hi == pytest.approx(0.7634, abs=1e-3)


def _synthetic(n, seed, distort):
    rng = random.Random(seed)
    items = []
    for _ in range(n):
        a, b = sorted((rng.random(), rng.random()))
        true = (a, b - a, 1 - b)
        r = rng.random()
        actual = "yes" if r < true[0] else ("abstain" if r < true[0] + true[1] else "no")
        items.append(Item(distort(true), actual))
    return items


def test_perfectly_calibrated_scores_as_calibrated():
    items = _synthetic(3000, 1, lambda p: p)
    assert verdict(reliability(items)) == "calibrated within noise"


def sharpen(p, power=4):
    q = [x ** power for x in p]
    s = sum(q)
    return tuple(x / s for x in q)


def test_over_confident_is_flagged():
    items = _synthetic(3000, 2, sharpen)
    assert verdict(reliability(items)) == "over-confident"


def test_under_confident_is_flagged():
    items = _synthetic(3000, 3, lambda p: tuple(0.5 * x + 0.5 / 3 for x in p))
    assert verdict(reliability(items)) == "under-confident"


def test_bootstrap_interval_contains_point_and_is_seeded():
    items = _synthetic(400, 4, lambda p: p)
    lo, hi = bootstrap(items, brier)
    assert lo <= brier(items) <= hi
    assert bootstrap(items, brier) == (lo, hi)


def test_report_compares_baselines_and_warns_small_samples():
    items = _synthetic(120, 5, lambda p: p)
    always_yes = [Item(point_probs("yes"), it.actual) for it in items]
    rep = report(items, {"everyone votes yes": always_yes}, reps=300)
    assert rep.n == 120
    assert rep.baselines[0]["name"] == "everyone votes yes"
    assert any("Only 120" in w for w in rep.warnings)
    assert rep.baselines[0]["beats"]          # informative probabilities beat a constant guess


def test_report_says_when_model_does_not_beat_baseline():
    items = _synthetic(200, 6, lambda p: (1 / 3, 1 / 3, 1 / 3))
    truth = [Item(it.probs, it.actual) for it in items]
    rep = report(items, {"same as model": truth}, reps=200)
    assert not rep.baselines[0]["beats"]
    assert any("does not clearly beat" in w for w in rep.warnings)
