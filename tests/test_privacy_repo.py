"""No real data or secrets in the repository (CLAUDE.md non-negotiable)."""
import re
import subprocess
from pathlib import Path

from tools.privacy_check import problems, tracked

ROOT = Path(__file__).resolve().parents[1]


def test_no_databases_or_data_folder_tracked():
    assert problems(tracked()) == []


def test_guard_blocks_db_and_data():
    assert problems(["data/real.db", "x/y.db", "data/config.json", "app/db/seed/countries.csv"]) == \
        ["data/real.db", "x/y.db", "data/config.json"]


def test_no_secrets_in_tracked_text():
    pat = re.compile(r"(sk-ant-[A-Za-z0-9]|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY|scrypt\$\d+\$)")
    hits = []
    for f in tracked():
        p = ROOT / f
        if p.suffix in (".png", ".gz") or not p.is_file() or p.stat().st_size > 2_000_000:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if pat.search(text):
            hits.append(f)
    assert hits == []
