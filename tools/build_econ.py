"""Build the country dossiers for The Session (D-101, phase 9) from the World Bank's World Development Indicators.

    python tools/build_econ.py

Source: World Bank, World Development Indicators (data.worldbank.org), licensed Creative Commons Attribution 4.0
(as the World Bank's data catalogue lists it, checked 5 Nov 2026). Fetched from api.worldbank.org with Ben's
approval ("Real data, cited", 5 Nov 2026). For each country this keeps the most recent value of a few indicators,
with the year of each, in app/modules/sim/campaign/econ.json. The game shows every figure with its source and year;
it never invents one. Run it again to refresh the figures (the file records when it was built).
"""
from __future__ import annotations

import datetime as dt
import json
import time
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "app" / "modules" / "sim" / "campaign" / "econ.json"
API = "https://api.worldbank.org/v2"
INDICATORS = {
    "gdp": ("NY.GDP.MKTP.CD", "GDP (current US$)"),
    "gdp_pc": ("NY.GDP.PCAP.CD", "GDP per person (current US$)"),
    "population": ("SP.POP.TOTL", "Population"),
    "exports_pct": ("NE.EXP.GNFS.ZS", "Exports of goods and services (% of GDP)"),
    "agri_pct": ("NV.AGR.TOTL.ZS", "Agriculture, forestry and fishing (% of GDP)"),
    "aid": ("DT.ODA.ODAT.CD", "Net official development assistance received (current US$)"),
    "x_fuel": ("TX.VAL.FUEL.ZS.UN", "Fuel exports (% of merchandise exports)"),
    "x_food": ("TX.VAL.FOOD.ZS.UN", "Food exports (% of merchandise exports)"),
    "x_manuf": ("TX.VAL.MANF.ZS.UN", "Manufactures exports (% of merchandise exports)"),
    "x_metal": ("TX.VAL.MMTL.ZS.UN", "Ores and metals exports (% of merchandise exports)"),
    "x_agri": ("TX.VAL.AGRI.ZS.UN", "Agricultural raw materials exports (% of merchandise exports)"),
}


def get(url: str):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 + attempt * 3)


def main() -> None:
    countries = {}
    meta = get(f"{API}/country?format=json&per_page=400")[1]
    for c in meta:
        if c.get("region", {}).get("value") == "Aggregates" or not c.get("id") or len(c["id"]) != 3:
            continue
        countries[c["id"]] = {"name": c["name"], "income": (c.get("incomeLevel") or {}).get("value") or None}
    for key, (code, _label) in INDICATORS.items():
        rows = get(f"{API}/country/all/indicator/{code}?format=json&mrnev=1&per_page=20000")
        for r in (rows[1] if len(rows) > 1 and rows[1] else []):
            iso = r.get("countryiso3code")
            if iso in countries and r.get("value") is not None:
                countries[iso][key] = [round(float(r["value"]), 2), int(r["date"])]
        print(f"{code}: {sum(1 for c in countries.values() if key in c)} countries", flush=True)
    out = {"source": "World Bank, World Development Indicators", "url": "https://data.worldbank.org",
           "licence": "Creative Commons Attribution 4.0 (CC BY 4.0)", "built": dt.date.today().isoformat(),
           "indicators": {k: {"code": v[0], "label": v[1]} for k, v in INDICATORS.items()}, "countries": countries}
    OUT.write_text(json.dumps(out, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB, {len(countries)} countries)")


if __name__ == "__main__":
    main()
