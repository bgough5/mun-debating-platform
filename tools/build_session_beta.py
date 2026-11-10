"""Build a beta zip of The Session for named testers (Ben, 11 Nov 2026).

    python tools/build_session_beta.py --tester "Alex P" --tester "Sam K" [--until 2027-01-31] [--out DIR]

Each tester gets their own zip, watermarked with their name. What goes in: the committed `app` folder (from
`git archive HEAD`, so only what is on the branch), `requirements.txt`, launchers for Windows and Mac, the beta terms
and a short read-me. What stays out: documents, decisions, tests, the old v2 game, project notes and any data. The
Python code ships compiled (Python 3.12 only), and the copy stops starting after `--until`. See app/beta.py.
"""
from __future__ import annotations

import argparse
import compileall
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

START_BAT = r"""@echo off
title The Session (beta)
cd /d "%~dp0"
if exist .venv\Scripts\python.exe goto run
echo.
echo   The Session (beta): first start. Setting up, this needs the internet once and takes a minute...
echo.
py -3.12 -m venv .venv 2>nul || python -m venv .venv || goto nopython
.venv\Scripts\python -c "import sys; sys.exit(sys.version_info[:2] != (3, 12))" || goto wrongpython
.venv\Scripts\python -m pip install --disable-pip-version-check -q -r requirements.txt || goto nopip
:run
echo.
echo   The Session (beta) is starting. Your browser will open in a moment.
echo   Keep this window open while you play; close it to stop.
echo.
start "" cmd /c "timeout /t 4 /nobreak >nul & start http://127.0.0.1:8765/session"
.venv\Scripts\python -m app --host 127.0.0.1 --port 8765 --data-dir data
pause
exit /b
:nopython
echo   Python 3.12 isn't installed. Install it from python.org (tick "Add python.exe to PATH"), then try again.
pause & exit /b 1
:wrongpython
rmdir /s /q .venv
echo   This beta needs Python 3.12 exactly. Install Python 3.12 from python.org, then try again.
pause & exit /b 1
:nopip
rmdir /s /q .venv
echo   Setting up needs the internet once. Check the connection and try again.
pause & exit /b 1
"""

START_COMMAND = """#!/bin/bash
# The Session (beta) for Mac: double-click this file (the first time, right-click it and choose Open).
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "The Session (beta): first start. Setting up, this needs the internet once and takes a minute..."
  PY=$(command -v python3.12 || echo "")
  if [ -z "$PY" ]; then echo "This beta needs Python 3.12. Install it from python.org, then try again."; read -r; exit 1; fi
  "$PY" -m venv .venv && .venv/bin/python -m pip install --disable-pip-version-check -q -r requirements.txt || { rm -rf .venv; echo "Setting up needs the internet once. Try again."; read -r; exit 1; }
fi
(sleep 4; open "http://127.0.0.1:8765/session") &
.venv/bin/python -m app --host 127.0.0.1 --port 8765 --data-dir data
"""

README = """THE SESSION (BETA)
==================

A Model UN campaign for one player. This is a private beta copy for {tester}, made {built}. It runs until {until}.

TO PLAY
1. Install Python 3.12 from https://www.python.org/downloads/ (on Windows, tick "Add python.exe to PATH").
2. Unzip this folder somewhere, for example your Desktop.
3. Windows: double-click "Start The Session.bat".  Mac: right-click "Start The Session.command", choose Open.
   The first start sets itself up (it needs the internet once). Your browser then opens The Session.
4. Keep the black window open while you play. Close it to stop.

The game runs only on this computer (http://127.0.0.1:8765). Nothing is sent anywhere, and your saved games stay in
the "data" folder here.

FEEDBACK
Anything that confused you, felt slow, broke, or that you loved: please tell Ben Gough.

Please read BETA TERMS.txt. This copy is for you only.
"""

TERMS = """BETA TERMS
==========

The Session, including its code, design, writing, artwork and scenarios, is the work of Ben Gough
(Public Speaking and Debating Coordinator, South Oakleigh College). Copyright (c) {year} Ben Gough. All rights reserved.

This beta copy is lent to {tester} for testing and feedback only, until {until}. By using it you agree:
- not to copy, share, publish, upload or pass it on, in whole or in part, to anyone;
- not to take apart, decompile or reuse its code, design, writing or artwork;
- not to use it commercially or in any other organisation;
- to delete it when asked, and in any case after {until}.

Every page shows whose copy this is. No licence is granted beyond the above.

Third-party parts keep their own licences: the fonts (SIL Open Font Licence, in app/static/fonts), the world map
(Natural Earth, public domain), the flags (flag-icons, MIT) and the economic figures (World Bank, CC BY 4.0).
"""


def build(tester: str, until: str, out: Path, keep: Path | None = None) -> Path:
    built = date.today().isoformat()
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp) / "The Session (beta)"
        stage.mkdir()
        raw = subprocess.run(["git", "archive", "--format=tar", "HEAD", "app", "requirements.txt"], cwd=ROOT,
                             check=True, capture_output=True).stdout
        with tarfile.open(fileobj=io.BytesIO(raw)) as t:
            t.extractall(stage, filter="data")
        app = stage / "app"
        ok = compileall.compile_dir(str(app), quiet=1, legacy=True)
        if not ok:
            raise SystemExit("compiling the app failed")
        for py in app.rglob("*.py"):                          # ship compiled code only
            py.unlink()
        for cache in app.rglob("__pycache__"):
            shutil.rmtree(cache, ignore_errors=True)
        (stage / "beta.json").write_text(json.dumps({"tester": tester, "until": until, "built": built}), encoding="utf-8")
        (stage / "Start The Session.bat").write_text(START_BAT.replace("\n", "\r\n"), encoding="utf-8")
        (stage / "Start The Session.command").write_text(START_COMMAND, encoding="utf-8", newline="\n")
        (stage / "READ ME.txt").write_text(README.format(tester=tester, built=built, until=until).replace("\n", "\r\n"), encoding="utf-8")
        (stage / "BETA TERMS.txt").write_text(TERMS.format(tester=tester, until=until, year=date.today().year).replace("\n", "\r\n"), encoding="utf-8")
        out.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^A-Za-z0-9]+", "-", tester).strip("-") or "tester"
        zpath = out / f"The-Session-beta-{slug}-{built}.zip"
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(stage.rglob("*")):
                if f.is_file():
                    info = zipfile.ZipInfo.from_file(f, f.relative_to(stage.parent).as_posix())
                    if f.name.endswith(".command"):
                        info.external_attr = 0o100755 << 16     # executable on a Mac
                    info.compress_type = zipfile.ZIP_DEFLATED
                    z.writestr(info, f.read_bytes())
        if keep:                                               # an unzipped copy (Ben's own, on his Desktop)
            if keep.exists():
                for child in keep.iterdir():
                    if child.name not in (".venv", "data"):     # keep its set-up and saved games across rebuilds
                        shutil.rmtree(child) if child.is_dir() else child.unlink()
            shutil.copytree(stage, keep, dirs_exist_ok=True)
        return zpath


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit("Build with Python 3.12: the compiled code only runs on the version that built it.")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tester", action="append", required=True)
    ap.add_argument("--until", default=(date.today() + timedelta(days=60)).isoformat())
    ap.add_argument("--out", default=str(ROOT / "dist"))
    ap.add_argument("--keep", default=None, help="also leave an unzipped copy here (for the first --tester)")
    a = ap.parse_args()
    date.fromisoformat(a.until)
    for i, t in enumerate(a.tester):
        z = build(t, a.until, Path(a.out), Path(a.keep) if (a.keep and i == 0) else None)
        print("built", z)


if __name__ == "__main__":
    main()
