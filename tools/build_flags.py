"""Build every country's flag for the platform (D-093) from the flag-icons set.

    python -I tools/build_flags.py path/to/flag-icons-4x3-folder

Source: flag-icons 7.2.3 by Panayiotis Lipiridis and contributors (MIT licence, github.com/lipis/flag-icons), the
4x3 SVGs, downloaded with Ben's approval on 2 Nov 2026. The folder holds `<iso2>.svg` files and `_iso.json` (iso3 to
iso2, from the Natural Earth data behind the world map).

The flags are inline SVG, so they must pass the app's flag filter (`app.web.safety.safe_svg`, which allows only plain
shapes). This tool rewrites each file into that subset without changing what the flag looks like:
  - `<use>` references are replaced with copies of what they point to;
  - gradients are replaced with their first colour; `style="fill:..."` becomes attributes;
  - ids are prefixed with the country, so many flags on one page never share a clip-path id;
  - numbers outside paths and transforms are rounded to 0.1 (the flags are drawn 640 by 480). Path data is left exactly as it is:
    rounding relative path steps or scale factors adds up, and bent the coats of arms of Bolivia, Mexico, El Salvador and Serbia
    when tried (2 Nov 2026). A few flags with coats of arms are large (Serbia about 370 KB); the tool lists them.
A flag that still doesn't pass is reported and left out. The output is app/db/seed/flags.json (iso3 to SVG), read
by the seed; the licence goes next to it as flags-LICENSE.txt.
"""
from __future__ import annotations

import copy
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.web.safety import safe_svg  # noqa: E402

SVG = "http://www.w3.org/2000/svg"
XLINK = "http://www.w3.org/1999/xlink"
KEEP_TAGS = {"svg", "g", "defs", "clipPath", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon"}
KEEP_ATTRS = {"viewBox", "width", "height", "fill", "fill-rule", "fill-opacity", "stroke", "stroke-width", "stroke-linecap",
              "stroke-linejoin", "stroke-dasharray", "stroke-opacity", "opacity", "d", "points", "x", "y", "x1", "y1", "x2",
              "y2", "cx", "cy", "r", "rx", "ry", "transform", "clip-path", "id"}
NUM = re.compile(r"-?\d*\.\d+(?:e-?\d+)?|-?\d+(?:e-?\d+)?")
MAX_BYTES = 60_000


def local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def rounded(value: str) -> str:
    def r(m):
        v = float(m.group(0))
        return ("%.1f" % v).rstrip("0").rstrip(".") if v != int(v) else str(int(v))
    return NUM.sub(r, value)


def convert(text: str, iso3: str) -> str | None:
    if "<!ENTITY" in text or "<!DOCTYPE" in text:
        return None
    root = ET.fromstring(text)
    ids = {el.get("id"): el for el in root.iter() if el.get("id")}
    # Gradients become their first colour.
    grads = {}
    for el in list(root.iter()):
        if local(el.tag) in ("linearGradient", "radialGradient"):
            stop = next((s for s in el.iter() if local(s.tag) == "stop"), None)
            colour = None
            if stop is not None:
                colour = stop.get("stop-color") or (re.search(r"stop-color:\s*([^;]+)", stop.get("style", "")) or [None, None])[1]
            grads[el.get("id")] = colour or "#888"
    # Inline <use>, repeatedly (a used group may itself contain uses).
    for _ in range(6):
        parent_of = {c: p for p in root.iter() for c in p}
        uses = [el for el in root.iter() if local(el.tag) == "use"]
        if not uses:
            break
        for u in uses:
            ref = (u.get(f"{{{XLINK}}}href") or u.get("href") or "").lstrip("#")
            target = ids.get(ref)
            parent = parent_of.get(u)
            if parent is None:
                continue
            g = ET.Element(f"{{{SVG}}}g")
            tf = " ".join(x for x in (u.get("transform"), f"translate({u.get('x', '0')} {u.get('y', '0')})"
                                      if u.get("x") or u.get("y") else None) if x)
            if tf:
                g.set("transform", tf)
            for k in ("fill", "stroke", "stroke-width", "fill-opacity", "opacity"):
                if u.get(k):
                    g.set(k, u.get(k))
            if target is not None:
                c = copy.deepcopy(target)
                if local(c.tag) == "symbol":
                    c.tag = f"{{{SVG}}}g"
                for el in c.iter():
                    el.attrib.pop("id", None)
                g.append(c)
            idx = list(parent).index(u)
            parent.remove(u)
            parent.insert(idx, g)
    # Clean every element.
    def clean(el):
        for child in list(el):
            if local(child.tag) not in KEEP_TAGS and local(child.tag) != "symbol":
                el.remove(child)
                continue
            if local(child.tag) == "symbol":                 # a symbol only drawn through <use>: already copied
                el.remove(child)
                continue
            clean(child)
        style = el.attrib.pop("style", "")
        for part in style.split(";"):
            if ":" in part:
                k, v = (x.strip() for x in part.split(":", 1))
                if k in KEEP_ATTRS and k not in el.attrib:
                    el.set(k, v)
        for k in list(el.attrib):
            name = local(k) if k.startswith("{") else k
            if k.startswith("{") or name not in KEEP_ATTRS:
                del el.attrib[k]
                continue
            v = el.attrib[k]
            m = re.match(r"url\(#([^)]+)\)", v)
            if m:
                if m.group(1) in grads:
                    el.set(k, grads[m.group(1)])
                    continue
                if k != "clip-path" or m.group(1) not in ids:
                    del el.attrib[k]
                    continue
                el.set(k, f"url(#f{iso3.lower()}-{m.group(1)})")
            elif k == "id":
                el.set(k, f"f{iso3.lower()}-{v}")
            elif k in ("points", "x", "y", "width", "height", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry", "stroke-width"):
                el.set(k, rounded(v))
    clean(root)
    root.attrib.clear()
    root.set("viewBox", "0 0 640 480")
    root.set("width", "24")
    root.set("height", "18")
    root.set("class", "flag")
    ET.register_namespace("", SVG)
    out = ET.tostring(root, encoding="unicode")
    out = out.replace(' xmlns="http://www.w3.org/2000/svg"', "", 1).replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ', 1)
    out = re.sub(r">\s+<", "><", out)
    safe = str(safe_svg(out))
    return safe or None


def main(folder: Path) -> None:
    iso = json.loads((folder / "_iso.json").read_text(encoding="utf-8"))
    flags, failed, big = {}, [], []
    for iso3, iso2 in sorted(iso.items()):
        f = folder / f"{(iso2 or '').lower()}.svg"
        if not iso2 or not f.exists():
            failed.append(f"{iso3}: no file")
            continue
        try:
            svg = convert(f.read_text(encoding="utf-8"), iso3)
        except ET.ParseError as e:
            failed.append(f"{iso3}: {e}")
            continue
        if not svg:
            failed.append(f"{iso3}: did not pass the flag filter")
            continue
        if len(svg) > MAX_BYTES:
            big.append(f"{iso3} ({len(svg) // 1000} KB)")
        flags[iso3] = svg
    out = ROOT / "app" / "db" / "seed" / "flags.json"
    out.write_text(json.dumps(flags, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    lic = folder / "LICENSE.txt"
    if lic.exists():
        (ROOT / "app" / "db" / "seed" / "flags-LICENSE.txt").write_text(
            "Country flags: flag-icons 7.2.3 (github.com/lipis/flag-icons), converted by tools/build_flags.py.\n\n"
            + lic.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"{len(flags)} flags, {out.stat().st_size // 1000} KB; left out: {failed or 'none'}; over {MAX_BYTES // 1000} KB: {big or 'none'}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
