"""Real and demo datasets: one SQLite file each (spec §6, R6).

The demo dataset is seeded from the fake-data generator only. Switching
between datasets is a coordinator action that signs every other device out,
so real data is never open in a demo session or the other way round.
"""
from __future__ import annotations

from app.config import Settings
from app.db import Database, connect, migrate, scalar
from app.db.seed import seed_reference

DATASETS = ("real", "demo")


def prepare(path, dataset: str) -> None:
    conn = connect(path)
    try:
        migrate(conn)
        seed_reference(conn)
        if dataset == "demo" and not scalar(conn, "SELECT COUNT(*) FROM class"):
            from app.fakedata import populate_demo
            populate_demo(conn)
    finally:
        conn.close()


def open_dataset(settings: Settings, dataset: str, hub=None) -> Database:
    if dataset not in DATASETS:
        raise ValueError(f"Unknown dataset {dataset!r}")
    path = settings.db_path(dataset)
    prepare(path, dataset)
    return Database(path, hub)
