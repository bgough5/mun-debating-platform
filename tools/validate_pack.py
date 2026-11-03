"""Check a Model UN scenario pack before it goes into app/db/seed/packs/ (D-097).

    python tools/validate_pack.py path/to/my_pack.json [more.json ...]
    python tools/validate_pack.py --all          # every pack already installed

Prints each problem in plain words and exits 1 if any pack has one. A pack that passes here also loads in the app
(tests/api/test_packs.py installs every pack in the folder). The rules are in docs/pack-authoring.md.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.modules.mun.packfile import PACK_DIR, validate  # noqa: E402


def check(path: Path) -> list[str]:
    try:
        pack = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return [f"Not readable JSON: {e}"]
    if path.name.startswith("_"):
        return ["Files starting with _ are templates: copy it to <code>.json and fill it in."]
    if "REPLACE" in json.dumps(pack):
        return ["The pack still contains REPLACE placeholders from the template."]
    return validate(pack, path.stem)


def main(args: list[str]) -> int:
    paths = sorted(p for p in PACK_DIR.glob("*.json") if not p.name.startswith("_")) if args == ["--all"] else [Path(a) for a in args]
    if not paths:
        print(__doc__)
        return 2
    bad = 0
    for p in paths:
        problems = check(p)
        if problems:
            bad += 1
            print(f"{p.name}: {len(problems)} problem(s)")
            for line in problems:
                print(f"  - {line}")
        else:
            print(f"{p.name}: OK")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
