"""Chaos tests (Phase 6 item 6): kill the server mid-session and restart it.

The real app runs in its own process. While a chair and students are acting concurrently the process is killed
with SIGKILL (no clean shutdown), then restarted on the same data folder. Every action the server acknowledged
before it died must still be there; the database must pass SQLite's integrity check; the chair reconnects to the
same state; a client that reconnects with the last event number it saw receives every change it missed.
"""
from __future__ import annotations

import json
import os
import signal
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest

from app.config import Settings
from app.util import hash_passphrase

ROOT = Path(__file__).resolve().parents[2]
PASS = "chaos test coordinator passphrase"
pytestmark = pytest.mark.slow


def _port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Server:
    def __init__(self, data: Path, port: int):
        self.data, self.port, self.proc = data, port, None
        self.base = f"http://127.0.0.1:{port}"

    def start(self):
        log = open(self.data / f"server-{time.time():.0f}.log", "w")
        self.proc = subprocess.Popen([sys.executable, "-m", "app", "--data-dir", str(self.data), "--port", str(self.port),
                                      "--host", "127.0.0.1"], cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT)
        for _ in range(300):
            try:
                if httpx.get(self.base + "/healthz", timeout=1).status_code == 200:
                    return self
            except httpx.HTTPError:
                time.sleep(0.1)
        raise RuntimeError("server did not start")

    def kill(self):
        self.proc.send_signal(signal.SIGKILL)       # no clean shutdown: as if the laptop lost power
        self.proc.wait(10)

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def _client(base) -> httpx.Client:
    c = httpx.Client(base_url=base, timeout=5)
    c.get("/healthz")
    return c


def _post(c: httpx.Client, url: str, data: dict | None = None) -> httpx.Response:
    d = dict(data or {})
    d["csrf"] = c.cookies.get("soc_csrf")
    return c.post(url, data=d, follow_redirects=False)


@pytest.fixture
def server(tmp_path):
    s = Settings(data_dir=tmp_path).load()
    s.values.update(coordinator_hash=hash_passphrase(PASS), dataset="demo")
    s.save()
    srv = Server(tmp_path, _port()).start()
    yield srv
    srv.stop()


def _db(server) -> sqlite3.Connection:
    conn = sqlite3.connect(str(server.data / "demo.db"))
    conn.row_factory = sqlite3.Row
    return conn


@pytest.mark.skipif(os.name == "nt", reason="SIGKILL semantics; the laptop smoke test covers Windows start-up")
def test_kill_mid_session_loses_no_acknowledged_change(server):
    chair = _client(server.base)
    assert _post(chair, "/login", {"who": "coordinator", "passphrase": PASS}).status_code == 303
    conn = _db(server)
    com, code = conn.execute("SELECT cm.id, c.code FROM committee cm JOIN class c ON c.id = cm.class_id "
                             "WHERE cm.name LIKE 'United Nations General Assembly%'").fetchone()
    dels = [r[0] for r in conn.execute("SELECT id FROM delegation WHERE committee_id = ? ORDER BY id", (com,))]
    members = conn.execute("SELECT dm.student_id, dm.delegation_id FROM delegation_member dm JOIN delegation d ON d.id = dm.delegation_id "
                           "WHERE d.committee_id = ? AND dm.deleted_at IS NULL ORDER BY dm.student_id", (com,)).fetchall()
    conn.close()
    r = _post(chair, f"/chair/committee/{com}/open")
    sid = int(r.headers["location"].rsplit("/", 1)[1])
    para = _db(server).execute("SELECT p.id FROM paragraph p JOIN resolution r ON r.id = p.resolution_id WHERE r.committee_id = ? "
                               "AND p.kind = 'operative' LIMIT 1", (com,)).fetchone()[0]
    assert _post(chair, f"/chair/{sid}/divisions", {"target": f"paragraph:{para}"}).status_code == 303
    did = _db(server).execute("SELECT id FROM division WHERE session_id = ? AND status = 'open'", (sid,)).fetchone()[0]

    students = []
    for st_id, del_id in members[:12]:
        c = _client(server.base)
        _post(c, "/join", {"code": code})
        _post(c, f"/join/{code}/{st_id}")
        students.append((c, del_id))

    acked_speakers: list[int] = []
    acked_votes: dict[int, str] = {}
    lock = threading.Lock()
    stop = threading.Event()

    def chair_loop():
        for d in dels:
            if stop.is_set():
                return
            try:
                if _post(chair, f"/chair/{sid}/speakers", {"delegation_id": d}).status_code == 303:
                    with lock:
                        acked_speakers.append(d)
            except (httpx.HTTPError, OSError):        # the server died mid-request: not acknowledged
                return
            time.sleep(0.02)

    def student_loop(c, del_id, i):
        for k in range(20):
            if stop.is_set():
                return
            vote = ["yes", "no", "abstain"][(i + k) % 3]
            try:
                if _post(c, f"/live/{sid}/vote", {"vote": vote}).status_code == 303:
                    with lock:
                        acked_votes[del_id] = vote
            except (httpx.HTTPError, OSError):
                return
            time.sleep(0.03)

    threads = [threading.Thread(target=chair_loop)] + [threading.Thread(target=student_loop, args=(c, d, i)) for i, (c, d) in enumerate(students)]
    for t in threads:
        t.start()
    deadline = time.time() + 10           # kill mid-burst: once some actions are acknowledged and more are in flight
    while time.time() < deadline:
        with lock:
            if len(acked_speakers) >= 2 and len(acked_votes) >= 3:
                break
        time.sleep(0.01)
    server.kill()
    stop.set()
    for t in threads:
        t.join(10)
    assert acked_speakers and acked_votes, "the burst should have been acknowledged in part before the kill"

    server.start()                       # same data folder: WAL recovery happens on open
    conn = _db(server)
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        queued = {r[0] for r in conn.execute("SELECT delegation_id FROM speakers_list_entry WHERE session_id = ?", (sid,))}
        assert set(acked_speakers) <= queued                      # every acknowledged speaker survived
        votes = {r["delegation_id"]: r["vote"] for r in conn.execute("SELECT * FROM division_vote WHERE division_id = ? AND computed = 0", (did,))}
        # A student may have had a later vote in flight when the server died; that one may or may not have committed,
        # but every delegation whose vote was acknowledged has a vote recorded.
        assert set(acked_votes) <= set(votes)
        seqs = [r[0] for r in conn.execute("SELECT seq FROM event_log ORDER BY seq")]
        assert seqs == sorted(set(seqs))
        last_seq = seqs[-1]
    finally:
        conn.close()

    # The chair reconnects (new browser: sign in again) to the same session and state.
    chair2 = _client(server.base)
    _post(chair2, "/login", {"who": "coordinator", "passphrase": PASS})
    page = chair2.get(f"/chair/{sid}").text
    assert "Close voting and announce" in page                    # the open division is still open
    with _db(server) as conn:
        names = [r[0] for r in conn.execute("SELECT c.name FROM speakers_list_entry e JOIN delegation d ON d.id = e.delegation_id "
                                            "JOIN country c ON c.iso3 = d.iso3 WHERE e.session_id = ? AND e.status = 'waiting' "
                                            "ORDER BY e.position LIMIT 3", (sid,))]
    import html
    assert all(html.escape(n) in page or n in page for n in names)

    # A client that saw everything up to last_seq reconnects after more changes and is sent exactly what it missed.
    for d in dels[-3:]:
        _post(chair2, f"/chair/{sid}/next")
    import asyncio
    import websockets

    async def replay():
        url = server.base.replace("http", "ws") + "/ws"
        cookie = "; ".join(f"{k}={v}" for k, v in chair2.cookies.items())
        async with websockets.connect(url, additional_headers={"Cookie": cookie, "Origin": server.base}) as ws:
            await ws.send(json.dumps({"subscribe": [f"session:{sid}"], "since": last_seq}))
            got = []
            try:
                while True:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
                    if "channels" in msg:
                        got.append(msg["seq"])
            except asyncio.TimeoutError:
                return got
    out: dict = {}
    t = threading.Thread(target=lambda: out.setdefault("got", asyncio.run(replay())))   # own loop: pytest may hold one
    t.start()
    t.join(30)
    got = out.get("got")
    with _db(server) as conn:
        expected = [r[0] for r in conn.execute(
            "SELECT MAX(seq) FROM event_log WHERE channel = ? AND seq > ? GROUP BY action_group ORDER BY MAX(seq)",
            (f"session:{sid}", last_seq))]
    assert expected and got == expected
    print(f"\nchaos: {len(acked_speakers)} speaker adds and {len(acked_votes)} votes acknowledged before SIGKILL, "
          f"all present after restart; {len(got)} missed change groups replayed")


def test_restart_between_lessons_keeps_everything(server):
    """A clean stop and start (closing the black window, starting it again) keeps every change and the open session."""
    chair = _client(server.base)
    _post(chair, "/login", {"who": "coordinator", "passphrase": PASS})
    conn = _db(server)
    com = conn.execute("SELECT id FROM committee WHERE name LIKE 'United Nations General Assembly%'").fetchone()[0]
    conn.close()
    sid = int(_post(chair, f"/chair/committee/{com}/open").headers["location"].rsplit("/", 1)[1])
    _post(chair, f"/chair/{sid}/stage", {"stage": "agenda"})
    _post(chair, f"/chair/{sid}/agenda", {"agenda": "Ocean plastics"})
    before = _db(server).execute("SELECT COUNT(*) FROM event_log").fetchone()[0]
    server.stop()
    server.start()
    with _db(server) as conn:
        assert conn.execute("SELECT COUNT(*) FROM event_log").fetchone()[0] >= before
        s = conn.execute("SELECT stage, agenda, state FROM live_session WHERE id = ?", (sid,)).fetchone()
    assert tuple(s) == ("agenda", "Ocean plastics", "open")
