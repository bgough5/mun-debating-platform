"""Small safety helpers (D-083, docs/security-audit.md).

- csv_safe / csv_unguard: stop a spreadsheet running an exported cell as a formula (S-1).
- safe_path / safe_back: keep redirect targets on this site (S-3).
- safe_svg / svg_is_safe: allow only a known-safe inline-SVG subset for stored flag markup (S-5).

Each one is conservative: when in doubt it neutralises rather than trusts.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urlsplit

from markupsafe import Markup, escape

# ---------- S-1: CSV formula injection ----------

_FORMULA_LEAD = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value):
    """Text that a spreadsheet won't run as a formula. Excel and Sheets execute a cell starting with = + - @
    (or a tab or carriage return before one); such text gets a leading apostrophe, which they show as text.
    Numbers are left alone, so -3 stays a number."""
    if isinstance(value, str) and value.startswith(_FORMULA_LEAD):
        return "'" + value
    return value


def csv_unguard(value):
    """Undo csv_safe on import, so exporting and re-importing a file doesn't pile up apostrophes."""
    if isinstance(value, str) and len(value) > 1 and value[0] == "'" and value[1:].startswith(_FORMULA_LEAD):
        return value[1:]
    return value


# ---------- S-3: redirects stay on this site ----------

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def safe_path(target, default: str = "/") -> str:
    """A redirect target that stays on this site, else `default`: a path starting with a single "/",
    with no backslash (browsers read "\\" as "/"), no control characters and no scheme or host."""
    if not isinstance(target, str):
        return default
    t = target.strip()
    if not t.startswith("/") or t.startswith("//") or "\\" in t or _CONTROL.search(t):
        return default
    return t


def safe_back(request, default: str = "/") -> str:
    """The page the browser came from (Referer), only if it is on this same site."""
    ref = request.headers.get("referer") or ""
    try:
        u = urlsplit(ref)
    except ValueError:
        return default
    if u.scheme not in ("http", "https") or u.netloc != request.url.netloc:
        return default
    return safe_path(u.path + (f"?{u.query}" if u.query else ""), default)


# ---------- S-5: stored flag markup ----------

_SVG_TAGS = {"svg", "g", "defs", "clippath", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "title"}
# Geometry and presentation only: no event handlers, no href or xlink:href, no style (CSS can load URLs).
_SVG_ATTRS = {"viewbox", "xmlns", "width", "height", "fill", "fill-rule", "fill-opacity", "stroke", "stroke-width",
              "stroke-linecap", "stroke-linejoin", "stroke-dasharray", "stroke-opacity", "opacity", "d", "points",
              "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry", "transform", "clip-path", "id", "class",
              "preserveaspectratio"}
# Values that could load or run something. url(#id) (a reference inside the same SVG) is allowed.
_RISKY_VALUE = re.compile(r"javascript:|vbscript:|data:|expression\s*\(|url\s*\(\s*(?![\"']?#)", re.I)


class _SvgCheck(HTMLParser):
    """Walks the markup; records whether every piece is allowed and rebuilds it from the allowed pieces only."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.ok, self.saw_svg, self.out = True, False, []

    def _start(self, tag, attrs, self_closing):
        if tag not in _SVG_TAGS:
            self.ok = False
            return
        self.saw_svg |= tag == "svg"
        parts = []
        for name, value in attrs:            # values arrive already entity-decoded, so encoded tricks are caught
            name, value = name.lower(), value or ""
            if name.startswith("on") or name not in _SVG_ATTRS or _RISKY_VALUE.search(value):
                self.ok = False
                return
            parts.append(f' {name}="{escape(value)}"')
        self.out.append(f"<{tag}{''.join(parts)}{' /' if self_closing else ''}>")

    def handle_starttag(self, tag, attrs):
        self._start(tag, attrs, False)

    def handle_startendtag(self, tag, attrs):
        self._start(tag, attrs, True)

    def handle_endtag(self, tag):
        if tag not in _SVG_TAGS:
            self.ok = False
            return
        self.out.append(f"</{tag}>")

    def handle_data(self, data):
        self.out.append(str(escape(data)))

    def _refuse(self, *_):
        self.ok = False

    handle_comment = handle_decl = handle_pi = unknown_decl = handle_entityref = handle_charref = _refuse


def _check(markup) -> _SvgCheck:
    p = _SvgCheck()
    p.feed(str(markup))
    p.close()
    return p


def safe_svg(markup) -> Markup:
    """The flag markup rebuilt from allowed SVG pieces only, or nothing if any piece isn't allowed.
    The output is re-serialised from what was checked, so what the browser gets is exactly what passed."""
    if not markup or not str(markup).strip():
        return Markup("")
    p = _check(markup)
    return Markup("".join(p.out)) if p.ok and p.saw_svg else Markup("")


def svg_is_safe(markup) -> bool:
    """For saving: empty, or markup that passes safe_svg."""
    if not markup or not str(markup).strip():
        return True
    p = _check(markup)
    return p.ok and p.saw_svg
