"""Single player on the board (D-099).

Ben: single player "with board game, pushed through to the student login section (it shouldn't require a code to use
and should be available as guest as well. (although with login used it should be able to save progress etc)". He
chose: nothing kept for guests; the full board table.

One game, two ways to keep it:
- a signed-in student plays their own solo committee (D-097) through the practice engine, and every conversation,
  reading, amendment and vote is saved to their runs;
- a guest plays the same game against a shared, hidden committee for the scenario (`committee.guest_pack`). Their
  game lives in the browser tab and is sent with each move; the server works out the answer and forgets it. Nothing
  about a guest is written down.
"""
from __future__ import annotations

import json
import random

from app.db import Writer, one, rows, scalar
from app.errors import UserError
from app.modules.sim import service as SIM

LIMIT = SIM.LOBBY_LIMIT
VOTES = ("yes", "abstain", "no")


def guest_committee(w: Writer, code: str) -> int:
    """The scenario's shared committee for guests, made the first time anyone plays it as a guest."""
    from app.modules.mun.packfile import install
    have = scalar(w.conn, "SELECT id FROM committee WHERE guest_pack = ? AND deleted_at IS NULL ORDER BY id LIMIT 1", (code,))
    if have:
        return have
    info = install(w, code, None, name_suffix=" · guest play")
    w.update("committee", info["committee_id"], {"guest_pack": code})
    return info["committee_id"]


def operative_ids(conn, committee_id: int) -> list[int]:
    return [r["id"] for r in rows(conn, "SELECT p.id FROM paragraph p JOIN resolution r ON r.id = p.resolution_id WHERE r.committee_id = ? "
                                        "AND p.kind = 'operative' AND p.deleted_at IS NULL AND r.deleted_at IS NULL ORDER BY p.position",
                                  (committee_id,))]


def guest_game(conn, code: str, iso3: str, seed: int, paragraph_id: int, tags: list[str] | None = None) -> dict:
    """A guest's game as the engine sees it: checked against the scenario's guest committee, never trusted blindly."""
    cid = scalar(conn, "SELECT id FROM committee WHERE guest_pack = ? AND deleted_at IS NULL ORDER BY id LIMIT 1", (code,))
    if not cid or paragraph_id not in operative_ids(conn, cid):
        raise UserError("That game isn't available. Start again from Play solo.", 404)
    if not one(conn, "SELECT 1 FROM delegation WHERE committee_id = ? AND iso3 = ? AND deleted_at IS NULL", (cid, iso3)):
        raise UserError("Choose a country that sits on this committee.")
    if not isinstance(seed, int) or not 1 <= seed < 2 ** 31:
        raise UserError("That game isn't available. Start again from Play solo.")
    allowed = set(topic_tags(conn, cid))
    base = one(conn, "SELECT v.tags FROM paragraph p JOIN paragraph_version v ON v.id = p.current_version_id WHERE p.id = ?",
               (paragraph_id,))["tags"] or ""
    use = [t for t in (tags if tags is not None else base.split(",")) if t in allowed]
    if not use:
        raise UserError("A clause needs at least one thing it commits countries to.")
    return {"id": None, "committee_id": cid, "paragraph_id": paragraph_id, "seed": seed, "tags": ",".join(use), "stage": "lobbying",
            "iso3": iso3}


def topic_tags(conn, committee_id: int) -> dict:
    topic_id = scalar(conn, "SELECT topic_id FROM committee WHERE id = ?", (committee_id,))
    return {r["code"]: r["label"] for r in rows(conn, "SELECT code, label FROM tag WHERE topic_id IS ? AND deleted_at IS NULL ORDER BY code",
                                                 (topic_id,))}


def readings_sources(conn, readings: list[dict]) -> dict:
    """A guest's own readings as practice-only sources, like a signed-in student's (SIM.readings_as_sources)."""
    from app.engine.model import Source
    wgt = scalar(conn, "SELECT weight FROM source_type WHERE code = 'student_intel'") or 2.0
    out: dict[str, list] = {}
    for i, r in enumerate(readings):
        pos = r.get("position")
        if isinstance(pos, int) and -2 <= pos <= 2 and isinstance(r.get("iso3"), str):
            out.setdefault(r["iso3"], []).append(Source(float(pos), float(wgt), "student_intel", "Practice lobbying (your reading)",
                                                        f"guest:{i}", False, ""))
    return out


def chance(conn, game: dict, readings: list[dict]) -> dict:
    """The whip count: how likely the clause is to pass, from the engine plus the player's own readings."""
    from app.modules.mun.predict import run_prediction
    r = run_prediction(conn, "paragraph", game["paragraph_id"], runs=1200, seed=game["seed"],
                       tags_override=[t for t in game["tags"].split(",") if t], extra_sources=readings_sources(conn, readings))
    res = r["result"]
    return {"p_pass": round(res.p_pass, 3), "yes_mean": round(res.yes_mean, 1), "yes_lo": res.yes_lo, "yes_hi": res.yes_hi}


def clean_lobbies(conn, game: dict, lobbies) -> list[dict]:
    """A guest's conversations as sent back by their browser: only countries on the committee, at most the limit."""
    names = {r["iso3"] for r in rows(conn, "SELECT iso3 FROM delegation WHERE committee_id = ? AND deleted_at IS NULL", (game["committee_id"],))}
    out = []
    for x in (lobbies or [])[:LIMIT]:
        if not isinstance(x, dict) or x.get("iso3") not in names or x.get("iso3") == game["iso3"]:
            continue
        pos = x.get("position")
        out.append({"iso3": x["iso3"], "position": pos if isinstance(pos, int) and -2 <= pos <= 2 else None,
                    "tags": ",".join(t for t in str(x.get("tags") or "").split(",") if t in topic_tags(conn, game["committee_id"])),
                    "heard": str(x.get("heard") or "")[:300]})
    return out


def guest_vote(conn, game: dict, my_vote: str, lobbies: list[dict]) -> dict:
    if my_vote not in VOTES:
        raise UserError("Cast your own country's vote first: yes, no or abstain.")
    before = chance(conn, {**game, "tags": game["tags"]}, [])["p_pass"]
    return SIM.practice_result(conn, game, {game["iso3"]: my_vote}, lobbies, before)


def new_seed() -> int:
    return random.SystemRandom().randrange(1, 2 ** 31)


def saved_state(conn, p: dict, student_id: int) -> dict:
    """A signed-in student's saved game, in the shape the board page plays from."""
    me = one(conn, "SELECT iso3, vote FROM sim_practice_member WHERE practice_id = ? AND student_id = ?", (p["id"], student_id))
    lobbies = [{"id": r["id"], "iso3": r["iso3"], "heard": r["heard"], "position": r["position"], "tags": r["tags"]}
               for r in rows(conn, "SELECT * FROM sim_practice_lobby WHERE practice_id = ? AND student_id = ? ORDER BY id", (p["id"], student_id))]
    return {"mode": "saved", "pid": p["id"], "iso3": me["iso3"], "my_vote": me["vote"], "tags": [t for t in (p["tags"] or "").split(",") if t],
            "lobbies": lobbies, "stage": p["stage"], "result": json.loads(p["result_json"]) if p["result_json"] else None}
