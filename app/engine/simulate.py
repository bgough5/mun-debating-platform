"""Seeded Monte Carlo pass probability, swing ranking and an exact check (spec §5.1, §5.5).

Determinism: the generator is `random.Random(seed)` (Mersenne Twister, the
same on every platform). Draw order is fixed: per run, one shock per
correlation group in sorted group order, then one draw per country in
sorted ISO-3 order. Same inputs + same seed => identical output.

Swing uses common random numbers: each counterfactual ("this country, or
this bloc, moves one step toward yes") is evaluated on the same draws as
the baseline, so the difference is not swamped by simulation noise.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass, field

from app.engine.model import CountryDist, ModelParams
from app.engine.rules import VotingRule, passes


@dataclass(frozen=True)
class SwingRow:
    kind: str            # 'country' | 'bloc'
    key: str             # iso3 or bloc code
    name: str
    delta_p: float       # change in P(pass) if it moves one step toward yes
    movability: float    # sigma / sigma_unknown: how uncertain we are about it
    score: float         # delta_p * movability; the ranking key
    members: tuple = ()


@dataclass
class SimResult:
    p_pass: float
    mc_se: float
    runs: int
    seed: int
    yes_mean: float
    yes_lo: int
    yes_hi: int
    yes_hist: dict = field(default_factory=dict)
    swing: list = field(default_factory=list)


def _vote(latent: float, c_yes: float, c_no: float) -> int:
    return 1 if latent > c_yes else (-1 if latent < c_no else 0)


def _passes(rule: VotingRule, yes: int, no: int, abstain: int, members: int, vetoes: int) -> bool:
    return passes(rule, yes, abstain, no, members, vetoes > 0)


def simulate(dists: list[CountryDist], rule: VotingRule, params: ModelParams, runs: int = 4000,
             seed: int = 1, members: int | None = None, blocs: dict[str, tuple[str, list[str]]] | None = None,
             with_swing: bool = False, direction: int = 1) -> SimResult:
    """blocs: code -> (name, [iso3 members present in this committee])."""
    if runs < 1:
        raise ValueError("runs must be at least 1")
    ds = sorted(dists, key=lambda d: d.iso3)
    n = len(ds)
    m = members if members is not None else n
    groups = sorted({d.corr_group for d in ds if d.corr_group})
    gidx = {g: i for i, g in enumerate(groups)}
    cy, cn = params.c_yes, params.c_no
    step = params.swing_step * direction
    rng = random.Random(seed)
    gauss = rng.gauss

    mus = [d.mu for d in ds]
    sig_shared = [d.sigma * math.sqrt(d.rho) for d in ds]
    sig_own = [d.sigma * math.sqrt(1.0 - d.rho) for d in ds]
    grp = [gidx.get(d.corr_group, -1) for d in ds]
    veto = [1 if d.iso3.upper() in rule.veto else 0 for d in ds]
    index = {d.iso3: i for i, d in enumerate(ds)}

    bloc_list = []
    if with_swing and blocs:
        for code in sorted(blocs):
            name, mem = blocs[code]
            idxs = [index[x] for x in mem if x in index]
            if idxs:
                bloc_list.append((code, name, idxs))

    pass_count = 0
    yes_counts = []
    country_delta = [0] * n
    bloc_delta = [0] * len(bloc_list)
    latent = [0.0] * n
    votes = [0] * n

    for _ in range(runs):
        shocks = [gauss(0.0, 1.0) for _ in groups]
        yes = no = ab = vt = 0
        for i in range(n):
            g = grp[i]
            x = mus[i] + sig_own[i] * gauss(0.0, 1.0)
            if g >= 0:
                x += sig_shared[i] * shocks[g]
            latent[i] = x
            v = 1 if x > cy else (-1 if x < cn else 0)
            votes[i] = v
            if v == 1:
                yes += 1
            elif v == -1:
                no += 1
                vt += veto[i]
            else:
                ab += 1
        base = passes(rule, yes, ab, no, m, vt > 0)
        if base:
            pass_count += 1
        yes_counts.append(yes)
        if not with_swing:
            continue
        for i in range(n):
            nv = _vote(latent[i] + step, cy, cn)
            ov = votes[i]
            if nv == ov:
                continue
            y2, n2, a2, v2 = yes, no, ab, vt
            if ov == 1: y2 -= 1
            elif ov == -1: n2 -= 1; v2 -= veto[i]
            else: a2 -= 1
            if nv == 1: y2 += 1
            elif nv == -1: n2 += 1; v2 += veto[i]
            else: a2 += 1
            country_delta[i] += passes(rule, y2, a2, n2, m, v2 > 0) - base
        for b, (_, _, idxs) in enumerate(bloc_list):
            y2, n2, a2, v2 = yes, no, ab, vt
            changed = False
            for i in idxs:
                nv = _vote(latent[i] + step, cy, cn)
                ov = votes[i]
                if nv == ov:
                    continue
                changed = True
                if ov == 1: y2 -= 1
                elif ov == -1: n2 -= 1; v2 -= veto[i]
                else: a2 -= 1
                if nv == 1: y2 += 1
                elif nv == -1: n2 += 1; v2 += veto[i]
                else: a2 += 1
            if changed:
                bloc_delta[b] += passes(rule, y2, a2, n2, m, v2 > 0) - base

    p = pass_count / runs
    ys = sorted(yes_counts)
    hist: dict[int, int] = {}
    for y in yes_counts:
        hist[y] = hist.get(y, 0) + 1
    res = SimResult(
        p_pass=p, mc_se=math.sqrt(p * (1 - p) / runs), runs=runs, seed=seed,
        yes_mean=sum(yes_counts) / runs,
        yes_lo=ys[int(math.floor(0.05 * (runs - 1)))], yes_hi=ys[int(math.ceil(0.95 * (runs - 1)))],
        yes_hist=dict(sorted(hist.items())),
    )
    if with_swing:
        rows = []
        for i, d in enumerate(ds):
            dp = country_delta[i] / runs
            mov = d.sigma / params.sigma_unknown
            rows.append(SwingRow("country", d.iso3, d.name, dp, mov, dp * mov))
        for b, (code, name, idxs) in enumerate(bloc_list):
            dp = bloc_delta[b] / runs
            mov = sum(ds[i].sigma for i in idxs) / (len(idxs) * params.sigma_unknown)
            rows.append(SwingRow("bloc", code, name, dp, mov, dp * mov, tuple(ds[i].iso3 for i in idxs)))
        res.swing = rank(rows)
    return res


def rank(rows: list[SwingRow]) -> list[SwingRow]:
    """Ties break by score (descending), then key (ISO-3 or bloc code) ascending (D-012)."""
    return sorted(rows, key=lambda r: (-round(r.score, 12), r.key))


def exact_p_pass(dists: list[CountryDist], rule: VotingRule, members: int | None = None) -> float:
    """Exact P(pass) assuming independent countries (rho ignored). Used to check the simulation."""
    m = members if members is not None else len(dists)
    states: dict[tuple, float] = {(0, 0, 0, 0): 1.0}
    for d in sorted(dists, key=lambda x: x.iso3):
        is_veto = 1 if d.iso3.upper() in rule.veto else 0
        nxt: dict[tuple, float] = {}
        for (y, a, no, v), pr in states.items():
            for key, q in (((y + 1, a, no, v), d.p_yes), ((y, a + 1, no, v), d.p_abstain),
                           ((y, a, no + 1, min(1, v + is_veto)), d.p_no)):
                if q > 0:
                    nxt[key] = nxt.get(key, 0.0) + pr * q
        states = nxt
    return sum(pr for (y, a, no, v), pr in states.items() if passes(rule, y, a, no, m, v > 0))


def inputs_hash(payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
