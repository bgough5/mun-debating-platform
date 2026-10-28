"""Privacy guard (spec §8.2): refuse to commit database files, anything under data/, or local config.

Used by the git pre-commit hook (.githooks/pre-commit) and by the test suite.
Enable the hook once per clone:  git config core.hooksPath .githooks
"""
from __future__ import annotations

import subprocess
import sys

BLOCKED_SUFFIXES = (".db", ".db-wal", ".db-shm", ".sqlite", ".sqlite3")
BLOCKED_PREFIXES = ("data/",)
BLOCKED_NAMES = ("config.json",)


def problems(paths: list[str]) -> list[str]:
    bad = []
    for p in paths:
        q = p.replace("\\", "/")
        if q.endswith(BLOCKED_SUFFIXES) or q.startswith(BLOCKED_PREFIXES) or q.rsplit("/", 1)[-1] in BLOCKED_NAMES:
            bad.append(p)
    return bad


def staged() -> list[str]:
    out = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"], capture_output=True, text=True)
    return [l for l in out.stdout.splitlines() if l]


def tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True)
    return [l for l in out.stdout.splitlines() if l]


if __name__ == "__main__":
    bad = problems(tracked() if "--all" in sys.argv else staged())
    if bad:
        print("Refusing to commit files that may hold real student data or secrets:")
        for b in bad:
            print("  ", b)
        print("Databases, data/ and config.json stay on the laptop (spec §8.2).")
        sys.exit(1)
