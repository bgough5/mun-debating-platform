"""The live room (D-089): the gavel, raised placards, breaking news, and the markers that set off sounds and title
cards on the projector (app/static/js/effects.js).

Effects are triggered by state the server already has, so a projector that reconnects shows the room as it is and
never replays an old moment: the gavel is an event in the change log, a placard is a row until it is lowered, and
a news update is a row sent at a time.
"""
from __future__ import annotations

from app.db import Writer, one, rows, scalar
from app.errors import UserError
from app.modules.mun.who import label as who_label
from app.util import display_name, now_iso

GAVEL_ACTIONS = ("gavel", "opened", "session_closed")
FICTION = "Fictional scenario update: these events are invented for practice."


def ch(sid: int) -> str:
    return f"session:{sid}"


# ---------- gavel ----------

def gavel(w: Writer, sid: int, knocks: int = 2) -> None:
    w.log("live_session", sid, "gavel", None, {"knocks": max(1, min(int(knocks or 2), 3))}, ch(sid))


def last_gavel(conn, sid: int) -> tuple[int, int]:
    """(event sequence, knocks) of the latest gavel moment: a gavel, the session opening or closing."""
    marks = ",".join("?" * len(GAVEL_ACTIONS))
    r = one(conn, f"SELECT seq, action, after_json FROM event_log WHERE channel = ? AND action IN ({marks}) ORDER BY seq DESC LIMIT 1",
            (ch(sid), *GAVEL_ACTIONS))
    if not r:
        return 0, 2
    knocks = 3 if r["action"] != "gavel" else 2
    if r["action"] == "gavel" and r["after_json"] and '"knocks": 1' in r["after_json"]:
        knocks = 1
    return r["seq"], knocks


# ---------- placards ----------

def raised(conn, sid: int) -> list[dict]:
    """Placards up, in the order they went up."""
    out = rows(conn, "SELECT p.*, d.iso3, c.name AS country, c.flag_svg, st.first_name, st.last_initial FROM placard p "
                     "JOIN delegation d ON d.id = p.delegation_id JOIN country c ON c.iso3 = d.iso3 JOIN student st ON st.id = p.student_id "
                     "WHERE p.session_id = ? AND p.lowered_at IS NULL ORDER BY p.id", (sid,))
    for p in out:
        p["name"] = display_name(p["first_name"], p["last_initial"])
        p["by"] = who_label(p["name"], p["country"])
    return out


def raise_placard(w: Writer, sid: int, delegation_id: int, student_id: int) -> int:
    s = one(w.conn, "SELECT state FROM live_session WHERE id = ?", (sid,))
    if not s or s["state"] != "open":
        raise UserError("The session isn't open.", 409)
    mine = one(w.conn, "SELECT id FROM placard WHERE session_id = ? AND student_id = ? AND lowered_at IS NULL", (sid, student_id))
    if mine:
        return mine["id"]
    return w.insert("placard", {"session_id": sid, "delegation_id": delegation_id, "student_id": student_id, "raised_at": now_iso()}, ch(sid))


def lower_placard(w: Writer, sid: int, placard_id: int, by: str) -> None:
    p = one(w.conn, "SELECT * FROM placard WHERE id = ? AND session_id = ?", (placard_id, sid))
    if p and not p["lowered_at"]:
        w.update("placard", placard_id, {"lowered_at": now_iso(), "lowered_by": by}, ch(sid), action="placard_lowered")


def lower_mine(w: Writer, sid: int, student_id: int) -> None:
    for p in rows(w.conn, "SELECT id FROM placard WHERE session_id = ? AND student_id = ? AND lowered_at IS NULL", (sid, student_id)):
        lower_placard(w, sid, p["id"], "student")


def lower_all(w: Writer, sid: int) -> int:
    ps = rows(w.conn, "SELECT id FROM placard WHERE session_id = ? AND lowered_at IS NULL", (sid,))
    for p in ps:
        lower_placard(w, sid, p["id"], "chair")
    return len(ps)


# ---------- breaking news ----------

def topic_code(conn, sid: int) -> str:
    return scalar(conn, "SELECT t.code FROM live_session s JOIN committee cm ON cm.id = s.committee_id JOIN topic t ON t.id = cm.topic_id "
                        "WHERE s.id = ?", (sid,)) or ""


def next_script(conn, sid: int) -> dict | None:
    """The next scripted update for this committee's fictional crisis that hasn't been sent in this session."""
    return one(conn, "SELECT * FROM crisis_script WHERE topic_code = ? AND deleted_at IS NULL AND id NOT IN "
                     "(SELECT script_id FROM crisis_update WHERE session_id = ? AND script_id IS NOT NULL AND deleted_at IS NULL) "
                     "ORDER BY position, id LIMIT 1", (topic_code(conn, sid), sid))


def script_left(conn, sid: int) -> int:
    return scalar(conn, "SELECT COUNT(*) FROM crisis_script WHERE topic_code = ? AND deleted_at IS NULL AND id NOT IN "
                        "(SELECT script_id FROM crisis_update WHERE session_id = ? AND script_id IS NOT NULL AND deleted_at IS NULL)",
                  (topic_code(conn, sid), sid)) or 0


def send_news(w: Writer, sid: int, script_id: int | None = None, headline: str = "", body: str = "") -> int:
    s = one(w.conn, "SELECT state FROM live_session WHERE id = ?", (sid,))
    if not s or s["state"] == "closed":
        raise UserError("The session has closed.", 409)
    if script_id:
        sc = one(w.conn, "SELECT * FROM crisis_script WHERE id = ? AND deleted_at IS NULL", (script_id,))
        if not sc or sc["topic_code"] != topic_code(w.conn, sid):
            raise UserError("That update isn't part of this committee's scenario.", 404)
        headline, body, label = sc["headline"], sc["body"], FICTION
    else:
        headline, body = " ".join((headline or "").split())[:140], (body or "").strip()[:800]
        if len(headline) < 4:
            raise UserError("Write a headline for the update.")
        label = "From the chair."
    return w.insert("crisis_update", {"session_id": sid, "script_id": script_id, "headline": headline, "body": body, "label": label,
                                      "sent_at": now_iso()}, ch(sid))


def news(conn, sid: int, limit: int = 10) -> list[dict]:
    return rows(conn, "SELECT * FROM crisis_update WHERE session_id = ? AND deleted_at IS NULL ORDER BY id DESC LIMIT ?", (sid, limit))


# ---------- what the effects watch ----------

def reveal(conn, division_id: int | None) -> dict | None:
    """The last closed vote, country by country in roll-call order (alphabetical), for the projector's reveal."""
    if not division_id:
        return None
    dv = one(conn, "SELECT * FROM division WHERE id = ? AND status = 'closed'", (division_id,))
    if not dv:
        return None
    votes = rows(conn, "SELECT v.vote, v.computed, v.iso3, c.name FROM division_vote v JOIN country c ON c.iso3 = v.iso3 "
                       "WHERE v.division_id = ? ORDER BY c.name", (division_id,))
    labels = {"yes": "Yes", "no": "No", "abstain": "Abstain"}
    for v in votes:
        v["label"] = labels.get(v["vote"], "Absent") + (" *" if v["computed"] else "")
        v["vote"] = v["vote"] if v["vote"] in labels else "absent"
    return {**dv, "votes": votes}


def fx_state(conn, sid: int, view: dict) -> dict:
    seq, knocks = last_gavel(conn, sid)
    last = (view.get("recent") or [None])[0]
    return {"gavel": seq, "gavel_n": knocks, "result_id": last["id"] if last else None,
            "reveal": reveal(conn, last["id"]) if last else None, "news": (news(conn, sid, 1) or [None])[0],
            "stage_line": (view.get("sim") or {}).get("student_prompt") or "", "adopted": last_adopted(conn, sid)}


def last_adopted(conn, sid: int) -> dict | None:
    """The amendment most recently adopted in this session's committee, with the clause before and after (D-091),
    for the projector's "Amendment adopted" moment. Only adoptions since the session opened count."""
    s = one(conn, "SELECT committee_id, created_at FROM live_session WHERE id = ?", (sid,))
    if not s:
        return None
    a = one(conn, "SELECT a.*, p.kind AS pkind, p.position, p.current_version_id, MAX(e.seq) AS seq FROM amendment a "
                  "JOIN paragraph p ON p.id = a.paragraph_id JOIN resolution r ON r.id = p.resolution_id "
                  "JOIN event_log e ON e.entity = 'amendment' AND e.entity_id = CAST(a.id AS TEXT) "
                  "WHERE r.committee_id = ? AND a.status IN ('passed', 'friendly') AND e.at >= ? "
                  "GROUP BY a.id ORDER BY seq DESC LIMIT 1", (s["committee_id"], s["created_at"]))
    if not a:
        return None
    if a["kind"] == "replace":
        before = scalar(conn, "SELECT pv0.text FROM paragraph_version pv JOIN paragraph_version pv0 ON pv0.id = pv.parent_version_id "
                              "WHERE pv.paragraph_id = ? AND pv.author_label = ? ORDER BY pv.id DESC LIMIT 1",
                        (a["paragraph_id"], f"Amendment {a['id']}")) or ""
        after = a["proposed_text"]
    elif a["kind"] == "delete":
        before = scalar(conn, "SELECT text FROM paragraph_version WHERE id = ?", (a["current_version_id"],)) or ""
        after = ""
    else:
        before, after = "", a["proposed_text"]
    clause = "operative" if a["pkind"] == "operative" else "preambular"
    label = {"replace": f"Change to {clause} clause {a['position']}", "delete": f"{clause.capitalize()} clause {a['position']} deleted",
             "add": f"New clause after {clause} clause {a['position']}"}[a["kind"]]
    return {"id": a["id"], "seq": a["seq"], "label": label, "before": before, "after": after,
            "friendly": a["status"] == "friendly"}
