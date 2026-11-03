"""The world map in the board-game look (D-090): real country shapes (Natural Earth, public domain; built by
tools/build_worldmap.py) on a deep-sea table, with a token pinned to each committee country.

What a map shows is decided by the page:
- "vote"   — the whip count: predictions, then the real vote (sim.service.whip_map);
- "region" — the five UN regional groups as board territories;
- a bloc code (EU, NATO, AU, ...) — that bloc's members highlighted.
The five permanent members of the Security Council get a star on their token. Countries too small to draw at this
scale (Monaco, Tuvalu, ...) are a dot at their real position, so every country is on the board.
"""
from __future__ import annotations

import functools
import json
import math
from pathlib import Path

from app.db import rows
from app.modules.mun.tilemap import LATLON

DATA = Path(__file__).resolve().parent / "worldmap.json"
TOKEN_W, TOKEN_H = 44.0, 26.0          # a country token, in map units (the map is 1000 wide)
REGIONS = {"AFR": "African Group", "APG": "Asia-Pacific Group", "EEG": "Eastern European Group",
           "GRULAC": "Latin American and Caribbean Group", "WEOG": "Western European and Others Group"}


@functools.lru_cache(maxsize=1)
def data() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def _project(lon: float, lat: float) -> tuple[float, float]:
    """The same Natural Earth projection the map was built with, for the dots of very small countries."""
    def raw(lo, la):
        l, p = math.radians(lo), math.radians(la)
        p2 = p * p
        p4 = p2 * p2
        x = l * (0.8707 - 0.131979 * p2 + p4 * (-0.013791 + p4 * (0.003971 * p2 - 0.001529 * p4)))
        y = p * (1.007226 + p2 * (0.015085 + p4 * (-0.044475 + 0.028874 * p2 - 0.005916 * p4)))
        return x, y
    x_max = raw(180, 0)[0]
    scale = 1000 / (2 * x_max)
    y_top = raw(0, 84)[1]
    x, y = raw(lon, lat)
    return (x + x_max) * scale, (y_top - y) * scale


def anchor(iso3: str) -> tuple[float, float] | None:
    c = data()["countries"].get(iso3)
    if c:
        return c["cx"], c["cy"]
    if iso3 in LATLON:
        lat, lon = LATLON[iso3]
        return _project(lon, lat)
    return None


def place_tokens(codes: list[str], width: float, height: float, tw: float = TOKEN_W, th: float = TOKEN_H) -> dict[str, dict]:
    """Token positions, cached: they depend only on which countries are in the room (D-090: the live room rebuilds
    the map on every change, and this keeps that cheap). `tw` and `th`: the token's size (the board's are larger)."""
    return {k: dict(v) for k, v in _placed(tuple(sorted(codes)), width, height, tw, th).items()}


@functools.lru_cache(maxsize=64)
def _placed(codes: tuple, width: float, height: float, tw: float = TOKEN_W, th: float = TOKEN_H) -> dict[str, dict]:
    """Token positions: each starts on its country and is nudged apart from overlapping tokens (a few hundred
    rounds of gentle pushing). A token that moved far gets a leader line back to its country."""
    pts = {c: list(anchor(c)) for c in codes if anchor(c)}
    home = {c: tuple(p) for c, p in pts.items()}
    keys = list(pts)
    for rnd in range(500):
        settle = rnd >= 300                                   # the last rounds only push apart, never pull home
        moved = False
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                ax, ay = pts[a]
                bx, by = pts[b]
                dx, dy = bx - ax, by - ay
                ox, oy = tw + 4 - abs(dx), th + 4 - abs(dy)
                if ox > 0 and oy > 0:
                    moved = True
                    if ox / tw < oy / th:             # push apart along the cheaper axis
                        s = (ox / 2 + 0.5) * (1 if dx >= 0 else -1)
                        pts[a][0] -= s
                        pts[b][0] += s
                    else:
                        s = (oy / 2 + 0.5) * (1 if dy >= 0 else -1)
                        pts[a][1] -= s
                        pts[b][1] += s
        for c in keys:                                        # a gentle pull home, and stay on the board
            if not settle:
                pts[c][0] += (home[c][0] - pts[c][0]) * 0.02
                pts[c][1] += (home[c][1] - pts[c][1]) * 0.02
            pts[c][0] = min(max(pts[c][0], tw / 2 + 2), width - tw / 2 - 2)
            pts[c][1] = min(max(pts[c][1], th / 2 + 2), height - th / 2 - 2)
        if not moved and settle:
            break
    out = {}
    for c in keys:
        x, y = pts[c]
        hx, hy = home[c]
        out[c] = {"x": round(x, 1), "y": round(y, 1), "hx": round(hx, 1), "hy": round(hy, 1),
                  "leader": math.hypot(x - hx, y - hy) > 10}
    return out


def groupings(conn) -> list[dict]:
    """Every grouping a map can be coloured by (real alignments, D-090): the negotiating and political blocs the
    prediction model knows (EU, Arab Group, AOSIS, LDC), and alliances kept for the map only (NATO, AU, ASEAN, G20,
    BRICS). The UN regional groups are the "region" view. Each says whether its membership has been checked."""
    out = []
    bl = rows(conn, "SELECT id, code, name, kind, verified, source, notes FROM bloc WHERE deleted_at IS NULL AND kind != 'regional_group' ORDER BY name")
    bm = rows(conn, "SELECT bloc_id, iso3 FROM bloc_member WHERE deleted_at IS NULL")
    for b in bl:
        out.append({**b, "kind": b["kind"].replace("_", " "), "members": {m["iso3"] for m in bm if m["bloc_id"] == b["id"]}})
    al = rows(conn, "SELECT id, code, name, kind, verified, source, notes FROM alignment WHERE deleted_at IS NULL ORDER BY name")
    am = rows(conn, "SELECT alignment_id, iso3 FROM alignment_member WHERE deleted_at IS NULL")
    for a in al:
        out.append({**a, "members": {m["iso3"] for m in am if m["alignment_id"] == a["id"]}})
    return sorted(out, key=lambda g: g["name"])


def board(conn, codes: list[str], mode: str = "region", values: dict | None = None, labels: dict | None = None,
          highlight: set | None = None, token: tuple = (TOKEN_W, TOKEN_H)) -> dict:
    """Everything a map template needs. `values`: iso3 -> a class for the fill (vote modes); `labels`: iso3 -> the
    second line on a token; `highlight`: countries to light up (bloc mode)."""
    d = data()
    w, h = d["width"], d["height"]
    countries = rows(conn, "SELECT iso3, name, region, p5 FROM country WHERE deleted_at IS NULL")
    info = {c["iso3"]: c for c in countries}
    inside = set(codes)
    land = []
    for iso3, c in d["countries"].items():
        cls = "wm-land"
        if mode == "region":
            reg = (info.get(iso3) or {}).get("region")
            if reg in REGIONS:
                cls += f" reg-{reg.lower()}"
        elif mode == "vote" and values and iso3 in values:
            cls += f" wm-{values[iso3]}"
        elif highlight is not None and iso3 in highlight:
            cls += " wm-member"
        if iso3 in inside:
            cls += " wm-in"
        land.append({"iso3": iso3, "d": c["d"], "cls": cls, "name": (info.get(iso3) or {}).get("name") or c["name"]})
    dots = []
    for iso3 in info:
        if iso3 not in d["countries"] and anchor(iso3):
            x, y = anchor(iso3)
            cls = "wm-dot"
            if mode == "region" and info[iso3]["region"] in REGIONS:
                cls += f" reg-{info[iso3]['region'].lower()}"
            elif mode == "vote" and values and iso3 in values:
                cls += f" wm-{values[iso3]}"
            elif highlight is not None and iso3 in highlight:
                cls += " wm-member"
            dots.append({"iso3": iso3, "x": round(x, 1), "y": round(y, 1), "cls": cls, "name": info[iso3]["name"]})
    tokens = []
    for iso3, p in place_tokens(sorted(inside), w, h, *token).items():
        c = info.get(iso3, {"name": iso3, "p5": 0, "region": ""})
        tokens.append({"iso3": iso3, "name": c["name"], "p5": bool(c["p5"]), "region": c["region"] or "", **p, "line": (labels or {}).get(iso3, ""),
                       "cls": f"wm-{values[iso3]}" if values and iso3 in values else ("wm-member" if highlight and iso3 in highlight else "")})
    return {"width": w, "height": h, "land": land, "dots": dots, "tokens": tokens, "mode": mode,
            "token_w": token[0], "token_h": token[1], "regions": REGIONS}
