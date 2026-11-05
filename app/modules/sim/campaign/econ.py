"""Country dossiers for The Session (D-101, phase 9): real figures from the World Bank's World Development Indicators
(CC BY 4.0), built by tools/build_econ.py into econ.json. Every figure is shown with its year and source; a country
with no figure says so. From the figures come what a delegation wants in a deal and what your own country can afford
to offer: these are the game's rules of thumb, not statements about any government's intentions."""
from __future__ import annotations

import json
import random
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).with_name("econ.json")
SOURCE = "World Bank, World Development Indicators (CC BY 4.0)"
EXPORTS = {"x_fuel": "fuel", "x_food": "food", "x_manuf": "manufactured goods", "x_metal": "ores and metals",
           "x_agri": "farm raw materials"}


MAX_AGE = 15     # years: an older figure is left out rather than shown as if it were current


@lru_cache(maxsize=1)
def data() -> dict:
    d = json.loads(DATA.read_text(encoding="utf-8"))
    oldest = int(d.get("built", "2026")[:4]) - MAX_AGE
    for c in d["countries"].values():
        for k in [k for k, v in c.items() if isinstance(v, list) and v[1] < oldest]:
            del c[k]
    return d


def _c(iso: str) -> dict:
    return data()["countries"].get(iso, {})


def money(v: float) -> str:
    a = abs(v)
    if a >= 1e12:
        return f"US${v / 1e12:.1f} trillion"
    if a >= 1e9:
        return f"US${v / 1e9:.1f} billion" if a < 1e10 else f"US${v / 1e9:,.0f} billion"
    if a >= 1e6:
        return f"US${v / 1e6:,.0f} million"
    return f"US${v:,.0f}"


def people(v: float) -> str:
    if v >= 1e9:
        return f"{v / 1e9:.2f} billion"
    if v >= 1e6:
        return f"{v / 1e6:.1f} million"
    return f"{v:,.0f}"


def _recent(x, years: int = 10) -> bool:
    built = int(data().get("built", "2026")[:4])
    return bool(x) and x[1] >= built - years


def main_export(iso: str):
    c = _c(iso)
    best = max((k for k in EXPORTS if k in c), key=lambda k: c[k][0], default=None)
    return (EXPORTS[best], c[best][0], c[best][1]) if best else None


def profile(iso: str) -> dict:
    """The dossier as the page shows it: label, value and year for each figure, and the source."""
    c = _c(iso)
    rows = []

    def row(label, key, fmt):
        if key in c:
            rows.append({"label": label, "value": fmt(c[key][0]), "year": c[key][1]})
    row("Economy (GDP)", "gdp", money)
    row("GDP per person", "gdp_pc", money)
    row("Population", "population", people)
    if c.get("income"):
        rows.append({"label": "Income group", "value": c["income"], "year": None})
    row("Exports", "exports_pct", lambda v: f"{v:.0f}% of GDP")
    m = main_export(iso)
    if m:
        rows.append({"label": "Main goods exports", "value": f"{m[0]} ({m[1]:.0f}% of goods exports)", "year": m[2]})
    row("Farming, forestry, fishing", "agri_pct", lambda v: f"{v:.0f}% of GDP")
    aid = c.get("aid")
    if aid and _recent(aid) and aid[0] > 0:
        rows.append({"label": "Development aid received", "value": money(aid[0]), "year": aid[1]})
    elif c:
        rows.append({"label": "Development aid received", "value": "none recorded in the last ten years", "year": None})
    return {"rows": rows, "source": SOURCE if rows else None, "url": data().get("url"), "known": bool(rows)}


def traits(iso: str) -> dict:
    c = _c(iso)
    gdp = (c.get("gdp") or [0])[0]
    m = main_export(iso)
    aid = c.get("aid")
    return {"size": 4 if gdp >= 3e12 else 3 if gdp >= 5e11 else 2 if gdp >= 5e10 else 1,
            "rich": c.get("income") == "High income", "upper": c.get("income") == "Upper middle income",
            "low": c.get("income") in ("Low income", "Lower middle income"),
            "aid": bool(aid and _recent(aid) and aid[0] > 0),
            "exporter": (c.get("exports_pct") or [0])[0] >= 35 or bool(m and m[0] in ("fuel", "ores and metals")),
            "main": m[0] if m else None, "known": bool(c)}


def asks(iso: str, seed: int) -> list[str]:
    """What a delegation is after in a deal, read from its figures: development money if it receives aid or has a low
    income, market access if trade matters to it, sometimes support for a candidacy, and always its favourite clause."""
    t = traits(iso)
    out = []
    if t["aid"] or t["low"]:
        out.append("funding")
    if t["exporter"] or t["main"] in ("food", "fuel", "ores and metals", "farm raw materials"):
        out.append("trade")
    if random.Random(f"{seed}:{iso}:candidacy").random() < 0.3:
        out.append("candidacy")
    out.append("clause")
    return out


def budget(iso: str) -> int:
    """How many funding pledges your treasury can make in a session: bigger and richer economies can make more."""
    t = traits(iso)
    return max(1, t["size"] + (2 if t["rich"] else 1 if t["upper"] else 0))
