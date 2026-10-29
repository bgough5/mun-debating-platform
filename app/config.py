"""Local settings for one installation.

Everything here lives under the data folder, which is gitignored: the
coordinator passphrase hash, which dataset is open (real or demo), backup
folder, which modules are switched on, and AI settings. Nothing secret is
ever in the repository (spec §8.5).
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = REPO_ROOT / "data"

MODULES = ("mun", "chair", "debating", "people", "intelligence")

DEFAULTS: dict = {
    "coordinator_hash": "",
    "dataset": "real",
    "backup_dir": "",
    "backup_keep": 14,
    "modules": {m: True for m in MODULES},
    # AI is off unless the school approves it (spec §8.7). The offline fake
    # provider is always available for practice and tests; it calls nothing.
    "ai": {"provider": "fake", "school_approved": False, "api_key_env": ""},
    "max_live_students": 25,
    "stale_evidence_days": 180,
    # Debating is for the classroom (D-074): tournament and carnival tools are hidden unless switched on (D-084).
    "show_tournaments": False,
}


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("SOC_DATA_DIR", DEFAULT_DATA_DIR)))
    values: dict = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def config_path(self) -> Path:
        return self.data_dir / "config.json"

    def load(self) -> "Settings":
        self.data_dir.mkdir(parents=True, exist_ok=True)
        merged = json.loads(json.dumps(DEFAULTS))
        if self.config_path.exists():
            stored = json.loads(self.config_path.read_text(encoding="utf-8"))
            for k, v in stored.items():
                if isinstance(v, dict) and isinstance(merged.get(k), dict):
                    merged[k].update(v)
                else:
                    merged[k] = v
        self.values = merged
        return self

    def save(self) -> None:
        with self._lock:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            tmp = self.config_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.values, indent=2), encoding="utf-8")
            os.replace(tmp, self.config_path)

    def get(self, key: str, default=None):
        return self.values.get(key, default)

    def set(self, key: str, value) -> None:
        self.values[key] = value
        self.save()

    @property
    def dataset(self) -> str:
        return self.values.get("dataset", "real")

    @property
    def is_demo(self) -> bool:
        return self.dataset == "demo"

    def db_path(self, dataset: str | None = None) -> Path:
        return self.data_dir / f"{dataset or self.dataset}.db"

    def module_on(self, name: str) -> bool:
        return bool(self.values.get("modules", {}).get(name, True))

    @property
    def backup_dir(self) -> Path:
        configured = self.values.get("backup_dir") or ""
        return Path(configured) if configured else self.data_dir / "backups"
