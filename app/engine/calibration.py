"""Calibration maths (spec §5.6).

An *item* is one country's predicted (p_yes, p_abstain, p_no) for one vote,
plus the vote it actually cast. Reports always show the sample size, a
bootstrap interval, and comparisons with baselines. With a few hundred
country-votes the intervals are wide, and the report says so.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

CLASSES = ("yes", "abstain", "no")
EPS = 1e-6


@dataclass(frozen=True)
class Item:
    probs: tuple          # (p_yes, p_abstain, p_no)
    actual: str           # 'yes' | 'abstain' | 'no'
    group: str = ""       # e.g. the vote it belongs to (for reporting only)


def _norm(p: tuple) -> tuple:
    s = sum(p)
    return tuple(x / s for x in p) if s > 0 else (1 / 3, 1 / 3, 1 / 3)


def brier(items: list[Item]) -> float:
    """Multi-class Brier score: mean over items of sum_k (p_k - o_k)^2. 0 is perfect, 2 is worst."""
    if not items:
        return float("nan")
    total = 0.0
    for it in items:
        p = _norm(it.probs)
        for k, c in enumerate(CLASSES):
            o = 1.0 if it.actual == c else 0.0
            total += (p[k] - o) ** 2
    return total / len(items)


def log_loss(items: list[Item]) -> float:
    """Mean negative log probability of the actual vote (natural log), clipped at EPS."""
    if not items:
        return float("nan")
    total = 0.0
    for it in items:
        p = _norm(it.probs)
        total -= math.log(max(EPS, p[CLASSES.index(it.actual)]))
    return total / len(items)


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    phat = k / n
    den = 1 + z * z / n
    centre = (phat + z * z / (2 * n)) / den
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


@dataclass(frozen=True)
class Bin:
    lo: float
    hi: float
    n: int
    mean_predicted: float
    observed: float
    ci_lo: float
    ci_hi: float
    flagged: bool          # mean prediction falls outside the 95% Wilson interval of what happened


def reliability(items: list[Item], bins: int = 10, min_n: int = 5, alpha: float = 0.05) -> list[Bin]:
    """Pooled one-vs-rest reliability over all three classes.

    A bin is flagged when its mean prediction falls outside the Wilson interval
    of what happened. The interval is Bonferroni-corrected across bins, so a
    well-calibrated model is not flagged just because there are ten chances.
    """
    z = _z_two_sided(alpha / bins)
    pairs = []
    for it in items:
        p = _norm(it.probs)
        for k, c in enumerate(CLASSES):
            pairs.append((p[k], 1 if it.actual == c else 0))
    out = []
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        sel = [(p, o) for p, o in pairs if (lo <= p < hi) or (b == bins - 1 and p == 1.0)]
        if not sel:
            continue
        n = len(sel)
        k = sum(o for _, o in sel)
        mp = sum(p for p, _ in sel) / n
        ci = wilson(k, n, z)
        flagged = n >= min_n and not (ci[0] <= mp <= ci[1])
        out.append(Bin(lo, hi, n, mp, k / n, ci[0], ci[1], flagged))
    return out


def _z_two_sided(alpha: float) -> float:
    """Normal quantile for a two-sided level, by bisection (no scipy)."""
    target = 1 - alpha / 2
    lo, hi = 0.0, 10.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if 0.5 * (1 + math.erf(mid / math.sqrt(2))) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def expected_calibration_error(rel: list[Bin]) -> float:
    total = sum(b.n for b in rel)
    return sum(b.n * abs(b.mean_predicted - b.observed) for b in rel) / total if total else float("nan")


def verdict(rel: list[Bin]) -> str:
    """Plain-English verdict on the reliability table.

    Over-confident means predictions are more extreme than outcomes: above the
    uninformative 1/3 they happen less often than predicted, below it more often.
    """
    flagged = [b for b in rel if b.flagged]
    if not flagged:
        return "calibrated within noise"
    pivot = 1 / 3
    over = sum(1 for b in flagged if (b.mean_predicted > pivot and b.observed < b.mean_predicted)
               or (b.mean_predicted < pivot and b.observed > b.mean_predicted))
    under = len(flagged) - over
    if over and not under:
        return "over-confident"
    if under and not over:
        return "under-confident"
    return "miscalibrated"


def bootstrap(items: list[Item], stat, reps: int = 1000, seed: int = 7, level: float = 0.90) -> tuple[float, float]:
    if not items:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    n = len(items)
    vals = sorted(stat([items[rng.randrange(n)] for _ in range(n)]) for _ in range(reps))
    a = (1 - level) / 2
    return (vals[int(a * (reps - 1))], vals[int(math.ceil((1 - a) * (reps - 1)))])


def paired_bootstrap_diff(model: list[Item], base: list[Item], stat, reps: int = 1000, seed: int = 11,
                          level: float = 0.90) -> tuple[float, float, float]:
    """(point, lo, hi) for stat(model) - stat(base) on the same items, resampled together."""
    assert len(model) == len(base)
    n = len(model)
    point = stat(model) - stat(base)
    if n == 0:
        return (float("nan"),) * 3
    rng = random.Random(seed)
    vals = []
    for _ in range(reps):
        idx = [rng.randrange(n) for _ in range(n)]
        vals.append(stat([model[i] for i in idx]) - stat([base[i] for i in idx]))
    vals.sort()
    a = (1 - level) / 2
    return (point, vals[int(a * (reps - 1))], vals[int(math.ceil((1 - a) * (reps - 1)))])


# ---- baselines ----
# Deterministic baselines are smoothed so log loss stays finite: the predicted
# vote gets 1 - 2*SMOOTH and the other two get SMOOTH each.
SMOOTH = 0.05


def point_probs(vote: str) -> tuple:
    return tuple(1 - 2 * SMOOTH if c == vote else SMOOTH for c in CLASSES)


@dataclass
class Report:
    n: int
    votes: int
    brier: float
    brier_ci: tuple
    log_loss: float
    log_loss_ci: tuple
    reliability: list
    ece: float
    verdict: str
    baselines: list = field(default_factory=list)   # dicts: name, brier, log_loss, diff, diff_lo, diff_hi, beats
    warnings: list = field(default_factory=list)


def report(items: list[Item], baselines: dict[str, list[Item]], reps: int = 1000) -> Report:
    rel = reliability(items)
    r = Report(
        n=len(items), votes=len({it.group for it in items}),
        brier=brier(items), brier_ci=bootstrap(items, brier, reps),
        log_loss=log_loss(items), log_loss_ci=bootstrap(items, log_loss, reps),
        reliability=rel, ece=expected_calibration_error(rel), verdict=verdict(rel),
    )
    for name, base in baselines.items():
        point, lo, hi = paired_bootstrap_diff(items, base, brier, reps)
        r.baselines.append({
            "name": name, "brier": brier(base), "log_loss": log_loss(base),
            "diff": point, "diff_lo": lo, "diff_hi": hi,
            # The model only "beats" a baseline if the whole 90% interval of the
            # Brier difference is below zero.
            "beats": hi < 0, "loses": lo > 0,
        })
    if r.n < 300:
        r.warnings.append(
            f"Only {r.n} country-votes. Intervals are wide; treat any difference from the baselines as unproven.")
    if any(not b["beats"] for b in r.baselines):
        r.warnings.append("The model does not clearly beat every baseline on this data.")
    return r
