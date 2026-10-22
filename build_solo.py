"""
Assembles the standalone offline single-player build from the shared core.

This is the v2 equivalent of the original v1 build step described in
HANDOVER.md section 2 ("string-replace the pack and logo into the engine
... three lines of Python"). It inlines shared/engine.js, shared/flags.js,
and the topic pack into src/engine.v2.html, plus the real South Oakleigh
College logo (assets/soc_logo.png), producing one self-contained HTML file
with no build step, no dependencies, no network, no storage — opens by
double-click, exactly like WhipCount_v1_built.html always has.

Run:  python build_solo.py [--pack climate2026] [--out FILE]
"""

from __future__ import annotations

import argparse
import base64
import re
from pathlib import Path

ROOT = Path(__file__).parent


def _inline_script(html: str, placeholder: str, js_path: Path) -> str:
    tag = f'<script src="{placeholder}"></script>'
    if tag not in html:
        raise ValueError(f"placeholder tag not found in source: {tag!r}")
    return html.replace(tag, f"<script>\n{js_path.read_text(encoding='utf-8')}\n</script>")


def build(pack_id: str = "climate2026", out_path: Path | None = None) -> Path:
    source = (ROOT / "src" / "engine.v2.html").read_text(encoding="utf-8")

    source = _inline_script(source, "PACK_PLACEHOLDER", ROOT / "src" / f"pack_{pack_id}.js")
    source = _inline_script(source, "ENGINE_PLACEHOLDER", ROOT / "shared" / "engine.js")
    source = _inline_script(source, "FLAGS_PLACEHOLDER", ROOT / "shared" / "flags.js")

    logo_b64 = base64.b64encode((ROOT / "assets" / "soc_logo.png").read_bytes()).decode("ascii")
    logo_tag = '<img id="logo" alt="South Oakleigh College">'
    if logo_tag not in source:
        raise ValueError(f"logo <img> tag not found in source: {logo_tag!r}")
    source = source.replace(logo_tag, f'<img id="logo" src="data:image/png;base64,{logo_b64}" alt="South Oakleigh College">')

    out_path = out_path or ROOT / "src" / "WhipCount_v2_solo_built.html"
    out_path.write_text(source, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", default="climate2026", help="pack id, e.g. 'climate2026' for src/pack_climate2026.js")
    parser.add_argument("--out", default=None, help="output path (default: src/WhipCount_v2_solo_built.html)")
    args = parser.parse_args()

    result = build(args.pack, Path(args.out) if args.out else None)
    size_kb = result.stat().st_size / 1024
    print(f"Built {result} ({size_kb:.0f} KB) — self-contained, no server needed, opens by double-click.")
