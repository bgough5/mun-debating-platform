"""Backups (spec §7.2 nightly copy; C-9 download and restore).

Uses SQLite's online backup API, so a backup is consistent even while the
app is running. A backup file contains the dataset only: the coordinator
passphrase hash and other local settings stay in data/config.json.
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import logging
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from app.db import connect, migrate
from app.errors import UserError
from app.util import now, now_iso

log = logging.getLogger("soc.backup")
DAY_S = 24 * 3600


def backup_to(db_path: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    src = connect(db_path)
    dst = sqlite3.connect(str(dest))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return dest


def stamp() -> str:
    return datetime.fromtimestamp(now(), timezone.utc).strftime("%Y%m%d-%H%M%S")


def nightly_backup(settings, dataset: str | None = None) -> Path:
    ds = dataset or settings.dataset
    folder = settings.backup_dir
    path = backup_to(settings.db_path(ds), folder / f"{ds}-{stamp()}.db")
    keep = int(settings.get("backup_keep", 14))
    old = sorted(folder.glob(f"{ds}-*.db"))
    for p in old[:-keep] if keep > 0 else []:
        p.unlink(missing_ok=True)
    return path


def last_backup_age_s(settings, dataset: str) -> float | None:
    files = sorted(settings.backup_dir.glob(f"{dataset}-*.db"))
    if not files:
        return None
    return now() - files[-1].stat().st_mtime


async def nightly_loop(app, check_every_s: int = 3600):
    """Every hour, make a backup if the newest one is more than a day old, then run the retention purge."""
    while True:
        try:
            s = app.state.settings
            age = last_backup_age_s(s, s.dataset)
            if age is None or age > DAY_S:
                await asyncio.to_thread(nightly_backup, s)
                from app.retention import purge
                report = await asyncio.to_thread(purge, app.state.db)
                if report["purged"] or report["event_log_deleted"] or report["kept_referenced"]:
                    log.info("Retention purge: %s", report)
        except Exception:      # never let a backup failure stop the app
            log.exception("Nightly backup failed")
        await asyncio.sleep(check_every_s)


def make_download(settings, dataset: str) -> bytes:
    """A zip holding a consistent copy of the dataset plus a manifest."""
    with tempfile.TemporaryDirectory() as tmp:
        db = backup_to(settings.db_path(dataset), Path(tmp) / f"{dataset}.db")
        conn = sqlite3.connect(str(db))
        try:
            versions = [r[0] for r in conn.execute("SELECT name FROM schema_migrations ORDER BY version")]
            counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                      for t in ("class", "student", "conference", "resolution", "event_log")}
        finally:
            conn.close()
        manifest = {"app": "soc-platform", "dataset": dataset, "created": stamp(), "migrations": versions,
                    "counts": counts}
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(db, "dataset.db")
            z.writestr("manifest.json", json.dumps(manifest, indent=2))
        return buf.getvalue()


def validate_backup_zip(data: bytes, workdir: Path) -> tuple[Path, dict]:
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise UserError("That file isn't a platform backup (.zip). Choose a file downloaded from Backups.")
    names = set(z.namelist())
    if not {"dataset.db", "manifest.json"} <= names:
        raise UserError("That zip doesn't contain a platform backup.")
    try:
        manifest = json.loads(z.read("manifest.json"))
    except ValueError:
        raise UserError("That zip doesn't contain a platform backup.")
    if not isinstance(manifest, dict):
        raise UserError("That zip doesn't contain a platform backup.")
    if manifest.get("app") != "soc-platform":
        raise UserError("That zip wasn't made by this platform.")
    out = workdir / "restore.db"
    out.write_bytes(z.read("dataset.db"))
    conn = sqlite3.connect(str(out))
    try:
        ok = conn.execute("PRAGMA integrity_check").fetchone()[0]
    except sqlite3.DatabaseError:
        ok = "not a database"
    finally:
        conn.close()
    if ok != "ok":
        raise UserError("The backup file is damaged (integrity check failed). Try an older backup.")
    return out, manifest


def check_backup(data: bytes) -> dict:
    """Validate a backup without touching the open data (call before closing connections)."""
    with tempfile.TemporaryDirectory() as tmp:
        return validate_backup_zip(data, Path(tmp))[1]


def restore(settings, dataset: str, data: bytes) -> dict:
    """Replace a dataset with a backup. The current file is kept as a backup first."""
    with tempfile.TemporaryDirectory() as tmp:
        restored, manifest = validate_backup_zip(data, Path(tmp))
        target = settings.db_path(dataset)
        if target.exists():
            backup_to(target, settings.backup_dir / f"{dataset}-before-restore-{stamp()}.db")
        staged = target.with_name(target.name + ".restoring")
        shutil.copyfile(restored, staged)
        for suffix in ("-wal", "-shm"):
            Path(str(target) + suffix).unlink(missing_ok=True)
        os.replace(staged, target)
    conn = connect(target)
    try:
        migrate(conn)     # bring an older backup up to the current schema
        # Devices signed in when the backup was made must not come back to life: everyone signs in again.
        conn.execute("UPDATE device_session SET revoked_at = ? WHERE revoked_at IS NULL", (now_iso(),))
        conn.commit()
    finally:
        conn.close()
    from app.web.auth import forget_sessions
    forget_sessions()
    return manifest
