"""South Oakleigh design tokens (D-058) and the colour pairs the interface uses.

The values here must match the `:root` block of app/static/css/app.css;
tests/test_design_contrast.py checks that, and checks every pair below
against WCAG 2.2 AA: 4.5:1 for normal text, 3:1 for large text (24 px, or
18.66 px bold) and for interface parts such as borders and focus rings.

Colours are the South Oakleigh College design system's (D-080, replacing
D-058's darker palette): white ground, College Maroon #621723, Green #135728
and Gold #A98B00. Gold is never text (3.3:1 on white).
"""
from __future__ import annotations

TOKENS = {
    # South Oakleigh College design system (D-080): white ground, College Maroon leading, green and gold in support.
    "maroon": "#621723",        # College Maroon: buttons, links, current page, table header rows
    "maroon-dk": "#4A101B",     # hover and pressed states of maroon
    "green": "#135728",         # College Green: success, "for", "yes"
    "green-dk": "#0E4220",
    "gold": "#A98B00",          # College Gold: heading bars, rules and the footer hairline; never text (3.3:1)
    "gold-lt": "#D8B638",       # gold on maroon (eyebrows on dark panels)
    "cream": "#FFFFFF",         # the page (kept as a name for older rules: it is white now)
    "card": "#FFFFFF",          # cards, tables, inputs
    "panel": "#F7F7F7",         # quiet panels, alternate table rows
    "grey": "#EDEDED",          # neutral blocks
    "ink": "#262626",           # all primary text
    "gold-text": "#7A6206",     # the rare gold-coloured word on white (5.9:1)
    "muted": "#4A4A4A",         # secondary text
    "line": "#DDDDDD",          # hairline dividers (decorative; never the only sign of a control)
    "control": "#858585",       # input and control borders: 3:1 on white and panel
    "white": "#FFFFFF",
    # Tints carry boxes, not pages
    "ok-bg": "#E8EFE9", "err-bg": "#F4EBEC", "warn-bg": "#F6F1DC", "info-bg": "#F7F7F7",
    "yes-bg": "#E8EFE9", "no-bg": "#F4EBEC", "abs-bg": "#EDEDED", "unk-bg": "#F7F7F7",
    # Projector: the same clean white ground, read from the back of the room
    "proj-bg": "#FFFFFF", "proj-card": "#F7F7F7", "proj-text": "#262626", "proj-accent": "#621723",
    "proj-low": "#B3261E", "proj-line": "#DDDDDD",
    # Speech timer bells as colour (D-075; the design system's on-screen timer colours). Ink text on each, and the
    # words always say which phase it is, so colour is never the only signal.
    "time-go": "#3FB36A", "time-warn": "#F2B705", "time-over": "#EF5A4F",
    # Table-top game look for the live room (D-089): felt and walnut behind parchment cards, a red stamp, brass trim.
    "felt": "#1E5C3A", "felt-dk": "#143F28", "wood": "#5C3A1E", "parchment": "#F7F0DC", "parchment-dk": "#E9DDBA",
    "stamp": "#A4231B", "brass": "#C9A227",
    # The world map (D-090): sea, land, vote fills and the five UN regional groups as board territories. Fills only;
    # every label sits on a parchment or white token, never on these colours.
    "sea": "#1F4E5A", "sea-lt": "#2B6473", "land": "#E4D6AE",
    "map-yes": "#6FAF7E", "map-no": "#C9675E", "map-abstain": "#B8B2A2",
    "reg-afr": "#D9A441", "reg-apg": "#C97B5A", "reg-eeg": "#8E9CC9", "reg-grulac": "#7DB37A", "reg-weog": "#6FA3B8",
    # The board (D-092): a walnut war-room table; UN blue for the institution (banners, the stage track).
    "walnut-dk": "#24160B", "walnut": "#3E2814", "un-blue": "#1F4E79", "un-blue-lt": "#5B8FCB", "lit": "#F4D77A",
    "un-blue-dk": "#12324F", "brass-dk": "#7A5C0E",
    # The speech coach (D-100): pale marks behind the student's own (ink) text, so the writing stays readable.
    "hl-repeat": "#FCE8A6", "hl-filler": "#F9D3D0", "hl-long": "#DCE8FA", "hl-tech": "#CDEBD5",
    # The Chief of Protocol, The Session's guide (D-101): a painted portrait. Fills only; no text sits on these.
    "skin": "#E2B48C", "skin-dk": "#B9825A", "hair": "#D3D6DB", "hair-dk": "#8E939B", "navy": "#1B2A45", "navy-lt": "#2E4268", "shirt": "#C9DDF2",
    # Delegates in respectful variety (phase 13): skin tones and hair colours, never national costume.
    "skin-lt": "#F3D2B3", "skin-md": "#C68E62", "skin-dp": "#7B4B2C", "hair-bk": "#231A15", "hair-br": "#5A3A22",
}

TEXT, LARGE, UI = 4.5, 3.0, 3.0

# (foreground, background, minimum ratio, where it is used)
PAIRS = [
    ("ink", "cream", TEXT, "body text"), ("ink", "card", TEXT, "text on cards and tables"),
    ("ink", "white", TEXT, "text in inputs"), ("ink", "panel", TEXT, "text on quiet panels and alternate rows"),
    ("muted", "cream", TEXT, "secondary text"), ("muted", "card", TEXT, "secondary text on cards"), ("muted", "panel", TEXT, "secondary text on panels"),
    ("maroon", "cream", TEXT, "links"), ("maroon", "card", TEXT, "links on cards, secondary buttons"), ("maroon", "panel", TEXT, "links on panels"),
    ("white", "maroon", TEXT, "primary button, table header row"), ("white", "maroon-dk", TEXT, "primary button hover"),
    ("gold-lt", "maroon", TEXT, "gold eyebrow on maroon"),
    ("white", "green", TEXT, "success button"),
    ("green", "cream", TEXT, "'for' text"), ("green-dk", "ok-bg", TEXT, "success message"),
    ("gold-text", "cream", TEXT, "gold text on the page"), ("gold-text", "card", TEXT, "gold text on cards"),
    ("ink", "warn-bg", TEXT, "warning message"), ("ink", "err-bg", TEXT, "error message"),
    ("ink", "info-bg", TEXT, "information message"), ("ink", "ok-bg", TEXT, "success message body"),
    ("maroon", "err-bg", TEXT, "error heading"),
    ("green-dk", "yes-bg", TEXT, "Yes / Support badge"), ("maroon", "no-bg", TEXT, "No / Oppose badge"),
    ("ink", "abs-bg", TEXT, "Abstain badge"), ("muted", "unk-bg", TEXT, "Unknown badge"),
    ("control", "cream", UI, "input borders on the page"), ("control", "card", UI, "input borders on cards"),
    ("control", "panel", UI, "input borders on panels"),
    ("maroon", "cream", UI, "focus ring"), ("gold", "cream", UI, "focus ring outer halo and heading bars (non-text)"),
    ("maroon", "card", UI, "secondary button border"),
    ("proj-text", "proj-bg", TEXT, "projector text"), ("proj-text", "proj-card", TEXT, "projector cards"),
    ("proj-accent", "proj-bg", TEXT, "projector headings"), ("proj-accent", "proj-card", TEXT, "projector accent on cards"),
    ("proj-low", "proj-bg", TEXT, "projector timer, last 10 seconds"), ("proj-low", "proj-card", TEXT, "low timer on a card"),
    ("proj-line", "proj-bg", 1.0, "projector dividers (decorative)"),
    ("ink", "time-go", TEXT, "speech timer: speaking"), ("ink", "time-warn", TEXT, "speech timer: warning bell"),
    ("ink", "time-over", TEXT, "speech timer: past time"),
    ("white", "felt", TEXT, "text on the felt table (title cards, reveal)"), ("white", "felt-dk", TEXT, "text on dark felt"),
    ("white", "wood", TEXT, "text on the walnut frame"), ("ink", "parchment", TEXT, "text on parchment cards"),
    ("ink", "parchment-dk", TEXT, "text on worn parchment"), ("stamp", "parchment", TEXT, "red stamp and headline on parchment"),
    ("white", "stamp", TEXT, "breaking news band"), ("maroon", "parchment", TEXT, "maroon headings on parchment"),
    ("green", "parchment", TEXT, "'yes' on parchment"), ("brass", "felt-dk", UI, "brass trim on dark felt (non-text)"),
    ("white", "un-blue", TEXT, "board banners"), ("parchment", "walnut-dk", TEXT, "text on the board's table"),
    ("parchment", "walnut", TEXT, "text on the board's rails"), ("ink", "lit", TEXT, "text on a lit country token"),
    ("brass", "walnut-dk", UI, "brass trim on the table (non-text)"),
    ("walnut-dk", "brass", TEXT, "engraved lettering on brass plaques and stage coins"), ("walnut-dk", "lit", TEXT, "the current stage coin"),
    ("lit", "un-blue-dk", TEXT, "gold lettering on the board's banner"), ("white", "un-blue-dk", TEXT, "the committee on the banner"),
    ("parchment", "un-blue", TEXT, "stage names on the banner"), ("walnut-dk", "parchment", TEXT, "the agenda ribbon"),
    ("white", "wood", TEXT, "an abstain band on a token"), ("parchment", "brass-dk", LARGE, "large lettering on dark brass"),
    # Tokens on the board (D-093): the country code on its regional group's band, and alignment shield monograms.
    ("walnut-dk", "reg-afr", TEXT, "code on an African Group band"), ("walnut-dk", "reg-apg", TEXT, "code on an Asia-Pacific band"),
    ("walnut-dk", "reg-eeg", TEXT, "code on an Eastern European band"), ("walnut-dk", "reg-grulac", TEXT, "code on a Latin American band"),
    ("walnut-dk", "reg-weog", TEXT, "code on a Western European band"), ("white", "un-blue-dk", TEXT, "NATO shield"),
    ("white", "maroon", TEXT, "ASEAN shield"), ("white", "felt", TEXT, "Arab League shield"), ("white", "brass-dk", TEXT, "BRICS shield"),
    ("white", "sea-lt", TEXT, "small island states shield"), ("white", "walnut", TEXT, "G20 shield"),
    # The speech coach (D-100)
    ("ink", "hl-repeat", TEXT, "a repeated word marked in the writing"), ("ink", "hl-filler", TEXT, "a filler word marked"),
    ("ink", "hl-long", TEXT, "a long sentence marked"), ("ink", "hl-tech", TEXT, "a persuasive technique marked"),
    ("ink", "lit", TEXT, "the word being read aloud"), ("un-blue", "hl-long", UI, "a long sentence's underline (non-text)"),
    ("time-go", "white", 1.0, "the coach's time dial on target (decorative; the words say it)"),
]


def luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)
