"""Phase 2 load test (spec §10): 30 simulated clients for N minutes.

  python tools/loadtest.py --minutes 45

Starts the real app in a separate process (demo data in a temporary folder),
then runs 30 clients on the same machine:
  - 25 students: sign in with their personal codes, open the live page, hold a
    WebSocket, re-fetch their live fragment on every change, add themselves to
    the speakers list now and then, and vote whenever a division opens;
  - 1 chair: performs an action every ~2 s (speakers, timers, motions, divisions);
  - 1 projector and 3 staff observers: WebSocket + fragment re-fetch.

Measured:
  - lost events: every change on the session channel (one per action group in
    the event log) must reach every client, live or by replay after a reconnect;
  - update latency: from the start of the chair's (or student's) action to the
    moment each client has the new fragment (WebSocket notice + HTTP fetch), p50/p95/p99/max;
  - errors, reconnects, server memory.
Results go to test-results/load/summary.json.
"""
from __future__ import annotations

import argparse
import asyncio
import bisect
import json
import os
import platform
import random
import re
import socket
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import websockets

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "test-results" / "load"
PASS = "load test coordinator passphrase"

actions: list[float] = []          # start times of every write action (chair and students)
errors: list[str] = []
transport_retries: list[str] = []   # client-side keep-alive races, retried once and counted
slow: list = []


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def pct(xs, p):
    if not xs:
        return None
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]


class Client:
    def __init__(self, name: str, base: str, frag: str, ws_query: str = ""):
        self.name, self.base, self.frag, self.ws_query = name, base, frag, ws_query
        self.http = httpx.AsyncClient(base_url=base, timeout=30)
        self.received: dict[int, float] = {}
        self.latencies: list[float] = []
        self.lat_at: list[float] = []
        self.notify: list[float] = []
        self.first_seq = None
        self.reconnects = 0
        self.last_seq = 0
        self.fragment = ""
        self.stop = False

    async def csrf(self) -> str:
        if "soc_csrf" not in self.http.cookies:
            await self.http.get("/healthz")
        return self.http.cookies["soc_csrf"]

    async def post(self, url, data=None):
        d = dict(data or {})
        d["csrf"] = await self.csrf()
        t0 = time.time()
        bisect.insort(actions, t0)
        r = await self.http.post(url, data=d, follow_redirects=False)
        slow.append((time.time() - t0, "POST " + url))
        if r.status_code >= 500:
            errors.append(f"{self.name} POST {url} -> {r.status_code}")
        return r

    def cookie_header(self):
        return "; ".join(f"{k}={v}" for k, v in self.http.cookies.items())

    async def fetch(self, started: float):
        t0 = time.time()
        try:
            r = await self.http.get(self.frag)
        except httpx.TransportError as e:       # e.g. keep-alive connection closed under us: retry once, count it
            transport_retries.append(f"{self.name} GET {self.frag}: {e!r}")
            r = await self.http.get(self.frag)
        slow.append((time.time() - t0, "GET " + self.frag))
        if r.status_code != 200:
            errors.append(f"{self.name} GET {self.frag} -> {r.status_code}")
            return
        self.fragment = r.text
        done = time.time()
        i = bisect.bisect_right(actions, started + 0.001)
        if i:
            self.latencies.append(done - actions[i - 1])
            self.lat_at.append(done)

    def schedule_fetch(self, started: float):
        """Same throttle as app/static/js/live.js: at once, then at most every 250 ms, never dropping the last."""
        self.pending_start = min(getattr(self, "pending_start", None) or started, started)
        if getattr(self, "fetch_timer", None):
            return
        wait = max(0.0, 0.25 - (time.time() - getattr(self, "last_fetch", 0)))

        async def go():
            await asyncio.sleep(wait)
            self.fetch_timer = None
            self.last_fetch = time.time()
            st, self.pending_start = self.pending_start, None
            await self.fetch(st)
        self.fetch_timer = asyncio.create_task(go())

    async def run_ws(self, channel: str):
        url = self.base.replace("http", "ws") + "/ws" + self.ws_query
        while not self.stop:
            try:
                async with websockets.connect(url, additional_headers={"Cookie": self.cookie_header()},
                                              ping_interval=None, max_queue=None) as ws:
                    await ws.send(json.dumps({"subscribe": [channel], "since": self.last_seq}))
                    pinger = asyncio.create_task(self._ping(ws))
                    try:
                        async for raw in ws:
                            msg = json.loads(raw)
                            if "subscribed" in msg:
                                if not msg["subscribed"]:
                                    errors.append(f"{self.name} denied: {msg['denied']}")
                                if self.first_seq is None:
                                    self.first_seq = msg["seq"]
                                    self.last_seq = msg["seq"]
                                continue
                            if "channels" in msg:
                                now = time.time()
                                self.received[msg["seq"]] = now
                                self.last_seq = max(self.last_seq, msg["seq"])
                                if "t" in msg:
                                    i = bisect.bisect_right(actions, msg["t"] + 0.001)
                                    if i:
                                        self.notify.append(now - actions[i - 1])
                                self.schedule_fetch(msg.get("t", now))
                            if self.stop:
                                break
                    finally:
                        pinger.cancel()
            except (OSError, websockets.ConnectionClosed) as e:
                if self.stop:
                    break
                self.reconnects += 1
                errors.append(f"{self.name} websocket dropped: {e!r}")
                await asyncio.sleep(1)

    async def _ping(self, ws):
        while True:
            await asyncio.sleep(20)
            await ws.send(json.dumps({"ping": time.time()}))


async def student_loop(c: Client, sid: int, rng: random.Random):
    voted = set()
    while not c.stop:
        await asyncio.sleep(rng.uniform(1, 3))
        m = re.search(r"<h2 id=\"h-vote\">Vote: ([^<]+)</h2>", c.fragment)
        try:
            if m and m.group(1) not in voted and 'name="vote"' in c.fragment:
                voted.add(m.group(1))
                await asyncio.sleep(rng.uniform(0.5, 6))
                await c.post(f"/live/{sid}/vote", {"vote": rng.choice(["yes", "yes", "no", "abstain"])})
            elif "Add me to the speakers list" in c.fragment and rng.random() < 0.02:
                await c.post(f"/live/{sid}/speak")
        except httpx.HTTPError as e:
            errors.append(f"{c.name}: {e!r}")


async def chair_loop(chair: Client, sid: int, db_path: Path, rng: random.Random, until: float):
    conn = sqlite3.connect(str(db_path))
    dels = [r[0] for r in conn.execute("SELECT d.id FROM delegation d JOIN live_session ls ON ls.committee_id = d.committee_id WHERE ls.id = ?", (sid,))]
    paras = [r[0] for r in conn.execute("SELECT p.id FROM paragraph p JOIN resolution r ON r.id = p.resolution_id JOIN live_session ls "
                                        "ON ls.committee_id = r.committee_id WHERE ls.id = ? AND p.kind = 'operative'", (sid,))]
    mod = conn.execute("SELECT pm.id FROM procedure_motion pm JOIN committee cm ON cm.procedure_rule_set_id = pm.rule_set_id "
                       "JOIN live_session ls ON ls.committee_id = cm.id WHERE ls.id = ? AND pm.code = 'mod'", (sid,)).fetchone()[0]
    conn.close()
    n = 0
    while time.time() < until:
        n += 1
        step = n % 12
        try:
            if step in (1, 2, 3):
                await chair.post(f"/chair/{sid}/speakers", {"delegation_id": rng.choice(dels)})
            elif step in (4, 8, 11):     # the chair calls speakers about as fast as they are added
                await chair.post(f"/chair/{sid}/next")
            elif step in (5, 9):
                tid = _latest_timer(db_path, sid)
                if tid:
                    await chair.post(f"/chair/{sid}/timers/{tid}", {"action": rng.choice(["start", "pause", "extend"]), "seconds": "30"})
            elif step == 6:
                await chair.post(f"/chair/{sid}/motions", {"procedure_motion_id": mod, "proposer_delegation_id": rng.choice(dels),
                                                           "duration_min": "5", "speaking_time_s": "45", "topic": f"Topic {n}"})
                mid = _latest(db_path, "SELECT MAX(id) FROM motion WHERE session_id = ?", sid)
                await chair.post(f"/chair/{sid}/motions/{mid}", {"action": "second", "delegation_id": rng.choice(dels)})
                await chair.post(f"/chair/{sid}/motions/{mid}", {"action": "consent"})
            elif step == 7:
                await chair.post(f"/chair/{sid}/end-caucus")
            elif step == 10:
                await chair.post(f"/chair/{sid}/divisions", {"target": f"paragraph:{rng.choice(paras)}", "title": f"Division {n}"})
                await asyncio.sleep(12)          # students vote
                did = _latest(db_path, "SELECT MAX(id) FROM division WHERE session_id = ? AND status = 'open'", sid)
                if did:
                    await chair.post(f"/chair/{sid}/divisions/{did}", {"action": "close"})
        except httpx.HTTPError as e:
            errors.append(f"chair: {e!r}")
        await asyncio.sleep(rng.uniform(1.5, 2.5))


def _latest(db_path, sql, *params):
    conn = sqlite3.connect(str(db_path))
    try:
        r = conn.execute(sql, params).fetchone()
        return r[0] if r else None
    finally:
        conn.close()


def _latest_timer(db_path, sid):
    return _latest(db_path, "SELECT MAX(id) FROM timer WHERE session_id = ? AND state != 'done'", sid)


def _describe(db_path, seqs):
    conn = sqlite3.connect(str(db_path))
    try:
        return [list(conn.execute("SELECT seq, actor_kind, entity, action, channel FROM event_log WHERE seq = ?", (q,)).fetchone() or [q])
                for q in seqs]
    finally:
        conn.close()


def rss_mb(pid: int) -> float | None:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    except OSError:
        return None
    return None


def server_rss_mb(timing_log: Path) -> float | None:
    """The server's own latest memory reading from its STATS lines (D-081). Used where /proc can't be read
    (Windows, where the venv's python.exe is also a launcher whose PID isn't the server's)."""
    try:
        lines = timing_log.read_text().splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        m = re.search(r" STATS rss_mb=([\d.]+)", line)
        if m:
            return float(m.group(1))
    return None


def slope_per_hour(pts):
    """Least-squares slope of (seconds, value) points, per hour."""
    if len(pts) < 2:
        return None
    n = len(pts)
    mx, my = sum(t for t, _ in pts) / n, sum(v for _, v in pts) / n
    den = sum((t - mx) ** 2 for t, _ in pts)
    return round(sum((t - mx) * (v - my) for t, v in pts) / den * 3600, 2) if den else None


def soak_verdict(start, mem, windows, warmup_min=10, span_min=60):
    """Phase 7 target: after a 10-minute warm-up, RSS grows < 10 MB over the next 60 minutes and p95 doesn't trend up."""
    after = [(t, m) for t, m in mem if m and t >= start + warmup_min * 60]
    inside = [(t, m) for t, m in after if t <= start + (warmup_min + span_min) * 60]
    growth = round(inside[-1][1] - inside[0][1], 1) if len(inside) >= 2 else None
    p95s = [(w["from_min"] * 60, w["p95"]) for w in windows if w["from_min"] >= warmup_min and w["p95"] is not None]
    covered = bool(inside) and inside[-1][0] - inside[0][0] >= (span_min - 1) * 60
    return {"warmup_min": warmup_min, "span_min": span_min, "span_covered": covered,
            "rss_growth_mb": growth, "rss_slope_mb_per_hour": slope_per_hour(after),
            "p95_slope_s_per_hour": slope_per_hour(p95s),
            "rss_target_met": (growth is not None and growth < 10) if covered else None}


async def main(minutes: float, seed: int) -> dict:
    rng = random.Random(seed)
    tmp = Path(tempfile.mkdtemp(prefix="soc-load-"))
    from app.config import Settings
    from app.util import hash_passphrase
    s = Settings(data_dir=tmp).load()
    s.values.update(coordinator_hash=hash_passphrase(PASS), dataset="demo")
    s.save()
    port = free_port()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "timing.log").unlink(missing_ok=True)
    (OUT / "rss.jsonl").unlink(missing_ok=True)
    server_log = open(OUT / "server.log", "w")
    proc = subprocess.Popen([sys.executable, "-m", "app", "--data-dir", str(tmp), "--port", str(port), "--host", "127.0.0.1"],
                            cwd=str(ROOT), stdout=server_log, stderr=subprocess.STDOUT,
                            env={**os.environ, "SOC_TIMING_LOG": str(OUT / "timing.log")})
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if httpx.get(base + "/healthz").status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.2)
    db_path = s.db_path("demo")
    conn = sqlite3.connect(str(db_path))
    com, cls, code = conn.execute("SELECT cm.id, c.id, c.code FROM committee cm JOIN class c ON c.id = cm.class_id "
                                  "WHERE cm.name LIKE 'United Nations General Assembly%'").fetchone()
    students = [(r[0], r[1]) for r in conn.execute("SELECT id, login_code FROM student WHERE class_id = ? ORDER BY id", (cls,))]
    conn.close()

    chair = Client("chair", base, "")
    await chair.post("/login", {"who": "coordinator", "passphrase": PASS})
    r = await chair.post(f"/chair/committee/{com}/open")
    sid = int(r.headers["location"].rsplit("/", 1)[1])
    chair.frag = f"/chair/{sid}/f/floor"
    token = _latest(db_path, "SELECT projector_token FROM live_session WHERE id = ?", sid)

    clients = [chair]
    for i in range(3):
        st = Client(f"staff{i}", base, f"/chair/{sid}/f/division")
        await st.post("/login", {"who": "coordinator", "passphrase": PASS})
        clients.append(st)
    clients.append(Client("projector", base, f"/projector/{token}/f", f"?projector={token}"))
    studs = []
    for i, (stid, login_code) in enumerate(students):
        c = Client(f"student{i}", base, f"/live/{sid}/f")
        await c.post("/join", {"code": login_code})
        r = await c.http.get(f"/live/{sid}")
        if r.status_code != 200:
            errors.append(f"student{i} could not open live page: {r.status_code}")
        studs.append(c)
    clients += studs
    assert len(clients) == 30, len(clients)

    channel = f"session:{sid}"
    ws_tasks = [asyncio.create_task(c.run_ws(channel)) for c in clients]
    await asyncio.sleep(2)
    start = time.time()
    until = start + minutes * 60
    loops = [asyncio.create_task(chair_loop(chair, sid, db_path, rng, until))]
    loops += [asyncio.create_task(student_loop(c, sid, random.Random(seed + i))) for i, c in enumerate(studs)]
    mem = []
    rss_source = "/proc"
    while time.time() < until:
        await asyncio.sleep(30)
        reading = rss_mb(proc.pid)
        if reading is None:
            reading = server_rss_mb(OUT / "timing.log")
            rss_source = "server STATS lines (D-081)"
        mem.append((time.time(), reading))
        with open(OUT / "rss.jsonl", "a") as f:          # kept as it goes, so an interrupted run still has its samples
            f.write(json.dumps({"t": round(mem[-1][0] - start, 1), "rss_mb": mem[-1][1]}) + "\n")
    await asyncio.sleep(5)            # let the last updates arrive
    for c in clients:
        c.stop = True
    for t in loops:
        t.cancel()
    await asyncio.sleep(1)
    for t in ws_tasks:
        t.cancel()

    # Expected changes: one per action group touching the session channel after each client subscribed.
    conn = sqlite3.connect(str(db_path))
    groups = [r[0] for r in conn.execute(
        "SELECT (SELECT MAX(seq) FROM event_log x WHERE x.action_group = g.action_group) AS s FROM event_log g "
        "WHERE g.channel = ? GROUP BY g.action_group ORDER BY s", (channel,))]
    stats = conn.execute("SELECT COUNT(*) FROM event_log WHERE channel = ?", (channel,)).fetchone()[0]
    divisions = conn.execute("SELECT COUNT(*) FROM division WHERE session_id = ? AND status = 'closed'", (sid,)).fetchone()[0]
    votes = conn.execute("SELECT COUNT(*) FROM division_vote dv JOIN division d ON d.id = dv.division_id WHERE d.session_id = ? "
                         "AND dv.computed = 0", (sid,)).fetchone()[0]
    conn.close()
    lost = {}
    missing_examples: set = set()
    for c in clients:
        expected = [g for g in groups if g > (c.first_seq or 0)]
        missing = [g for g in expected if g not in c.received]
        if missing:
            lost[c.name] = len(missing)
            missing_examples.update(missing[:3])
    all_lat = [x for c in clients for x in c.latencies]
    windows = []
    for k in range(int(minutes // 5) + 1):
        lo, hi = start + k * 300, start + (k + 1) * 300
        xs = [x for c in clients for x, at in zip(c.latencies, c.lat_at) if lo <= at < hi]
        if xs:
            ms = [m for at, m in mem if lo <= at < hi and m]
            windows.append({"from_min": k * 5, "n": len(xs), "p50": pct(xs, 50), "p95": pct(xs, 95), "max": max(xs),
                            "rss_mb_end": ms[-1] if ms else None})
    all_notify = [x for c in clients for x in c.notify]
    proc.terminate()
    try:
        proc.wait(10)
    except subprocess.TimeoutExpired:
        proc.kill()
    summary = {
        "minutes": minutes, "clients": len(clients), "ws_connections": len(clients),
        "changes_on_channel": len(groups), "events_logged": stats, "actions": len(actions),
        "divisions_closed": divisions, "student_votes": votes,
        "lost_events": sum(lost.values()), "lost_by_client": lost,
        "missing_examples": _describe(db_path, sorted(missing_examples)[:5]),
        "update_latency_s": {"n": len(all_lat), "p50": pct(all_lat, 50), "p95": pct(all_lat, 95), "p99": pct(all_lat, 99),
                             "max": max(all_lat) if all_lat else None},
        "notify_latency_s": {"n": len(all_notify), "p50": pct(all_notify, 50), "p95": pct(all_notify, 95), "max": max(all_notify) if all_notify else None},
        "update_latency_by_5_min": windows,
        "reconnects": sum(c.reconnects for c in clients), "errors": errors[:50], "error_count": len(errors),
        "client_transport_retries": len(transport_retries), "transport_retry_examples": transport_retries[:5],
        "server_rss_mb": {"first": mem[0][1] if mem else None, "last": mem[-1][1] if mem else None,
                          "max": max([m for _, m in mem if m] or [0]), "source": rss_source},
        "soak": soak_verdict(start, mem, windows),
        "machine": f"{platform.system()} {platform.release()}, Python {platform.python_version()}",
        "http_s": {"n": len(slow), "p50": pct([x[0] for x in slow], 50), "p95": pct([x[0] for x in slow], 95),
                   "slowest": sorted(slow, reverse=True)[:8]},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=45)
    ap.add_argument("--seed", type=int, default=2026)
    a = ap.parse_args()
    print(json.dumps(asyncio.run(main(a.minutes, a.seed)), indent=2))
