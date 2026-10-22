"""Exports: CSV (standard library), Word (python-docx). PDF is the browser's
print-to-PDF from print stylesheets (D-016), so there is no PDF code here.
"""
from __future__ import annotations

import csv
import io

from docx import Document
from docx.shared import Pt

from app.modules.admin.tables import SECRET_COLUMNS


def csv_bytes(rows: list[dict], columns: list[str] | None = None) -> bytes:
    """UTF-8 with a byte-order mark so Excel opens accents (Türkiye, Côte d'Ivoire) correctly."""
    if columns is None:
        columns = list(rows[0].keys()) if rows else []
    columns = [c for c in columns if c not in SECRET_COLUMNS]
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(columns)
    for r in rows:
        w.writerow(["" if r.get(c) is None else r.get(c) for c in columns])
    return ("﻿" + buf.getvalue()).encode("utf-8")


def read_csv(data: bytes) -> list[dict]:
    text = data.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def _doc(title: str, subtitle: str = "") -> Document:
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)
    doc.core_properties.title = title
    doc.core_properties.author = "South Oakleigh College"
    doc.add_heading(title, level=0)
    if subtitle:
        doc.add_paragraph(subtitle)
    return doc


def docx_bytes(doc: Document) -> bytes:
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def resolution_docx(resolution: dict, committee: dict, preambular: list[dict], operative: list[dict],
                    sponsors: list[str]) -> bytes:
    doc = _doc(resolution["title"], committee["name"])
    if sponsors:
        doc.add_paragraph("Sponsors: " + ", ".join(sponsors))
    for p in preambular:
        para = doc.add_paragraph(p["text"])
        para.paragraph_format.left_indent = Pt(18)
    for p in operative:
        para = doc.add_paragraph()
        para.add_run(f"{p['position']}. ").bold = True
        para.add_run(p["text"])
    return docx_bytes(doc)


def text_docx(title: str, body: str, subtitle: str = "") -> bytes:
    """A plain document from text (minutes, run sheets, MC scripts). Lines in CAPITALS become headings."""
    doc = _doc(title, subtitle)
    for line in body.splitlines():
        s = line.rstrip()
        if not s:
            continue
        if s.isupper() and len(s) < 80:
            doc.add_heading(s.title(), level=2)
        elif s.startswith("- "):
            doc.add_paragraph(s[2:], style="List Bullet")
        else:
            doc.add_paragraph(s)
    return docx_bytes(doc)


def table_docx(title: str, headers: list[str], rows: list[list], subtitle: str = "") -> bytes:
    doc = _doc(title, subtitle)
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    for i, h in enumerate(headers):
        t.rows[0].cells[i].text = str(h)
    for r in rows:
        cells = t.add_row().cells
        for i, v in enumerate(r):
            cells[i].text = "" if v is None else str(v)
    return docx_bytes(doc)
