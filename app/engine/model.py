"""Per-country vote distributions (spec §5.2, decision D-025).

Each source (archetype prior, bloc position, recorded vote, statement, class
intel...) gives a position on the -2..+2 scale and a weight. A country's mean
latent position is the weighted average of its sources:

    mu    = sum(w_i * x_i) / sum(w_i)
    sigma = sigma_min + (sigma_unknown - sigma_min) / (1 + sum(w_i))

More and better evidence pulls the estimate toward what the sources say and
narrows it. With no sources at all the country is *unknown*: mu = 0 and
sigma = sigma_unknown, shown as unknown and never as a confident number.

The vote is yes if latent > c_yes, no if latent < c_no, otherwise abstain,
where latent = mu + sigma * (sqrt(rho) * bloc_shock + sqrt(1 - rho) * noise).
All constants live in `ModelParams` and are stored per model version.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class ModelParams:
    sigma_unknown: float = 1.5
    sigma_min: float = 0.45
    c_yes: float = 0.4
    c_no: float = -0.4
    archetype_weight: float = 1.0
    strength: dict = field(default_factory=lambda: {"weak": 0.5, "moderate": 1.0, "strong": 1.5})
    conditional_factor: float = 0.5
    stale_days: int = 180
    stale_factor: float = 0.5
    history_weight_per_vote: float = 0.25
    history_weight_cap: float = 4.0
    swing_step: float = 1.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ModelParams":
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)


@dataclass(frozen=True)
class Source:
    """One input to a country's position."""
    position: float          # -2 .. +2
    weight: float            # already multiplied by strength, staleness, conditional
    kind: str                # source type code, e.g. 'model_estimate', 'student_intel'
    label: str               # what the UI shows, e.g. "Model estimate (archetype)"
    ref: str = ""            # evidence id or other reference
    stale: bool = False
    note: str = ""


@dataclass(frozen=True)
class CountryInput:
    iso3: str
    name: str
    sources: tuple = ()
    corr_group: str = ""     # bloc code whose members share noise
    rho: float = 0.0         # share of variance that is shared within the group


@dataclass(frozen=True)
class CountryDist:
    iso3: str
    name: str
    mu: float
    sigma: float
    unknown: bool
    p_yes: float
    p_abstain: float
    p_no: float
    corr_group: str
    rho: float
    total_weight: float

    @property
    def modal_vote(self) -> str:
        """Most likely vote. Exact ties go to abstain, then yes (a fixed, cautious rule)."""
        best = max(self.p_yes, self.p_abstain, self.p_no)
        if self.p_abstain == best:
            return "abstain"
        return "yes" if self.p_yes == best else "no"


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def source_weight(base: float, strength: str, params: ModelParams, conditional: bool = False,
                  stale: bool = False) -> float:
    w = base * params.strength.get(strength, 1.0)
    if conditional:
        w *= params.conditional_factor
    if stale:
        w *= params.stale_factor
    return w


def distribution(ci: CountryInput, params: ModelParams) -> CountryDist:
    srcs = [s for s in ci.sources if s.weight > 0]
    total = sum(s.weight for s in srcs)
    if total <= 0:
        mu, sigma, unknown = 0.0, params.sigma_unknown, True
    else:
        mu = sum(s.weight * max(-2.0, min(2.0, s.position)) for s in srcs) / total
        sigma = params.sigma_min + (params.sigma_unknown - params.sigma_min) / (1.0 + total)
        unknown = False
    p_no = norm_cdf((params.c_no - mu) / sigma)
    p_yes = 1.0 - norm_cdf((params.c_yes - mu) / sigma)
    p_abstain = max(0.0, 1.0 - p_yes - p_no)
    return CountryDist(ci.iso3, ci.name, mu, sigma, unknown, p_yes, p_abstain, p_no,
                       ci.corr_group, ci.rho if ci.corr_group else 0.0, total)


def vote_variance(d: CountryDist) -> float:
    """Variance of the vote coded yes=+1, abstain=0, no=-1."""
    mean = d.p_yes - d.p_no
    return d.p_yes + d.p_no - mean * mean


# Sources that are estimates, not evidence: the archetype prior, unsourced notes, invented demo positions and AI
# estimates (an AI is not a source even when it cites one). D-065.
ESTIMATE_KINDS = frozenset({"model_estimate", "unsourced_note", "demo_unverified", "ai_estimate"})
QUALITY_LABEL = {"sourced": "Sourced", "estimate": "Estimate only", "unknown": "Unknown"}


def evidence_quality(ci: CountryInput) -> str:
    """'sourced' if any counted source is real evidence; 'estimate' if all are estimates; 'unknown' if none."""
    kinds = [s.kind for s in ci.sources if s.weight > 0]
    if not kinds:
        return "unknown"
    return "sourced" if any(k not in ESTIMATE_KINDS for k in kinds) else "estimate"


def quality_shares(dists: list[CountryDist], quality: dict[str, str]) -> dict[str, float]:
    """Share of the total vote variance from countries of each evidence quality (sums to 1)."""
    total = sum(vote_variance(d) for d in dists)
    out = {"sourced": 0.0, "estimate": 0.0, "unknown": 0.0}
    if total <= 0:
        return out
    for d in dists:
        out[quality.get(d.iso3, "unknown")] += vote_variance(d) / total
    return out


def unknown_share(dists: list[CountryDist]) -> float:
    """Share of the total vote variance that comes from countries with no evidence."""
    total = sum(vote_variance(d) for d in dists)
    if total <= 0:
        return 0.0
    return sum(vote_variance(d) for d in dists if d.unknown) / total
