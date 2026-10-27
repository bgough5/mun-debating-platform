"""Committee flow v4 (D-068): the open floor and the tools students use on it.

The room leads: speeches, motions and negotiation happen out loud. The program records what the chair decides and
shows the same state on every screen. This module holds what the floor adds to the Phase 6 session:

- amendments: private drafts, submitted (public, shown as tracked changes), signatories, suggested edits that the
  sponsors accept or decline, the chair bringing one to the floor, speakers for and against, the vote;
- points (order, personal privilege, parliamentary inquiry, right of reply), raised aloud or from a device;
- messages between delegations: notes passed across the room, not assessed, readable by the chair;
- a student's own speech drafts (the program never writes them);
- friends and foes: each student's own reading of every delegation on every operative clause, beside the engine's
  estimate, which is labelled as an estimate with its evidence quality;
- voting procedure: roll-call order, and reopening the floor with another draft after a failed vote.
"""
from __future__ import annotations

import difflib
import html
import math
import random
import re
from datetime import datetime, timezone

from markupsafe import Markup

from app.db import Writer, one, rows, scalar
from app.errors import UserError
from app.util import display_name, now, now_iso

UNMOD_MAX_S = 600                    # an unmoderated caucus is at most 10 minutes per motion (Ben, D-068)
POINT_KINDS = {"order": "Point of order", "privilege": "Point of personal privilege",
               "inquiry": "Point of parliamentary inquiry", "reply": "Right of reply"}
MESSAGE_MAX = 500
MESSAGES_PER_MINUTE = 10
SPEECH_MAX = 6000
SPEECH_KINDS = {"opening": "Opening statement", "speech": "Speech", "notes": "Notes"}
STANCES = ("friend", "undecided", "foe")


def ch(sid: int) -> str:
    return f"session:{sid}"


def inbox_channel(delegation_id: int) -> str:
    return f"inbox:{delegation_id}"


def chat_channel(sid: int) -> str:
    return f"chat:{sid}"


def resolution_channel(rid: int) -> str:
    return f"resolution:{rid}"


def committee_channel(cid: int) -> str:
    return f"committee:{cid}"


# ---------------- tracked changes ----------------

_TOKENS = re.compile(r"\s+|[^\s]+")


def diff_html(old: str, new: str) -> Markup:
    """Word-level tracked changes: deletions in <del>, insertions in <ins>. Text is escaped."""
    a, b = _TOKENS.findall(old or ""), _TOKENS.findall(new or "")
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            out.append(html.escape("".join(a[i1:i2])))
            continue
        if op in ("delete", "replace"):
            out.append(f"<del>{html.escape(''.join(a[i1:i2]))}</del>")
        if op in ("insert", "replace"):
            out.append(f"<ins>{html.escape(''.join(b[j1:j2]))}</ins>")
    return Markup("".join(out))


# ---------------- amendments ----------------

def signatories_needed(conn, committee_id: int) -> int:
    """One fifth of the delegations that have students, at least two (D-068). Computed seats can't sign, so counting
    them would make the threshold unreachable in a class (one fifth of 33 GA seats is 7; a class may hold 8)."""
    n = scalar(conn, "SELECT COUNT(*) FROM delegation d WHERE d.committee_id = ? AND d.deleted_at IS NULL AND EXISTS "
                     "(SELECT 1 FROM delegation_member dm WHERE dm.delegation_id = d.id AND dm.deleted_at IS NULL)", (committee_id,)) or 0
    return max(2, math.ceil(n / 5))


def _amendment(conn, aid: int) -> dict:
    a = one(conn, "SELECT a.*, p.resolution_id, p.position, p.kind AS pkind, p.current_version_id, r.committee_id, r.title AS resolution, "
                  "cv.text AS current_text, bv.text AS base_text, c.name AS sponsor_name, d.iso3 AS sponsor_iso3 FROM amendment a "
                  "JOIN paragraph p ON p.id = a.paragraph_id JOIN resolution r ON r.id = p.resolution_id "
                  "JOIN paragraph_version cv ON cv.id = p.current_version_id JOIN paragraph_version bv ON bv.id = a.base_version_id "
                  "LEFT JOIN delegation d ON d.id = a.sponsor_delegation_id LEFT JOIN country c ON c.iso3 = d.iso3 "
                  "WHERE a.id = ? AND a.deleted_at IS NULL", (aid,))
    if not a:
        raise UserError("That amendment doesn't exist.", 404)
    return a


def _supports(conn, aid: int) -> list[dict]:
    return rows(conn, "SELECT s.*, d.iso3, c.name FROM amendment_support s JOIN delegation d ON d.id = s.delegation_id "
                      "JOIN country c ON c.iso3 = d.iso3 WHERE s.amendment_id = ? AND s.deleted_at IS NULL ORDER BY s.seq", (aid,))


def sponsors_of(conn, aid: int) -> set[int]:
    a = one(conn, "SELECT sponsor_delegation_id FROM amendment WHERE id = ?", (aid,))
    ids = {r["delegation_id"] for r in rows(conn, "SELECT delegation_id FROM amendment_support WHERE amendment_id = ? "
                                                  "AND kind = 'sponsor' AND deleted_at IS NULL", (aid,))}
    if a and a["sponsor_delegation_id"]:
        ids.add(a["sponsor_delegation_id"])
    return ids


def amendment_state(a: dict, floor_id: int | None, signed: int, needed: int) -> tuple[str, str]:
    """(code, label) for where an amendment is in its life (figure 4 of the flow)."""
    if a["status"] == "passed":
        return "adopted", "Adopted"
    if a["status"] == "friendly":
        return "adopted", "Adopted as friendly"
    if a["status"] == "failed":
        return "rejected", "Rejected"
    if a["status"] == "withdrawn":
        return "withdrawn", "Withdrawn"
    if a["submitted_at"] is None:
        return "draft", "Draft (only the sponsors see it)"
    if floor_id == a["id"]:
        return "floor", "On the floor"
    if signed >= needed:
        return "ready", "Ready for the floor"
    return "submitted", f"Submitted: {signed} of {needed} signatories"


def amendment_view(conn, aid: int, floor_id: int | None = None, needed: int | None = None) -> dict:
    a = _amendment(conn, aid)
    sup = _supports(conn, aid)
    signed = len({s["delegation_id"] for s in sup if s["kind"] == "signatory"})
    needed = needed if needed is not None else signatories_needed(conn, a["committee_id"])
    code, label = amendment_state(a, floor_id, signed, needed)
    if a["kind"] == "replace":
        diff = diff_html(a["current_text"], a["proposed_text"])
    elif a["kind"] == "delete":
        diff = Markup(f"<del>{html.escape(a['current_text'])}</del>")
    else:
        diff = Markup(f"<ins>{html.escape(a['proposed_text'])}</ins>")
    sugg = rows(conn, "SELECT g.*, c.name AS country, d.iso3 FROM amendment_suggestion g JOIN delegation d ON d.id = g.delegation_id "
                      "JOIN country c ON c.iso3 = d.iso3 WHERE g.amendment_id = ? ORDER BY g.id", (aid,))
    for g in sugg:
        g["diff"] = diff_html(a["proposed_text"], g["proposed_text"])
    return {**a, "supports": sup, "signed": signed, "needed": needed, "state": code, "state_label": label, "diff": diff,
            "sponsor_ids": sponsors_of(conn, aid), "suggestions": sugg,
            "stale": a["kind"] != "add" and a["base_version_id"] != a["current_version_id"] and code not in ("adopted", "rejected"),
            "kind_label": {"replace": f"Change operative clause {a['position']}", "delete": f"Delete operative clause {a['position']}",
                           "add": f"Add a clause after clause {a['position']}"}[a["kind"]] if a["pkind"] == "operative" else
                          {"replace": f"Change preambular clause {a['position']}", "delete": f"Delete preambular clause {a['position']}",
                           "add": f"Add a clause after preambular clause {a['position']}"}[a["kind"]]}


def board(conn, committee_id: int, my_delegation_id: int | None = None, staff: bool = False,
          floor_id: int | None = None) -> list[dict]:
    """Every submitted amendment in the committee, plus drafts the viewer sponsors (or all drafts, for staff)."""
    ids = [r["id"] for r in rows(conn, "SELECT a.id FROM amendment a JOIN paragraph p ON p.id = a.paragraph_id "
                                       "JOIN resolution r ON r.id = p.resolution_id WHERE r.committee_id = ? AND a.deleted_at IS NULL "
                                       "AND p.deleted_at IS NULL AND (a.submitted_at IS NOT NULL OR ? OR a.sponsor_delegation_id = ? "
                                       "OR a.id IN (SELECT amendment_id FROM amendment_support WHERE delegation_id = ? AND kind = 'sponsor' "
                                       "AND deleted_at IS NULL)) ORDER BY r.id, p.kind = 'operative', p.position, a.id",
                                 (committee_id, int(staff), my_delegation_id or -1, my_delegation_id or -1))]
    needed = signatories_needed(conn, committee_id)
    if floor_id is None:
        floor_id = scalar(conn, "SELECT floor_amendment_id FROM live_session WHERE committee_id = ? AND state != 'closed' "
                                "ORDER BY id DESC LIMIT 1", (committee_id,))
    return [amendment_view(conn, i, floor_id, needed) for i in ids]


def _require_sponsor(conn, aid: int, delegation_id: int | None) -> dict:
    a = _amendment(conn, aid)
    if delegation_id is None or delegation_id not in sponsors_of(conn, aid):
        raise UserError("Only the amendment's sponsors can do that.", 403)
    return a


def edit_draft(w: Writer, aid: int, delegation_id: int | None, text: str, rationale: str, staff: bool = False) -> None:
    a = _amendment(w.conn, aid) if staff else _require_sponsor(w.conn, aid, delegation_id)
    if a["submitted_at"] is not None:
        raise UserError("This amendment has been submitted. Others can now suggest edits; the sponsors accept or decline them.")
    text = (text or "").strip()
    if a["kind"] != "delete" and not text:
        raise UserError("Type the proposed text.")
    w.update("amendment", aid, {"proposed_text": text[:4000], "rationale": (rationale or "")[:1000]},
             resolution_channel(a["resolution_id"]), action="draft_edited")


def submit(w: Writer, aid: int, delegation_id: int | None, staff: bool = False) -> None:
    a = _amendment(w.conn, aid) if staff else _require_sponsor(w.conn, aid, delegation_id)
    if a["submitted_at"] is not None:
        return
    w.update("amendment", aid, {"submitted_at": now_iso()}, resolution_channel(a["resolution_id"]), action="amendment_submitted")
    w.touch(committee_channel(a["committee_id"]))


def suggest(w: Writer, aid: int, delegation_id: int, student_id: int | None, text: str, note: str = "") -> int:
    a = _amendment(w.conn, aid)
    if a["submitted_at"] is None:
        raise UserError("That amendment is still a draft.")
    if a["status"] != "tabled":
        raise UserError("That amendment has already been decided.")
    if a["kind"] == "delete":
        raise UserError("An amendment that deletes a clause has no text to edit. Propose your own amendment instead.")
    if delegation_id in sponsors_of(w.conn, aid):
        raise UserError("You sponsor this amendment: edit it with your co-sponsors instead of suggesting.")
    if _on_floor(w.conn, aid):
        raise UserError("This amendment is on the floor: its text is fixed until the vote.")
    text = (text or "").strip()
    if not text or text == a["proposed_text"]:
        raise UserError("Change the text to suggest an edit.")
    if scalar(w.conn, "SELECT COUNT(*) FROM amendment_suggestion WHERE amendment_id = ? AND delegation_id = ? AND status = 'pending'",
              (aid, delegation_id)) >= 3:
        raise UserError("Your delegation already has three suggestions waiting on this amendment.")
    return w.insert("amendment_suggestion", {"amendment_id": aid, "delegation_id": delegation_id, "student_id": student_id,
                                             "proposed_text": text[:4000], "note": (note or "")[:300], "created_at": now_iso()},
                    resolution_channel(a["resolution_id"]))


def _on_floor(conn, aid: int) -> bool:
    return bool(scalar(conn, "SELECT 1 FROM live_session WHERE floor_amendment_id = ? AND state != 'closed'", (aid,)))


def decide_suggestion(w: Writer, sid_: int, accept: bool, delegation_id: int | None, staff: bool = False) -> None:
    g = one(w.conn, "SELECT * FROM amendment_suggestion WHERE id = ?", (sid_,))
    if not g or g["status"] != "pending":
        raise UserError("That suggestion has already been dealt with.")
    a = _amendment(w.conn, g["amendment_id"]) if staff else _require_sponsor(w.conn, g["amendment_id"], delegation_id)
    if accept:
        if a["status"] != "tabled" or _on_floor(w.conn, a["id"]):
            raise UserError("The amendment's text is fixed now (on the floor or decided).")
        w.update("amendment", a["id"], {"proposed_text": g["proposed_text"]}, resolution_channel(a["resolution_id"]),
                 action="suggestion_accepted")
    w.update("amendment_suggestion", sid_, {"status": "accepted" if accept else "declined", "decided_at": now_iso()},
             resolution_channel(a["resolution_id"]))


def withdraw_suggestion(w: Writer, sid_: int, delegation_id: int) -> None:
    g = one(w.conn, "SELECT g.*, p.resolution_id FROM amendment_suggestion g JOIN amendment a ON a.id = g.amendment_id "
                    "JOIN paragraph p ON p.id = a.paragraph_id WHERE g.id = ?", (sid_,))
    if not g or g["delegation_id"] != delegation_id or g["status"] != "pending":
        raise UserError("You can only withdraw your own pending suggestion.")
    w.update("amendment_suggestion", sid_, {"status": "withdrawn", "decided_at": now_iso()}, resolution_channel(g["resolution_id"]))


def bring_to_floor(w: Writer, sid: int, aid: int, override: bool = False) -> None:
    from app.modules.chair.service import get_session
    s = get_session(w.conn, sid)
    if s["state"] == "closed":
        raise UserError("This session is closed.", 409)
    v = amendment_view(w.conn, aid, s["floor_amendment_id"])
    if v["committee_id"] != s["committee_id"]:
        raise UserError("That amendment isn't in this committee.", 404)
    if v["state"] in ("draft", "adopted", "rejected", "withdrawn"):
        raise UserError(f"That amendment can't go to the floor: {v['state_label'].lower()}.")
    if v["state"] == "submitted" and not override:
        raise UserError(f"It has {v['signed']} of the {v['needed']} signatories it needs. Tick “Bring it anyway” to override.")
    if s["current_division_id"]:
        raise UserError("Close the open vote first.")
    w.update("live_session", sid, {"floor_amendment_id": aid, "mode": "formal", "mode_topic": "", "stage": "floor"}, ch(sid),
             action="amendment_on_floor")
    _clear_side_lists(w, sid, keep=aid)


def clear_floor(w: Writer, sid: int) -> None:
    w.update("live_session", sid, {"floor_amendment_id": None}, ch(sid), action="amendment_off_floor")
    _clear_side_lists(w, sid)


def _clear_side_lists(w: Writer, sid: int, keep: int | None = None) -> None:
    for e in rows(w.conn, "SELECT id FROM speakers_list_entry WHERE session_id = ? AND status = 'waiting' AND amendment_id IS NOT NULL "
                          "AND amendment_id IS NOT ?", (sid, keep)):
        w.update("speakers_list_entry", e["id"], {"status": "withdrawn"}, ch(sid), action="withdraw")


def add_side_speaker(w: Writer, sid: int, delegation_id: int, student_id: int | None, side: str) -> int:
    from app.modules.chair.service import add_speaker, get_session
    if side not in ("for", "against"):
        raise UserError("Speak for or against the amendment.")
    s = get_session(w.conn, sid)
    if not s["floor_amendment_id"]:
        raise UserError("No amendment is on the floor.")
    if one(w.conn, "SELECT 1 FROM speakers_list_entry WHERE session_id = ? AND delegation_id = ? AND status = 'waiting' "
                   "AND amendment_id = ?", (sid, delegation_id, s["floor_amendment_id"])):
        raise UserError("Your delegation is already on the list for this amendment.")
    eid = add_speaker(w, sid, delegation_id, student_id, "general", amendment_id=s["floor_amendment_id"], side=side)
    return eid


def accept_friendly(w: Writer, sid: int | None, aid: int) -> None:
    from app.modules.mun.service import set_amendment_status
    a = _amendment(w.conn, aid)
    if a["submitted_at"] is None:
        raise UserError("Submit the amendment first.")
    set_amendment_status(w, aid, "friendly")
    if sid:
        w.log("amendment", aid, "friendly", None, {"amendment": aid}, ch(sid))
        s = one(w.conn, "SELECT floor_amendment_id FROM live_session WHERE id = ?", (sid,))
        if s and s["floor_amendment_id"] == aid:
            clear_floor(w, sid)


# ---------------- points ----------------

def raise_point(w: Writer, sid: int, delegation_id: int, student_id: int | None, kind: str, note: str = "") -> int:
    from app.modules.chair.service import get_session
    s = get_session(w.conn, sid)
    if s["state"] == "closed":
        raise UserError("This session is closed.", 409)
    if kind not in POINT_KINDS:
        raise UserError("Choose the kind of point.")
    if one(w.conn, "SELECT 1 FROM floor_point WHERE session_id = ? AND delegation_id = ? AND status = 'raised'", (sid, delegation_id)):
        raise UserError("Your delegation already has a point waiting. The chair will come to it.")
    if s["stage"] == "voting_procedure" and kind not in ("order", "privilege"):
        raise UserError("In voting procedure only points of order and personal privilege are in order.")
    return w.insert("floor_point", {"session_id": sid, "delegation_id": delegation_id, "student_id": student_id, "kind": kind,
                                    "note": " ".join((note or "").split())[:200], "created_at": now_iso()}, ch(sid))


def decide_point(w: Writer, point_id: int, status: str) -> None:
    p = one(w.conn, "SELECT * FROM floor_point WHERE id = ?", (point_id,))
    if not p or p["status"] != "raised":
        raise UserError("That point has already been dealt with.")
    if status not in ("answered", "granted", "declined"):
        raise UserError("Answer, grant or decline the point.")
    if status == "granted" and p["kind"] != "reply":
        status = "answered"
    w.update("floor_point", point_id, {"status": status, "decided_at": now_iso()}, ch(p["session_id"]), action=f"point_{status}")
    if status == "granted":
        # A right of reply goes to the top of the current list.
        from app.modules.chair.service import add_speaker, current_list, get_session
        kind, amendment = current_list(get_session(w.conn, p["session_id"]))
        try:
            eid = add_speaker(w, p["session_id"], p["delegation_id"], p["student_id"], kind, amendment_id=amendment)
            top = scalar(w.conn, "SELECT MIN(position) FROM speakers_list_entry WHERE session_id = ? AND status = 'waiting'",
                         (p["session_id"],)) or 1
            w.update("speakers_list_entry", eid, {"position": top - 1}, ch(p["session_id"]), action="reorder")
        except UserError:
            pass                     # already waiting on the list


def withdraw_point(w: Writer, point_id: int, delegation_id: int) -> None:
    p = one(w.conn, "SELECT * FROM floor_point WHERE id = ?", (point_id,))
    if not p or p["delegation_id"] != delegation_id or p["status"] != "raised":
        raise UserError("You can only withdraw your own waiting point.")
    w.update("floor_point", point_id, {"status": "withdrawn", "decided_at": now_iso()}, ch(p["session_id"]))


def points(conn, sid: int, open_only: bool = True, limit: int = 30) -> list[dict]:
    q = ("SELECT fp.*, d.iso3, c.name AS country, st.first_name, st.last_initial FROM floor_point fp "
         "JOIN delegation d ON d.id = fp.delegation_id JOIN country c ON c.iso3 = d.iso3 LEFT JOIN student st ON st.id = fp.student_id "
         "WHERE fp.session_id = ?")
    if open_only:
        q += " AND fp.status = 'raised' ORDER BY CASE fp.kind WHEN 'privilege' THEN 0 WHEN 'order' THEN 1 ELSE 2 END, fp.id"
    else:
        q += f" ORDER BY fp.id DESC LIMIT {int(limit)}"
    out = rows(conn, q, (sid,))
    for p in out:
        p["label"] = POINT_KINDS[p["kind"]]
        p["who"] = display_name(p["first_name"], p["last_initial"]) if p["first_name"] else ""
    return out


# ---------------- messages ----------------

def send_message(w: Writer, sid: int, from_delegation_id: int, from_student_id: int | None, to_delegation_id: int, body: str) -> int:
    from app.modules.chair.service import get_session
    s = get_session(w.conn, sid)
    if s["state"] == "closed":
        raise UserError("This session is closed.", 409)
    if s["stage"] == "voting_procedure":
        raise UserError("No notes during voting procedure: the doors are closed.")
    body = (body or "").strip()
    if not body:
        raise UserError("Type a message.")
    if len(body) > MESSAGE_MAX:
        raise UserError(f"Keep messages under {MESSAGE_MAX} characters.")
    if to_delegation_id == from_delegation_id:
        raise UserError("Choose another delegation to message.")
    to = one(w.conn, "SELECT id FROM delegation WHERE id = ? AND committee_id = ? AND deleted_at IS NULL", (to_delegation_id, s["committee_id"]))
    if not to:
        raise UserError("That delegation isn't in this committee.")
    if from_student_id is not None:
        cutoff = datetime.fromtimestamp(now() - 60, timezone.utc).isoformat(timespec="seconds")
        recent = scalar(w.conn, "SELECT COUNT(*) FROM delegate_message WHERE from_student_id = ? AND created_at > ?",
                        (from_student_id, cutoff))
        if recent >= MESSAGES_PER_MINUTE:
            raise UserError("That's a lot of messages in a minute. Wait a moment, or go and talk to them.")
    mid = w.insert("delegate_message", {"session_id": sid, "from_delegation_id": from_delegation_id, "from_student_id": from_student_id,
                                        "to_delegation_id": to_delegation_id, "body": body, "created_at": now_iso()},
                   inbox_channel(from_delegation_id))
    w.touch(inbox_channel(to_delegation_id), chat_channel(sid))
    return mid


def hide_message(w: Writer, mid: int, hidden: bool = True) -> None:
    m = one(w.conn, "SELECT * FROM delegate_message WHERE id = ?", (mid,))
    if not m:
        raise UserError("That message doesn't exist.", 404)
    w.update("delegate_message", mid, {"hidden_by": w.actor.label if hidden else None}, chat_channel(m["session_id"]),
             action="message_hidden" if hidden else "message_shown")
    w.touch(inbox_channel(m["from_delegation_id"]), inbox_channel(m["to_delegation_id"]))


_MSG_SELECT = ("SELECT m.*, fc.name AS from_country, fd.iso3 AS from_iso3, tc.name AS to_country, td.iso3 AS to_iso3, "
               "st.first_name, st.last_initial FROM delegate_message m JOIN delegation fd ON fd.id = m.from_delegation_id "
               "JOIN country fc ON fc.iso3 = fd.iso3 JOIN delegation td ON td.id = m.to_delegation_id JOIN country tc ON tc.iso3 = td.iso3 "
               "LEFT JOIN student st ON st.id = m.from_student_id ")


def _who(m: dict) -> dict:
    m["who"] = display_name(m["first_name"], m["last_initial"]) if m["first_name"] else ""
    return m


def inbox(conn, sid: int, delegation_id: int, limit: int = 60) -> list[dict]:
    """Messages to and from a delegation, newest first. Hidden messages show as hidden to the delegation."""
    return [_who(m) for m in rows(conn, _MSG_SELECT + "WHERE m.session_id = ? AND (m.from_delegation_id = ? OR m.to_delegation_id = ?) "
                                                       f"ORDER BY m.id DESC LIMIT {int(limit)}", (sid, delegation_id, delegation_id))]


def all_messages(conn, sid: int, limit: int = 300) -> list[dict]:
    return [_who(m) for m in rows(conn, _MSG_SELECT + f"WHERE m.session_id = ? ORDER BY m.id DESC LIMIT {int(limit)}", (sid,))]


# ---------------- speech drafts (the student's own words; private) ----------------

def drafts(conn, student_id: int, committee_id: int) -> list[dict]:
    return rows(conn, "SELECT * FROM speech_draft WHERE student_id = ? AND committee_id = ? AND deleted_at IS NULL "
                      "ORDER BY kind = 'opening' DESC, updated_at DESC", (student_id, committee_id))


def save_draft(w: Writer, student_id: int, committee_id: int, kind: str, title: str, body: str, draft_id: int | None = None) -> int:
    if kind not in SPEECH_KINDS:
        raise UserError("Choose what kind of speech this is.")
    body = (body or "").replace("\r\n", "\n")
    if len(body) > SPEECH_MAX:
        raise UserError(f"Keep a draft under {SPEECH_MAX} characters.")
    title = " ".join((title or "").split())[:80] or SPEECH_KINDS[kind]
    if draft_id:
        d = one(w.conn, "SELECT * FROM speech_draft WHERE id = ? AND deleted_at IS NULL", (draft_id,))
        if not d or d["student_id"] != student_id:
            raise UserError("That draft isn't yours.", 403)
        w.update("speech_draft", draft_id, {"title": title, "body": body, "kind": kind, "updated_at": now_iso()})
        return draft_id
    if kind == "opening":
        existing = scalar(w.conn, "SELECT id FROM speech_draft WHERE student_id = ? AND committee_id = ? AND kind = 'opening' "
                                  "AND deleted_at IS NULL", (student_id, committee_id))
        if existing:
            w.update("speech_draft", existing, {"title": title, "body": body, "updated_at": now_iso()})
            return existing
    if scalar(w.conn, "SELECT COUNT(*) FROM speech_draft WHERE student_id = ? AND committee_id = ? AND deleted_at IS NULL",
              (student_id, committee_id)) >= 20:
        raise UserError("You have 20 drafts for this committee. Delete one first.")
    return w.insert("speech_draft", {"student_id": student_id, "committee_id": committee_id, "kind": kind, "title": title,
                                     "body": body, "updated_at": now_iso()})


def delete_draft(w: Writer, student_id: int, draft_id: int) -> None:
    d = one(w.conn, "SELECT * FROM speech_draft WHERE id = ? AND deleted_at IS NULL", (draft_id,))
    if not d or d["student_id"] != student_id:
        raise UserError("That draft isn't yours.", 403)
    w.soft_delete("speech_draft", draft_id)


def words(text: str) -> int:
    return len((text or "").split())


def speaking_seconds(text: str, wpm: int = 130) -> int:
    """About how long the draft takes to say aloud, at a calm 130 words a minute."""
    return round(words(text) * 60 / wpm)


# ---------------- friends and foes ----------------

def operative_clauses(conn, committee_id: int) -> list[dict]:
    """Operative clauses only: the preamble is deliberately left out (Ben, D-068)."""
    return rows(conn, "SELECT p.id, p.position, r.id AS resolution_id, r.title, v.text, v.tags FROM paragraph p "
                      "JOIN resolution r ON r.id = p.resolution_id JOIN paragraph_version v ON v.id = p.current_version_id "
                      "WHERE r.committee_id = ? AND r.deleted_at IS NULL AND p.deleted_at IS NULL AND p.kind = 'operative' "
                      "ORDER BY r.id, p.position", (committee_id,))


def ff_sheet(conn, student_id: int, committee_id: int, paragraph_id: int, my_delegation_id: int | None) -> list[dict]:
    """Every other delegation with the student's own reading, and the engine's estimate beside it (labelled)."""
    from app.modules.mun.predict import run_prediction
    mine = {r["delegation_id"]: r for r in rows(conn, "SELECT * FROM ff_entry WHERE student_id = ? AND paragraph_id = ?",
                                                (student_id, paragraph_id))}
    pred = run_prediction(conn, "paragraph", paragraph_id, with_swing=False, runs=400)
    dist = {d.iso3: d for d in pred["dists"]}
    out = []
    for d in rows(conn, "SELECT d.id, d.iso3, c.name FROM delegation d JOIN country c ON c.iso3 = d.iso3 "
                        "WHERE d.committee_id = ? AND d.deleted_at IS NULL ORDER BY c.name", (committee_id,)):
        if d["id"] == my_delegation_id:
            continue
        e = mine.get(d["id"])
        g = dist.get(d["iso3"])
        est = None
        if g is not None:
            est = "friend" if g.p_yes >= 0.6 else "foe" if g.p_no >= 0.6 else "undecided"
        out.append({**d, "stance": e["stance"] if e else None, "note": e["note"] if e else "",
                    "p_yes": g.p_yes if g else None, "p_no": g.p_no if g else None, "estimate": est,
                    "quality": pred["quality"].get(d["iso3"], "unknown")})
    return out


def ff_save(w: Writer, student_id: int, paragraph_id: int, committee_id: int, entries: dict[int, tuple[str, str]]) -> int:
    valid = {r["id"] for r in rows(w.conn, "SELECT id FROM delegation WHERE committee_id = ? AND deleted_at IS NULL", (committee_id,))}
    if not one(w.conn, "SELECT 1 FROM paragraph p JOIN resolution r ON r.id = p.resolution_id WHERE p.id = ? AND r.committee_id = ? "
                       "AND p.kind = 'operative'", (paragraph_id, committee_id)):
        raise UserError("Choose an operative clause in this committee.")
    n = 0
    for did, (stance, note) in entries.items():
        if did not in valid or stance not in STANCES:
            continue
        note = " ".join((note or "").split())[:200]
        w.conn.execute("INSERT INTO ff_entry (student_id, paragraph_id, delegation_id, stance, note, updated_at) VALUES (?,?,?,?,?,?) "
                       "ON CONFLICT (student_id, paragraph_id, delegation_id) DO UPDATE SET stance = excluded.stance, "
                       "note = excluded.note, updated_at = excluded.updated_at", (student_id, paragraph_id, did, stance, note, now_iso()))
        n += 1
    if n:
        w.log("ff_entry", f"{student_id}:{paragraph_id}", "saved", None, {"entries": n})
    return n


def ff_summary(conn, student_id: int, committee_id: int) -> list[dict]:
    counts = {(r["paragraph_id"], r["stance"]): r["n"] for r in rows(
        conn, "SELECT paragraph_id, stance, COUNT(*) AS n FROM ff_entry WHERE student_id = ? GROUP BY paragraph_id, stance", (student_id,))}
    out = []
    for p in operative_clauses(conn, committee_id):
        out.append({**p, **{s: counts.get((p["id"], s), 0) for s in STANCES}})
    return out


# ---------------- voting procedure ----------------

def roll_call_order(conn, sid: int, committee_id: int) -> list[dict]:
    """Alphabetical order starting from a delegation drawn by lot, as in the General Assembly. Stable for the session."""
    ds = rows(conn, "SELECT d.id, d.iso3, c.name FROM delegation d JOIN country c ON c.iso3 = d.iso3 "
                    "WHERE d.committee_id = ? AND d.deleted_at IS NULL ORDER BY c.name", (committee_id,))
    if not ds:
        return []
    k = random.Random(sid).randrange(len(ds))
    return ds[k:] + ds[:k]


def set_resolution(w: Writer, sid: int, resolution_id: int) -> None:
    from app.modules.chair.service import get_session
    s = get_session(w.conn, sid)
    r = one(w.conn, "SELECT * FROM resolution WHERE id = ? AND committee_id = ? AND deleted_at IS NULL", (resolution_id, s["committee_id"]))
    if not r:
        raise UserError("That draft resolution isn't in this committee.")
    w.update("live_session", sid, {"resolution_id": resolution_id}, ch(sid), action="draft_on_floor")


def reopen_with_draft(w: Writer, sid: int, resolution_id: int) -> None:
    """After a failed vote, the floor reopens with another draft (figure 5)."""
    set_resolution(w, sid, resolution_id)
    w.update("live_session", sid, {"stage": "floor", "mode": "formal", "mode_topic": "", "floor_amendment_id": None}, ch(sid),
             action="floor_reopened")


def session_resolution(conn, s: dict) -> dict | None:
    if s.get("resolution_id"):
        r = one(conn, "SELECT * FROM resolution WHERE id = ?", (s["resolution_id"],))
        if r:
            return r
    return one(conn, "SELECT * FROM resolution WHERE committee_id = ? AND deleted_at IS NULL AND status NOT IN ('failed', 'withdrawn') "
                     "ORDER BY id LIMIT 1", (s["committee_id"],))
