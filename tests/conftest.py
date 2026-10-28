"""Shared fixtures. Every test gets its own temporary data folder: fake data only."""
from __future__ import annotations

import html
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.util import hash_passphrase

COORD_PASS = "correct horse battery staple"


def make_settings(tmp_path: Path, dataset: str = "demo") -> Settings:
    s = Settings(data_dir=tmp_path / "data").load()
    s.values["coordinator_hash"] = hash_passphrase(COORD_PASS)
    s.values["dataset"] = dataset
    s.save()
    return s


class Client(TestClient):
    """TestClient that sends the CSRF token on every unsafe request, like the real pages do."""

    def csrf(self) -> str:
        tok = self.cookies.get("soc_csrf")
        if not tok:
            self.get("/healthz")
            tok = self.cookies.get("soc_csrf")
        return tok

    def request(self, *a, **kw):
        # Unescape HTML entities so tests can look for plain English like "didn't".
        r = super().request(*a, **kw)
        if "text/html" in r.headers.get("content-type", ""):
            r._text = html.unescape(r.text)
        return r

    def post(self, url, data=None, files=None, follow_redirects=True, **kw):
        data = dict(data or {})
        data.setdefault("csrf", self.csrf())
        return super().post(url, data=data, files=files, follow_redirects=follow_redirects, **kw)


def new_client(app) -> Client:
    return Client(app, base_url="http://testserver")


@pytest.fixture
def settings(tmp_path):
    return make_settings(tmp_path)


@pytest.fixture
def app(settings):
    from app.main import create_app
    return create_app(settings)


@pytest.fixture
def client(app):
    with new_client(app) as c:
        yield c


def login_coordinator(c: Client) -> Client:
    r = c.post("/login", {"who": "coordinator", "passphrase": COORD_PASS})
    assert r.status_code == 200, r.text[:500]
    return c


def login_staff(c: Client, staff_id: int, passphrase: str) -> Client:
    r = c.post("/login", {"who": str(staff_id), "passphrase": passphrase})
    assert r.status_code == 200, r.text[:500]
    return c


@pytest.fixture
def coord(app):
    with new_client(app) as c:
        yield login_coordinator(c)


def ids(html: str, pattern: str) -> list[int]:
    return [int(x) for x in re.findall(pattern, html)]


def db_rows(app, sql, params=()):
    with app.state.db.read() as conn:
        return [dict(r) for r in conn.execute(sql, params)]


def db_one(app, sql, params=()):
    r = db_rows(app, sql, params)
    return r[0] if r else None


@pytest.fixture(autouse=True)
def _reset_throttles():
    from app.web import auth
    for t in (auth.login_throttle, auth.join_throttle):
        t.fails.clear()
        t.locked_until.clear()
    yield
