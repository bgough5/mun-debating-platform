"""Icons (D-059): local Lucide sprite, one icon per concept, accessible markup."""
import re
from pathlib import Path

import pytest

from app.web.icons import CONCEPTS, icon

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"


def test_sprite_has_every_concept_and_licence():
    sprite = (STATIC / "icons" / "sprite.svg").read_text(encoding="utf-8")
    ids = set(re.findall(r'<symbol id="i-([a-z0-9-]+)"', sprite))
    assert ids == set(CONCEPTS)
    lic = (STATIC / "icons" / "LICENSE-lucide.txt").read_text(encoding="utf-8")
    assert lic.startswith("ISC License")


def test_decorative_and_labelled_icons():
    deco = str(icon("vote"))
    assert 'aria-hidden="true"' in deco and "role=" not in deco and "#i-vote" in deco
    named = str(icon("undo", "Undo"))
    assert 'role="img"' in named and 'aria-label="Undo"' in named and "aria-hidden" not in named
    assert 'aria-label="&lt;b&gt;"' in str(icon("x", "<b>"))      # labels are escaped


def test_unknown_icon_fails_loudly():
    with pytest.raises(KeyError):
        icon("not-a-concept")


def test_no_icon_font_or_cdn():
    for f in list((STATIC.parent / "templates").rglob("*.html")) + list((STATIC.parent / "modules").rglob("*.html")):
        text = f.read_text(encoding="utf-8")
        assert not re.search(r'<(link|script)[^>]+(src|href)="https?://', text), f
        assert "font-awesome" not in text.lower() and "material-icons" not in text.lower(), f
