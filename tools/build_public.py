"""Build the public copy of this repository (Ben, 11 Nov 2026): no history, no internal documents, no school details.

    python tools/build_public.py OUT_DIR

Exports the committed tree (`git archive HEAD`) into OUT_DIR (keeping OUT_DIR/.git if there is one), leaves out the
internal files below, replaces the school's name, crest and logo with neutral ones, and prints any line that still
looks school-specific so it can be checked by hand before publishing. The private repository is never changed.
"""
from __future__ import annotations

import io
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXCLUDE = [
    "CLAUDE.md", "HANDOVER.md", "build_solo.py", "launch_platform.ps1", "assets/soc_launcher.ico",
    "docs/decisions.md", "docs/phase-reports.md", "docs/audit.md", "docs/privacy-summary.md", "docs/pilot-checklist.md",
    "docs/walkthrough.md", "docs/walkthrough-log.csv", "docs/reviews", "docs/screens",
    "tools/build_session_beta.py", "tools/install_desktop_shortcut.ps1", "tools/build_public.py",
]

# order matters: the longest, most specific phrases first
REPLACE = [
    (r"Public Speaking and Debating Coordinator,\s*South Oakleigh College", "the author"),
    (r", drawn from a colleague's photo with his consent: [^.]*\.", ": an original, stylised character."),
    (r" The photo is not kept anywhere in the project\.", ""),
    (r"South Oakleigh College Model United Nations", "Model United Nations"),
    (r"SOUTH OAKLEIGH COLLEGE MUN", "MODEL UN"),
    (r"South Oakleigh Debating (&amp;|&) (Model UN|MUN)", r"Debating \1 \2"),
    (r"SOC Debating (&amp;|&) MUN", r"Debating \1 MUN"),
    (r"South Oakleigh College design system", "the platform's design system"),
    (r"South Oakleigh College look", "the platform's look"),
    (r"South Oakleigh restyle", "restyle"),
    (r"at South Oakleigh College", "at your school"),
    (r"South Oakleigh College's four houses, with the College's house colours \(the College design system\)", "four demo houses, in the platform's house colours"),
    (r"South Oakleigh College", "Your School"),
    (r"South Oakleigh\s*", ""),
    (r'split\(" — SOC"\)', 'split(" — Debating")'),
    (r"\bSOC's\b", "the school's"),
    (r"\bSOC\b", "school"),
    (r"Debating Jr BGO", "Debating Juniors"),
    (r"mia@school\.vic\.edu\.au", "mia@example.invalid"),
    (r"soc_crest\.png", "crest.png"),
    (r"soc_logo\.png", "logo.png"),
    (r"soc_launcher\.ico", "launcher.ico"),
]
TEXT = {".py", ".html", ".j2", ".md", ".css", ".js", ".txt", ".ps1", ".bat", ".sql", ".csv", ".toml", ".ini", ".cfg",
        ".json", ".sh", ".command", ".yml", ".yaml", ".svg", ".xml"}
FLAG = re.compile(r"(?i)oakleigh|\bBGO\b|vic\.gov|curric\b|\.wan\b|colleague'?s photo|claude\.ai/artifact")


def _png(size: int = 256) -> bytes:
    """A plain gold emblem (a ring around a globe) as a PNG, written without any imaging library."""
    gold, dark = (201, 162, 39, 255), (122, 92, 14, 255)
    c = (size - 1) / 2
    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            dx, dy = x - c, y - c
            r = (dx * dx + dy * dy) ** 0.5
            px = (0, 0, 0, 0)
            if 0.40 * size <= r <= 0.48 * size:
                px = gold
            elif r <= 0.30 * size:
                on_line = abs(dx) < 2.2 or abs(dy) < 2.2 or abs(r - 0.30 * size) < 2.5
                ell = (dx / (0.15 * size)) ** 2 + (dy / (0.30 * size)) ** 2
                on_line = on_line or abs(ell - 1) < 0.08 or abs(abs(dy) - 0.15 * size) < 2.0
                px = dark if on_line else gold
            row += bytes(px)
        rows.append(bytes(row))
    raw = zlib.compress(b"".join(rows), 9)

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)) + chunk(b"IDAT", raw) + chunk(b"IEND", b"")


EMBLEM64 = __import__("base64").b64encode(_png(128)).decode()


def build(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for child in out.iterdir():                                     # a fresh tree, keeping the public repo's .git
        if child.name != ".git":
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    raw = subprocess.run(["git", "archive", "--format=tar", "HEAD"], cwd=ROOT, check=True, capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(raw)) as t:
        t.extractall(out, filter="data")
    for rel in EXCLUDE:
        p = out / rel
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
    for old, new in (("app/static/soc_crest.png", "app/static/crest.png"), ("app/static/soc_logo.png", "app/static/logo.png"),
                     ("assets/soc_logo.png", "assets/logo.png")):
        if (out / old).exists():
            (out / old).unlink()
        (out / new).write_bytes(_png())
    flagged = []
    for f in sorted(out.rglob("*")):
        if not f.is_file() or f.suffix.lower() not in TEXT or ".git" in f.parts:
            continue
        try:
            s = f.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            continue
        new = s
        for pat, rep in REPLACE:
            new = re.sub(pat, rep, new)
        new = re.sub(r"data:image/png;base64,[A-Za-z0-9+/=]+", lambda m: "data:image/png;base64," + EMBLEM64, new)   # embedded logos
        if new != s:
            f.write_bytes(new.encode("utf-8"))
        for n, line in enumerate(new.splitlines(), 1):
            if FLAG.search(line):
                flagged.append(f"{f.relative_to(out).as_posix()}:{n}: {line.strip()[:160]}")
    print(f"built {out}")
    print(f"{len(flagged)} line(s) to check by hand:")
    for x in flagged:
        print("  " + x)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    build(Path(sys.argv[1]).resolve())
