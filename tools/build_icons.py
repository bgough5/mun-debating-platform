"""Build app/static/icons/sprite.svg from lucide-static (ISC) for the concepts in app/web/icons.py.

  python tools/build_icons.py path/to/lucide-static/package

Download lucide-static from npm (`npm pack lucide-static` or the registry tarball), check its
licence is still ISC, extract it, and point this script at the extracted `package` folder.
Only the icons the platform uses are copied; nothing is fetched at runtime.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "app" / "static" / "icons"


def main(pkg: Path) -> None:
    from app.web.icons import CONCEPTS
    meta = json.loads((pkg / "package.json").read_text(encoding="utf-8"))
    if meta.get("license") != "ISC":
        raise SystemExit(f"lucide-static licence is {meta.get('license')!r}, not ISC: check it before vendoring")
    symbols = []
    for concept, name in sorted(CONCEPTS.items()):
        svg = (pkg / "icons" / f"{name}.svg").read_text(encoding="utf-8")
        inner = re.search(r"<svg[^>]*>(.*)</svg>", svg, re.S).group(1)
        inner = re.sub(r"\s+", " ", inner).strip()
        symbols.append(f'<symbol id="i-{concept}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
                       f'stroke-linecap="round" stroke-linejoin="round"><!-- lucide:{name} -->{inner}</symbol>')
    OUT.mkdir(parents=True, exist_ok=True)
    head = f'<!-- Lucide icons (lucide-static {meta["version"]}, ISC licence: LICENSE-lucide.txt). Built by tools/build_icons.py. -->'
    (OUT / "sprite.svg").write_text(head + '\n<svg xmlns="http://www.w3.org/2000/svg">\n' + "\n".join(symbols) + "\n</svg>\n",
                                    encoding="utf-8")
    shutil.copyfile(pkg / "LICENSE", OUT / "LICENSE-lucide.txt")
    print(f"{len(symbols)} icons from lucide-static {meta['version']} -> {OUT / 'sprite.svg'}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
