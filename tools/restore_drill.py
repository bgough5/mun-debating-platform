"""Backup and restore drill (spec Phase 5).

  python tools/restore_drill.py

Runs two separate copies of the platform, each its own process with its own data
folder, standing in for "the laptop" and "a second machine":
  A: first-run setup, then real work through the web pages (class, students,
     staff, a conference with a committee), then "Download backup".
  B: a fresh install: first-run setup, then Admin -> Data -> Restore with A's zip.
Then checks, through B's pages and its database file, that everything from A is
there: every table's row count, the class and its students, and SQLite's
integrity check. Writes test-results/restore-drill.json.

Only fake names are used. A real second machine (Ben's laptop to another
computer) is a manual step in docs/backup-restore.md; this drill can't do it.
"""
from __future__ import annotations

import json
import re
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "test-results" / "restore-drill.json"
PASS_A, PASS_B = "drill passphrase machine a", "drill passphrase machine b"


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Machine:
    def __init__(self, label: str):
        self.label = label
        self.dir = Path(tempfile.mkdtemp(prefix=f"soc-drill-{label}-"))
        self.port = free_port()
        self.log = open(self.dir / "server.log", "w")
        self.proc = subprocess.Popen([sys.executable, "-m", "app", "--data-dir", str(self.dir), "--port", str(self.port),
                                      "--host", "127.0.0.1"], cwd=str(ROOT), stdout=self.log, stderr=subprocess.STDOUT)
        self.http = httpx.Client(base_url=f"http://127.0.0.1:{self.port}", timeout=60)
        for _ in range(150):
            try:
                if self.http.get("/healthz").status_code == 200:
                    return
            except httpx.HTTPError:
                time.sleep(0.2)
        raise RuntimeError(f"{label} did not start; see {self.dir / 'server.log'}")

    def post(self, url, data=None, files=None):
        d = dict(data or {})
        d["csrf"] = self.http.cookies.get("soc_csrf")
        r = self.http.post(url, data=d, files=files, follow_redirects=True)
        if r.status_code >= 400:
            raise RuntimeError(f"{self.label} POST {url} -> {r.status_code}: {r.text[:300]}")
        return r

    def setup(self, passphrase):
        self.post("/setup", {"passphrase": passphrase, "passphrase2": passphrase})

    def db(self) -> Path:
        return self.dir / "real.db"

    def stop(self):
        self.http.close()
        self.proc.terminate()
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.log.close()


def counts(db: Path) -> dict:
    conn = sqlite3.connect(str(db))
    try:
        names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                                            "AND name != 'device_session' ORDER BY name")]
        return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in names}
    finally:
        conn.close()


def integrity(db: Path) -> str:
    conn = sqlite3.connect(str(db))
    try:
        return conn.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        conn.close()


def main() -> dict:
    t0 = time.perf_counter()
    a = Machine("A")
    b = None
    try:
        a.setup(PASS_A)
        a.post("/people/classes", {"name": "Drill 10D", "year": "2026"})
        cid = int(re.search(r"/people/classes/(\d+)", a.http.get("/people").text).group(1))
        a.post(f"/people/classes/{cid}/students", {"names": "Testa\nTestb B\nTestc\nTestd\nTeste"})
        a.post("/people/staff", {"action": "create", "name": "Drill Teacher", "passphrase": "drill staff passphrase"})
        a.post("/mun/conferences", {"name": "Drill conference", "starts_on": "2026-11-01"})
        page = a.http.get("/people").text
        assert "Drill 10D" in page
        r = a.http.get("/admin/data/download")
        assert r.status_code == 200 and r.headers["content-type"] == "application/zip", r.status_code
        zip_bytes = r.content
        before = counts(a.db())
        a.stop()
        t_backup = time.perf_counter() - t0

        b = Machine("B")
        b.setup(PASS_B)
        fresh = counts(b.db())
        t1 = time.perf_counter()
        r = b.post("/admin/data/restore", {"confirm": "yes"}, files={"file": ("backup.zip", zip_bytes, "application/zip")})
        restored_msg = re.search(r"Restored the backup[^<]*", r.text)
        t_restore = time.perf_counter() - t1
        after = counts(b.db())
        people = b.http.get("/people").text
        cls = b.http.get(f"/people/classes/{cid}").text
        kept = sorted(p.name for p in (b.dir / "backups").glob("*")) if (b.dir / "backups").exists() else []
        diffs = {t: (before.get(t), after.get(t)) for t in set(before) | set(after) if before.get(t) != after.get(t)}
        result = {
            "machines": "two separate app processes with separate data folders on one computer (not two machines)",
            "rows_in_backup": sum(before.values()), "tables": len(before),
            "row_count_differences": diffs,
            "class_visible_after_restore": "Drill 10D" in people,
            "students_visible_after_restore": all(n in cls for n in ("Testa", "Testb", "Testc", "Testd", "Teste")),
            "integrity_check": integrity(b.db()),
            "previous_data_kept_as": kept,
            "fresh_install_rows_replaced": sum(fresh.values()),
            "message": restored_msg.group(0) if restored_msg else None,
            "seconds": {"setup_work_and_backup": round(t_backup, 2), "restore": round(t_restore, 2),
                        "total": round(time.perf_counter() - t0, 2)},
            "zip_bytes": len(zip_bytes),
        }
        # The coordinator of B stays B's (passphrase is not in the backup): B's passphrase still signs in.
        b.post("/logout")
        r = b.post("/login", {"who": "coordinator", "passphrase": PASS_B})
        result["machine_b_passphrase_still_works"] = "Sign out" in r.text or "/logout" in r.text
        result["pass"] = (not diffs and result["class_visible_after_restore"] and result["students_visible_after_restore"]
                          and result["integrity_check"] == "ok" and result["machine_b_passphrase_still_works"])
    finally:
        if a.proc.poll() is None:
            a.stop()
        if b is not None and b.proc.poll() is None:
            b.stop()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    res = main()
    print(json.dumps(res, indent=2))
    sys.exit(0 if res["pass"] else 1)
