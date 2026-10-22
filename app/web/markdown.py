"""A small Markdown-to-HTML converter for the platform's own guides (docs/*.md) shown inside the app.

Covers what the guides use: #/##/### headings, paragraphs, - bullet and 1. numbered lists, **bold**, *italic*,
`code` and [links](url). Everything is HTML-escaped first, so a guide can't inject markup. Not a general parser.
"""
from __future__ import annotations

import re

from markupsafe import Markup, escape


def _inline(text: str) -> str:
    s = str(escape(text))
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![*\w])\*([^*\s][^*]*)\*(?!\*)", r"<em>\1</em>", s)

    def link(m):
        href = m.group(2)
        if not re.match(r"^(https?://|/|#|mailto:)", href):
            return m.group(1)               # relative file links (docs/x.md) aren't pages in the app
        return f'<a href="{href}">{m.group(1)}</a>'
    return re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, s)


def render_markdown(text: str, heading_offset: int = 0) -> Markup:
    out: list[str] = []
    para: list[str] = []
    lst: str | None = None

    def flush_para():
        if para:
            out.append("<p>" + _inline(" ".join(para)) + "</p>")
            para.clear()

    def close_list():
        nonlocal lst
        if lst:
            out.append(f"</{lst}>")
            lst = None

    for raw in text.splitlines():
        line = raw.rstrip()
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            flush_para(); close_list()
            level = min(6, len(m.group(1)) + heading_offset)
            slug = re.sub(r"[^a-z0-9]+", "-", m.group(2).lower()).strip("-")
            out.append(f'<h{level} id="{slug}">{_inline(m.group(2))}</h{level}>')
            continue
        m = re.match(r"^\s*(-|\d+\.)\s+(.*)$", line)
        if m:
            flush_para()
            kind = "ul" if m.group(1) == "-" else "ol"
            if lst != kind:
                close_list()
                out.append(f"<{kind}>")
                lst = kind
            out.append("<li>" + _inline(m.group(2)) + "</li>")
            continue
        if not line.strip():
            flush_para(); close_list()
            continue
        if lst and raw.startswith("  "):          # continuation of a list item
            out[-1] = out[-1][:-5] + " " + _inline(line.strip()) + "</li>"
            continue
        close_list()
        para.append(line.strip())
    flush_para(); close_list()
    return Markup("\n".join(out))
