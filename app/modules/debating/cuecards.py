"""Cue cards (D-087): a written speech laid out as printable, cut-out cards, as dot points or as the full speech.

Nothing here writes for the student. Full cards are their own words split at sentence ends so each card is short
enough to glance at. Dot points are their own sentences shortened: leading filler ("Firstly,", "I believe that")
is dropped and each point is cut to its first few words. They are a starting point the student edits before
printing (Ben chose "auto, then editable").
"""
from __future__ import annotations

import hashlib
import json
import re

FULL_WORDS = 55          # most words on a full-speech card: about 25 seconds out loud
DOT_WORDS = 9            # most words in a dot point
DOTS_PER_CARD = 5

_SENT = re.compile(r"(?<=[.!?…])[\"')\]]*\s+(?=[\"'(\[]?[A-Z0-9])")
_FILLER = [
    "ladies and gentlemen", "honourable chair", "honorable chair", "madam chair", "mr chair", "chair", "fellow delegates",
    "distinguished delegates", "good morning", "good afternoon", "good evening", "hello everyone", "thank you",
    "firstly", "first of all", "secondly", "thirdly", "finally", "lastly", "in conclusion", "to conclude", "to sum up",
    "furthermore", "moreover", "additionally", "in addition", "also", "however", "therefore", "so", "and", "but",
    "i believe that", "i think that", "i would like to", "i'd like to", "i want to", "we believe that", "we think that",
    "it is clear that", "it's clear that", "the fact is that", "basically", "obviously", "clearly", "today",
]
_FILLER_RE = re.compile(r"^(?:(?:" + "|".join(re.escape(f) for f in sorted(_FILLER, key=len, reverse=True)) + r")\b[\s,:;—-]*)+", re.I)


def sentences(text: str) -> list[str]:
    text = " ".join((text or "").split())
    return [s.strip() for s in _SENT.split(text) if s.strip()] if text else []


def paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n|\r\n\s*\r\n", (text or "").replace("\r\n", "\n")) if p.strip()]


def dot(sentence: str) -> str:
    """One sentence as a short dot point: filler dropped, cut to its first few words."""
    s = _FILLER_RE.sub("", sentence.strip()).strip()
    if not re.search(r"\w", s):              # all greeting ("Honourable chair, fellow delegates."): keep it as written
        s = sentence.strip()
    s = s[0].upper() + s[1:] if s else s
    words = s.split()
    if len(words) > DOT_WORDS:
        return " ".join(words[:DOT_WORDS]).rstrip(",;:—-") + " …"
    return s.rstrip(".")


def _pack(chunks: list[str], limit: int) -> list[str]:
    """Join sentences into cards of at most `limit` words, never splitting a sentence unless it alone is too long."""
    cards, cur, n = [], [], 0
    for c in chunks:
        w = len(c.split())
        if w > limit:
            if cur:
                cards.append(" ".join(cur))
                cur, n = [], 0
            words = c.split()
            cards.extend(" ".join(words[i:i + limit]) for i in range(0, len(words), limit))
            continue
        if n + w > limit and cur:
            cards.append(" ".join(cur))
            cur, n = [], 0
        cur.append(c)
        n += w
    if cur:
        cards.append(" ".join(cur))
    return cards


def build(sections: list[tuple[str, str]], mode: str) -> list[dict]:
    """Cards for (heading, text) sections. Each card: {"heading", "body"}; dot-point bodies are one point per line.
    A heading goes on its section's first card; later cards in the section say "(continued)"."""
    out: list[dict] = []
    for heading, text in sections:
        if not (text or "").strip():
            continue
        if mode == "dots":
            points = [dot(s) for p in paragraphs(text) for s in sentences(p)]
            bodies = ["\n".join(points[i:i + DOTS_PER_CARD]) for i in range(0, len(points), DOTS_PER_CARD)]
        else:
            bodies = []
            for p in paragraphs(text):
                bodies.extend(_pack(sentences(p), FULL_WORDS))
            # Short neighbouring paragraphs share a card.
            merged: list[str] = []
            for b in bodies:
                if merged and len(merged[-1].split()) + len(b.split()) <= FULL_WORDS:
                    merged[-1] += "\n\n" + b
                else:
                    merged.append(b)
            bodies = merged
        for i, b in enumerate(bodies):
            out.append({"heading": heading if i == 0 else (f"{heading} (continued)" if heading else ""), "body": b})
    return out


def fingerprint(sections: list[tuple[str, str]]) -> str:
    """Changes when the speech changes, so edited cards can say they're out of date."""
    return hashlib.sha256(json.dumps(sections, ensure_ascii=False).encode()).hexdigest()[:16]



# ---------- where the speech comes from, and edited cards ----------

SOURCES = {"speech": "Speech", "case": "Debate case", "mun": "Model UN speech"}
MODES = {"dots": "Dot points", "full": "Full speech"}
MAX_CARDS = 60


def _sentence(text: str) -> str:
    t = " ".join((text or "").split())
    return t if not t or t[-1] in ".!?…" else t + "."


def source(conn, actor, kind: str, sid: int) -> dict:
    """The speech to make cards from, after checking it is this student's own. Returns its title, (heading, text)
    sections, and where to go back to."""
    from app.db import one
    from app.errors import UserError
    from app.modules.debating import prep as P
    if actor is None or actor.kind != "student":
        raise UserError("Cue cards are made by the student who wrote the speech.", 403)
    if kind == "speech":
        sp = P.get_speech(conn, actor, sid)
        v = P.speech_view(conn, sp)
        return {"title": sp["title"], "sections": [(s["label"] if len(v["sections"]) > 1 else "", s["text"]) for s in v["sections"]],
                "back": f"/me/prep/speeches/{sid}", "back_label": sp["title"]}
    if kind == "case":
        case = P.get_case(conn, actor, sid)
        if (case["speech_text"] or "").strip():
            secs = [("", case["speech_text"])]
        else:
            # No speech written out yet: cards from the case itself, one section per argument and rebuttal.
            v = P.case_view(conn, case)
            secs = [("Team line", case["team_line"])] if case["team_line"].strip() else []
            for i, p in enumerate(v["arguments"], 1):
                d = p["parts_d"]
                secs.append((f"Argument {i}", " ".join(_sentence(d.get(k, "")) for k in ("claim", "reason", "evidence", "impact"))))
            for p in v["custom"] + [a["rebuttal"] for a in v["opposition"] if a.get("rebuttal")]:
                d = p["parts_d"]
                secs.append(("Rebuttal", " ".join(_sentence(d.get(k, "")) for k in ("they_say", "flaw", "support", "impact"))))
        return {"title": f"{P.SIDES[case['side']]}: {case['motion']}", "sections": secs,
                "back": f"/me/prep/cases/{sid}", "back_label": f"{P.SIDES[case['side']]} case"}
    if kind == "mun":
        d = one(conn, "SELECT sd.*, cm.name AS committee FROM speech_draft sd JOIN committee cm ON cm.id = sd.committee_id "
                      "WHERE sd.id = ? AND sd.deleted_at IS NULL", (sid,))
        if not d or d["student_id"] != actor.id:
            raise UserError("That speech isn't yours to make cards from.", 404 if not d else 403)
        return {"title": d["title"], "sections": [("", d["body"])], "back": f"/me/committees/{d['committee_id']}/prepare",
                "back_label": d["committee"]}
    raise UserError("Unknown kind of speech.", 404)


def _saved(conn, student_id: int, kind: str, sid: int, mode: str) -> dict | None:
    from app.db import one
    return one(conn, "SELECT * FROM cue_card_set WHERE student_id = ? AND source = ? AND source_id = ? AND mode = ? "
                     "AND deleted_at IS NULL ORDER BY id DESC LIMIT 1", (student_id, kind, sid, mode))


def cards_for(conn, actor, kind: str, sid: int, mode: str) -> dict:
    """The cards to show: the student's edited set if there is one, else fresh from the speech."""
    src = source(conn, actor, kind, sid)
    mode = mode if mode in MODES else "dots"
    fp = fingerprint(src["sections"])
    saved = _saved(conn, actor.id, kind, sid, mode)
    cards = json.loads(saved["cards"]) if saved else build(src["sections"], mode)
    return {**src, "kind": kind, "sid": sid, "mode": mode, "cards": cards, "edited": bool(saved),
            "stale": bool(saved) and saved["fingerprint"] != fp, "fingerprint": fp}


def save_cards(w, actor, kind: str, sid: int, mode: str, form) -> int:
    """Keep the student's edits. Empty cards are dropped; a card is a heading and its text."""
    from app.errors import UserError
    from app.util import now_iso
    view = cards_for(w.conn, actor, kind, sid, mode)
    cards = []
    for i in range(MAX_CARDS + 1):
        h, b = (form.get(f"h_{i}") or "").strip()[:120], (form.get(f"b_{i}") or "").strip()
        if len(b) > 1500:
            raise UserError(f"Card {i + 1} is too long to read at a glance (over 1,500 characters). Split it into two cards.")
        if h or b:
            cards.append({"heading": h, "body": b})
    if len(cards) > MAX_CARDS:
        raise UserError(f"Up to {MAX_CARDS} cards.")
    saved = _saved(w.conn, actor.id, kind, sid, view["mode"])
    row = {"cards": json.dumps(cards, ensure_ascii=False), "fingerprint": view["fingerprint"], "updated_at": now_iso()}
    if saved:
        w.update("cue_card_set", saved["id"], row)
        return saved["id"]
    return w.insert("cue_card_set", {"student_id": actor.id, "source": kind, "source_id": sid, "mode": view["mode"], **row})


def rebuild(w, actor, kind: str, sid: int, mode: str) -> None:
    """Throw away edits and make the cards fresh from the speech as it is now."""
    source(w.conn, actor, kind, sid)                        # ownership check
    saved = _saved(w.conn, actor.id, kind, sid, mode)
    if saved:
        w.soft_delete("cue_card_set", saved["id"])


# How much fits on one printed card (measured on A4 landscape, four to a page, 30 Oct 2026).
PRINT_FIT = {("dots", False): 5, ("dots", True): 3, ("full", False): 58, ("full", True): 34}


def fit_for_print(cards: list[dict], mode: str, large: bool) -> list[dict]:
    """Split any card that wouldn't fit on paper (large text, or a long edited card) so nothing is cut off."""
    cap = PRINT_FIT[(mode, large)]
    out = []
    for c in cards:
        if mode == "dots":
            lines = [x for x in c["body"].splitlines() if x.strip()]
            parts = ["\n".join(lines[i:i + cap]) for i in range(0, len(lines), cap)] or [""]
        else:
            parts = [p for para in c["body"].split("\n\n") for p in _pack(sentences(para), cap)] or [""]
            merged: list[str] = []
            for p in parts:
                if merged and len(merged[-1].split()) + len(p.split()) <= cap:
                    merged[-1] += "\n\n" + p
                else:
                    merged.append(p)
            parts = merged
        for i, p in enumerate(parts):
            out.append({"heading": c["heading"] if i == 0 else (f"{c['heading']} (continued)" if c["heading"] else ""), "body": p})
    return out


def target_seconds(conn, kind: str, sid: int, sections: list[tuple[str, str]]) -> int:
    """The time to rehearse against: a prepared speech's own target, otherwise the speech's length at a steady pace,
    rounded up to the next half minute (at least one minute)."""
    from app.db import scalar
    from app.modules.debating.prep import WPM
    if kind == "speech":
        t = scalar(conn, "SELECT target_seconds FROM prep_speech WHERE id = ?", (sid,))
        if t:
            return int(t)
    words = sum(len((text or "").split()) for _, text in sections)
    return max(60, -(-round(words / WPM * 60) // 30) * 30)
