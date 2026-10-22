"""UI test fixtures: a real server on a free port (demo data in a temp folder) and Chromium.

On Ben's laptop:  pip install -r requirements-dev.txt  then  python -m playwright install chromium
"""
from __future__ import annotations

import json
import os
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn

from tests.conftest import COORD_PASS, make_settings

AXE = (Path(__file__).resolve().parents[1] / "vendor" / "axe-4.10.2.min.js").read_text(encoding="utf-8")
AXE_RESULTS = Path(__file__).resolve().parents[2] / "test-results" / "axe"
FALLBACK_CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class LiveServer:
    def __init__(self, app, port):
        self.app, self.port = app, port
        self.url = f"http://127.0.0.1:{port}"
        self.server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def start(self):
        self.thread.start()
        for _ in range(200):
            if self.server.started:
                return self
            time.sleep(0.05)
        raise RuntimeError("server did not start")

    def stop(self):
        self.server.should_exit = True
        self.thread.join(timeout=10)


@pytest.fixture(scope="module")
def live(tmp_path_factory):
    from app.main import create_app
    settings = make_settings(tmp_path_factory.mktemp("ui"))
    srv = LiveServer(create_app(settings), free_port()).start()
    yield srv
    srv.stop()


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception:
            b = p.chromium.launch(executable_path=os.environ.get("PW_CHROMIUM", FALLBACK_CHROMIUM))
        yield b
        b.close()


@pytest.fixture
def page(browser):
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    pg = ctx.new_page()
    yield pg
    ctx.close()


def login(page, live, who="coordinator", passphrase=COORD_PASS):
    page.goto(live.url + "/login")
    page.select_option("#who", who)
    page.fill("#pp", passphrase)
    page.click("button:has-text('Sign in')")
    page.wait_for_load_state("networkidle")


def axe(page, name: str, impacts=("serious", "critical")) -> list:
    """Run axe-core (WCAG 2.0/2.1/2.2 A and AA rules). Returns blocking violations; saves full results."""
    page.add_script_tag(content=AXE)
    res = page.evaluate("""async () => await axe.run(document, {runOnly: {type: 'tag',
        values: ['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']}})""")
    AXE_RESULTS.mkdir(parents=True, exist_ok=True)
    summary = {"url": page.url, "violations": [{"id": v["id"], "impact": v["impact"], "nodes": len(v["nodes"]), "targets": [n["target"] for n in v["nodes"][:5]],
                                                  "help": v["help"]} for v in res["violations"]],
               "passes": len(res["passes"]), "incomplete": len(res["incomplete"])}
    (AXE_RESULTS / f"{name}.json").write_text(json.dumps(summary, indent=1))
    return [v for v in res["violations"] if v["impact"] in impacts]
