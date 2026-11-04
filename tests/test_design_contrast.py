"""Design system (D-058): every text/background pair the interface uses meets WCAG 2.2 AA,
and the CSS uses exactly the token values that were checked."""
import re
from pathlib import Path

import pytest

from app.web.design import PAIRS, TOKENS, contrast

CSS = (Path(__file__).resolve().parents[1] / "app" / "static" / "css" / "app.css").read_text(encoding="utf-8")


def _root_vars() -> dict:
    root = re.search(r":root\s*\{(.*?)\}", CSS, re.S).group(1)
    return {k: v.upper() for k, v in re.findall(r"--([a-z0-9-]+)\s*:\s*(#[0-9A-Fa-f]{6})", root)}


def test_css_tokens_match_checked_values():
    css = _root_vars()
    assert {k: v.upper() for k, v in TOKENS.items()} == {k: css.get(k) for k in TOKENS}


@pytest.mark.parametrize("fg,bg,minimum,where", PAIRS, ids=[f"{p[0]}-on-{p[1]}" for p in PAIRS])
def test_pair_meets_aa(fg, bg, minimum, where):
    ratio = contrast(TOKENS[fg], TOKENS[bg])
    assert ratio >= minimum, f"{fg} on {bg} ({where}) is {ratio:.2f}:1, needs {minimum}:1"


def test_contrast_maths():
    assert round(contrast("#000000", "#FFFFFF"), 1) == 21.0
    assert round(contrast("#777777", "#FFFFFF"), 2) == 4.48       # the classic just-fails grey


def test_no_raw_colours_outside_tokens():
    """Colours in the stylesheet come from the tokens, so the contrast test covers what users see."""
    body = re.sub(r":root\s*\{.*?\}", "", CSS, count=1, flags=re.S)
    raw = sorted(set(re.findall(r"#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{3}\b", body)))
    assert raw == []


def test_the_board_uses_only_tokens():
    """The board (D-092) has its own stylesheet; it takes every colour from the same tokens."""
    board = (Path(__file__).resolve().parents[1] / "app" / "static" / "css" / "board.css").read_text(encoding="utf-8")
    assert re.findall(r"#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{3}\b", board) == []
    # Set by board.js, not colours: a tally bar's width, the scroll's height, the spotlight's centre and radius.
    used = set(re.findall(r"var\(--([a-z0-9-]+)", board)) - {"w", "h", "sx", "sy", "sr"}
    defined = set(re.findall(r"--([a-z0-9-]+):", CSS))
    assert used <= defined, used - defined


def test_the_session_uses_only_tokens():
    """The Session (D-101) has its own stylesheet; its colours come from the same tokens."""
    css = (Path(__file__).resolve().parents[1] / "app" / "static" / "css" / "session.css").read_text(encoding="utf-8")
    assert re.findall(r"#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{3}\b", css) == []
    used = set(re.findall(r"var\(--([a-z0-9-]+)", css)) - {"p"}       # --p: a clause's chance on its dial, set by session.js
    defined = set(re.findall(r"--([a-z0-9-]+):", CSS))
    assert used <= defined, used - defined
