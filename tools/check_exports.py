"""Check that exports open in office software (spec Phase 1 exit: "every export opens in Word, Excel and a PDF viewer").

What this can and can't prove: it opens each file in LibreOffice (headless) and
poppler's pdfinfo/pdftotext, which parse the same formats as Word, Excel and a
PDF viewer. It does not run Microsoft Word or Excel themselves; Ben should open
one of each on the school laptop to confirm.

Usage:  python tools/check_exports.py   (needs soffice and pdfinfo on PATH, plus Playwright/Chromium)
Writes a summary to test-results/exports/summary.json.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.conftest import COORD_PASS, make_settings, new_client, login_coordinator  # noqa: E402

OUT = ROOT / "test-results" / "exports"


def soffice_convert(src: Path, fmt: str) -> tuple[bool, str]:
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if not exe:
        return False, "LibreOffice not installed"
    outdir = src.parent / f"conv_{fmt}"
    outdir.mkdir(exist_ok=True)
    r = subprocess.run([exe, "--headless", "--convert-to", fmt, "--outdir", str(outdir), str(src)],
                       capture_output=True, text=True, timeout=180)
    produced = list(outdir.glob(f"{src.stem}.*"))
    ok = r.returncode == 0 and produced and produced[0].stat().st_size > 0
    return bool(ok), (produced[0].name if produced else r.stderr[-300:])


def pdf_ok(path: Path) -> tuple[bool, str]:
    if not shutil.which("pdfinfo"):
        return False, "pdfinfo not installed"
    r = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True)
    pages = [l for l in r.stdout.splitlines() if l.startswith("Pages:")]
    t = subprocess.run(["pdftotext", str(path), "-"], capture_output=True, text=True).stdout if shutil.which("pdftotext") else ""
    return r.returncode == 0 and bool(pages), (pages[0] if pages else r.stderr) + f"; {len(t)} chars of text"


def main() -> int:
    from app.main import create_app
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp())
    app = create_app(make_settings(tmp))
    files: dict[str, Path] = {}
    with new_client(app) as c:
        login_coordinator(c)
        with app.state.db.read() as conn:
            res = conn.execute("SELECT id FROM resolution ORDER BY id LIMIT 1").fetchone()[0]
        c.post(f"/mun/predict/resolution/{res}/snapshot")
        with app.state.db.read() as conn:
            pid = conn.execute("SELECT id FROM prediction ORDER BY id DESC LIMIT 1").fetchone()[0]
        extra = getattr(sys.modules[__name__], "EXTRA_EXPORTS", [])
        for name, url in [("resolution.docx", f"/mun/resolutions/{res}/export.docx"),
                          ("prediction.csv", f"/mun/predictions/{pid}.csv"),
                          ("countries.csv", "/admin/csv/country.csv"),
                          ("event_log.csv", "/admin/csv/event_log.csv")] + extra:
            r = c.get(url)
            assert r.status_code == 200, (url, r.status_code)
            p = OUT / name
            p.write_bytes(r.content)
            files[name] = p
    # PDF: the browser's print-to-PDF of the print page (D-016)
    from tests.ui.conftest import FALLBACK_CHROMIUM, LiveServer, free_port, login
    from playwright.sync_api import sync_playwright
    srv = LiveServer(app, free_port()).start()
    try:
        with sync_playwright() as pw:
            try:
                b = pw.chromium.launch()
            except Exception:
                b = pw.chromium.launch(executable_path=os.environ.get("PW_CHROMIUM", FALLBACK_CHROMIUM))
            pg = b.new_page()
            login(pg, srv)
            pg.goto(f"{srv.url}/mun/resolutions/{res}/print")
            pg.pdf(path=str(OUT / "resolution.pdf"), format="A4")
            files["resolution.pdf"] = OUT / "resolution.pdf"
            b.close()
    finally:
        srv.stop()
    summary = {}
    for name, p in files.items():
        if name.endswith(".docx"):
            ok, detail = soffice_convert(p, "pdf")
            summary[name] = {"opens_in": "LibreOffice Writer (Word format)", "ok": ok, "detail": detail}
        elif name.endswith(".csv"):
            ok, detail = soffice_convert(p, "xlsx")
            text = p.read_bytes()
            summary[name] = {"opens_in": "LibreOffice Calc (Excel)", "ok": ok, "detail": detail,
                             "utf8_bom": text.startswith(b"\xef\xbb\xbf")}
        elif name.endswith(".pdf"):
            ok, detail = pdf_ok(p)
            summary[name] = {"opens_in": "poppler pdfinfo/pdftotext", "ok": ok, "detail": detail}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0 if all(v["ok"] for v in summary.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
