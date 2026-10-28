"""Prediction engine (spec §5). Pure Python, no database access.

Modules:
- priors/archetype.py  the v2 `stanceOf` maths, ported unchanged (parity-tested)
- rules.py             voting rules as data (GA, two-thirds, Security Council, custom)
- model.py             per-country vote distributions from priors and evidence
- simulate.py          seeded Monte Carlo P(pass), swing ranking, exact check
- calibration.py       Brier, log loss, reliability, baselines, bootstrap
- sponsorship.py       sponsor/second resolution, ported from v2
"""
