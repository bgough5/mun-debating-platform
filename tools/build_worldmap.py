"""Build the world map the platform draws (D-090) from Natural Earth country borders.

    python tools/build_worldmap.py path/to/ne_50m_admin_0_countries.geojson

Source: Natural Earth 1:50m Admin 0 – Countries, v5.1.2 (public domain; "Made with Natural Earth",
naturalearthdata.com), downloaded from github.com/nvkelso/natural-earth-vector with Ben's approval on 30 Oct 2026.
The download is not kept in the repo; this script turns it into app/modules/mun/worldmap.json: each country's
outline projected (Natural Earth projection), simplified, and written as an SVG path, with a centre point for its
label. Antarctica is left out. Run it again only to change the detail or the projection.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "app" / "modules" / "mun" / "worldmap.json"
WIDTH = 1000.0
TOLERANCE = 0.55          # simplification, in map units (the map is 1000 wide)
MIN_RING_AREA = 0.6       # drop islands smaller than this, unless they are the country's biggest piece


def project(lon: float, lat: float) -> tuple[float, float]:
    """The Natural Earth projection (Šavrič, Jenny, Patterson, Jenny 2011): a rounded, friendly world shape."""
    l, p = math.radians(lon), math.radians(lat)
    p2 = p * p
    p4 = p2 * p2
    x = l * (0.8707 - 0.131979 * p2 + p4 * (-0.013791 + p4 * (0.003971 * p2 - 0.001529 * p4)))
    y = p * (1.007226 + p2 * (0.015085 + p4 * (-0.044475 + 0.028874 * p2 - 0.005916 * p4)))
    return x, y


X_MAX = project(180, 0)[0]
SCALE = WIDTH / (2 * X_MAX)
Y_TOP = project(0, 84)[1]
Y_BOTTOM = project(0, -58)[1]
HEIGHT = (Y_TOP - Y_BOTTOM) * SCALE


def to_map(lon: float, lat: float) -> tuple[float, float]:
    x, y = project(lon, lat)
    return (x + X_MAX) * SCALE, (Y_TOP - y) * SCALE


def simplify(pts: list, tol: float) -> list:
    """Douglas-Peucker, iterative."""
    if len(pts) < 4:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay = pts[a]
        bx, by = pts[b]
        dx, dy = bx - ax, by - ay
        norm = math.hypot(dx, dy) or 1e-9
        best, idx = 0.0, None
        for i in range(a + 1, b):
            px, py = pts[i]
            d = abs(dy * px - dx * py + bx * ay - by * ax) / norm
            if d > best:
                best, idx = d, i
        if idx is not None and best > tol:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    return [p for p, k in zip(pts, keep) if k]


def simplify_ring(pts: list, tol: float) -> list:
    """A closed ring: split at the point farthest from the start and simplify each half (the ends meet)."""
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) < 4:
        return pts
    x0, y0 = pts[0]
    far = max(range(len(pts)), key=lambda i: (pts[i][0] - x0) ** 2 + (pts[i][1] - y0) ** 2)
    a = simplify(pts[:far + 1], tol)
    b = simplify(pts[far:] + [pts[0]], tol)
    return a[:-1] + b[:-1]


def area(pts: list) -> float:
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))) / 2


def code_of(props: dict) -> str:
    for key in ("ISO_A3", "ADM0_A3", "ISO_A3_EH"):
        v = props.get(key)
        if v and v != "-99":
            return v
    return ""


def main(src: str) -> None:
    data = json.loads(Path(src).read_text(encoding="utf-8"))
    out: dict = {}
    for f in data["features"]:
        p = f["properties"]
        code = code_of(p)
        if not code or code == "ATA" or not f.get("geometry"):
            continue
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        rings = []
        for poly in polys:
            for ring in poly[:1]:                      # outer rings only: lakes are too small to matter here
                pts = simplify_ring([to_map(lon, max(-58, min(84, lat))) for lon, lat in ring], TOLERANCE)
                if len(pts) >= 3:
                    rings.append(pts)
        if not rings:
            continue
        biggest = max(rings, key=area)
        rings = [r for r in rings if r is biggest or area(r) >= MIN_RING_AREA]
        d = "".join("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in r) + "Z" for r in rings)
        lx, ly = p.get("LABEL_X"), p.get("LABEL_Y")
        cx, cy = to_map(lx, ly) if lx is not None and ly is not None else (
            sum(x for x, _ in biggest) / len(biggest), sum(y for _, y in biggest) / len(biggest))
        prev = out.get(code)
        if prev and len(prev["d"]) > len(d):           # a few codes appear twice (e.g. dependencies): keep the larger
            continue
        out[code] = {"name": p.get("NAME_EN") or p.get("NAME"), "d": d, "cx": round(cx, 1), "cy": round(cy, 1),
                     "area": round(sum(area(r) for r in rings), 1)}
    doc = {"source": "Natural Earth 1:50m Admin 0 Countries v5.1.2, public domain (naturalearthdata.com)",
           "projection": "Natural Earth", "width": WIDTH, "height": round(HEIGHT, 1), "countries": out}
    OUT.write_text(json.dumps(doc, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"{len(out)} countries, {OUT.stat().st_size // 1024} KB -> {OUT}")


if __name__ == "__main__":
    main(sys.argv[1])
