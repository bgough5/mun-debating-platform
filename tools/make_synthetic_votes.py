"""Writes tests/fixtures/synthetic_un_votes.csv: SYNTHETIC General Assembly-style votes for tests and demo.

Not real votes. Real countries' codes are used only so the file joins to the
country table; their behaviour is invented from a known model:
    latent = base(country) + affinity(country, tag) + regional shock + noise
    yes if latent > 0.4, no if latent < -0.4, else abstain
so a backtest can show the method recovers a signal that is known to be there.
Run:  python tools/make_synthetic_votes.py
"""
from __future__ import annotations

import csv
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "fixtures" / "synthetic_un_votes.csv"
SUBJECTS = {
    "curb_fossil": "FOSSIL FUELS--EMISSIONS", "binding": "CONVENTION--OBLIGATIONS", "human_right": "HUMAN RIGHTS--RIGHT TO ENVIRONMENT",
    "adapt_finance": "ADAPTATION--FINANCING", "cost_wealthy": "DEVELOPED COUNTRIES--CONTRIBUTIONS",
    "tech_transfer": "TECHNOLOGY TRANSFER", "ecosystems": "FORESTS--BIODIVERSITY", "agriculture": "AGRICULTURE--FOOD SECURITY",
}


def main(seed: int = 2026, n_countries: int = 70, n_resolutions: int = 120) -> None:
    rng = random.Random(seed)
    countries = []
    with open(ROOT / "app/db/seed/countries.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["un_member"] == "1":
                countries.append((r["iso3"], r["region"]))
    rng.shuffle(countries)
    countries = sorted(countries[:n_countries])
    tags = list(SUBJECTS)
    base = {c: rng.gauss(0.6, 0.6) for c, _ in countries}
    aff = {(c, t): rng.gauss(0, 0.9) for c, _ in countries for t in tags}
    region_aff = {(g, t): rng.gauss(0, 0.5) for g in {g for _, g in countries} for t in tags}
    rows = []
    for i in range(n_resolutions):
        k = 1 + (rng.random() < 0.4)
        rtags = rng.sample(tags, k)
        year = 2010 + i * 15 // n_resolutions
        day = f"{year}-{1 + rng.randrange(12):02d}-{1 + rng.randrange(28):02d}"
        shock = {g: rng.gauss(0, 0.3) for g in {g for _, g in countries}}
        for c, g in countries:
            x = base[c] + sum(aff[(c, t)] + region_aff[(g, t)] for t in rtags) / k + shock[g] + rng.gauss(0, 0.5)
            vote = "yes" if x > 0.4 else ("no" if x < -0.4 else "abstain")
            if rng.random() < 0.03:
                vote = "absent"
            rows.append({"resolution_id": f"SYN/{i + 1:03d}", "symbol": f"A/RES/SYN/{i + 1}", "date": day, "session": str(65 + year - 2010),
                         "title": f"Synthetic resolution {i + 1} on " + " and ".join(t.replace('_', ' ') for t in rtags),
                         "subjects": "; ".join(SUBJECTS[t] for t in rtags), "iso3": c, "vote": vote})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} synthetic votes ({n_resolutions} resolutions x {n_countries} countries) to {OUT}")


if __name__ == "__main__":
    main()
