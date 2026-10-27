"""South Oakleigh design tokens (D-058) and the colour pairs the interface uses.

The values here must match the `:root` block of app/static/css/app.css;
tests/test_design_contrast.py checks that, and checks every pair below
against WCAG 2.2 AA: 4.5:1 for normal text, 3:1 for large text (24 px, or
18.66 px bold) and for interface parts such as borders and focus rings.

Brand colours come from HANDOVER.md §10. Where a brand colour fails on a
background it is used on, a darker shade is added beside it, never silently
swapped (each is listed in docs/decisions.md D-058).
"""
from __future__ import annotations

TOKENS = {
    # Brand (HANDOVER §10)
    "maroon": "#8C332A",        # primary: buttons, links, active states
    "maroon-dk": "#2A1512",     # header, navigation, projector background
    "green": "#0A6B39",         # success, "for", "yes"
    "green-dk": "#0A4527",
    "gold": "#B8960C",          # accent: decoration, or on dark backgrounds only
    "gold-lt": "#D4B441",       # accent on dark backgrounds
    "cream": "#F4F0E6",         # page
    "card": "#FBFAF6",          # cards, tables, inputs
    "ink": "#2A2320",           # body text
    # Added for AA (D-058): darker shades of brand colours for text on light surfaces
    "gold-text": "#7A6206",     # gold on cream is 2.5:1; this is 5.2:1
    "muted": "#655C55",         # secondary text
    "line": "#D9D0C1",          # decorative dividers (not relied on to find a control)
    "control": "#8A7F76",       # input and control borders: 3:1 on cream and card
    "white": "#FFFFFF",
    # Tinted surfaces for messages and stances
    "ok-bg": "#E3F1E7", "err-bg": "#F8E6E3", "warn-bg": "#FBF1D3", "info-bg": "#EFE7DA",
    "yes-bg": "#DDEFE3", "no-bg": "#F6E1DD", "abs-bg": "#ECE7E1", "unk-bg": "#F1EEE9",
    # Projector (dark) theme
    "proj-bg": "#2A1512", "proj-card": "#3D211C", "proj-text": "#F4F0E6", "proj-accent": "#D4B441",
    "proj-low": "#FFC2B8", "proj-line": "#6B4A42",
    # Speech timer bells as colour (D-075): speaking, after the warning bell, past time. The text on each always
    # says which, so colour is never the only signal.
    "time-go": "#0A6B39", "time-warn": "#F2C14E", "time-over": "#B3261E",
}

TEXT, LARGE, UI = 4.5, 3.0, 3.0

# (foreground, background, minimum ratio, where it is used)
PAIRS = [
    ("ink", "cream", TEXT, "body text"), ("ink", "card", TEXT, "text on cards and tables"),
    ("ink", "white", TEXT, "text in inputs"),
    ("muted", "cream", TEXT, "secondary text"), ("muted", "card", TEXT, "secondary text on cards"),
    ("maroon", "cream", TEXT, "links"), ("maroon", "card", TEXT, "links on cards, secondary buttons"),
    ("white", "maroon", TEXT, "primary button"), ("white", "maroon-dk", TEXT, "header text"),
    ("gold-lt", "maroon-dk", TEXT, "header accent, current-page marker"),
    ("cream", "maroon-dk", TEXT, "header links"),
    ("white", "green", TEXT, "success button"),
    ("green", "cream", TEXT, "'for' text"), ("green-dk", "ok-bg", TEXT, "success message"),
    ("gold-text", "cream", TEXT, "gold text on the page"), ("gold-text", "card", TEXT, "gold text on cards"),
    ("ink", "warn-bg", TEXT, "warning message"), ("ink", "err-bg", TEXT, "error message"),
    ("ink", "info-bg", TEXT, "information message"), ("ink", "ok-bg", TEXT, "success message body"),
    ("maroon", "err-bg", TEXT, "error heading"),
    ("green-dk", "yes-bg", TEXT, "Yes / Support badge"), ("maroon", "no-bg", TEXT, "No / Oppose badge"),
    ("ink", "abs-bg", TEXT, "Abstain badge"), ("muted", "unk-bg", TEXT, "Unknown badge"),
    ("control", "cream", UI, "input borders on the page"), ("control", "card", UI, "input borders on cards"),
    ("maroon-dk", "cream", UI, "focus ring (inner)"), ("gold-lt", "maroon-dk", UI, "focus ring on the dark header"),
    ("maroon", "card", UI, "secondary button border"),
    ("proj-text", "proj-bg", TEXT, "projector text"), ("proj-text", "proj-card", TEXT, "projector cards"),
    ("proj-accent", "proj-bg", TEXT, "projector headings and timer"), ("proj-accent", "proj-card", TEXT, "projector accent on cards"),
    ("proj-low", "proj-bg", TEXT, "projector timer, last 10 seconds"), ("proj-low", "proj-card", TEXT, "low timer on a card"),
    ("proj-line", "proj-bg", 1.0, "projector dividers (decorative)"),
    ("white", "time-go", TEXT, "speech timer: speaking"), ("ink", "time-warn", TEXT, "speech timer: warning bell"),
    ("white", "time-over", TEXT, "speech timer: past time"),
]


def luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)
