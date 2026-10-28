"""Committee flow v4 (D-068): routes for the floor, the student tabs, the amendment board, friends and foes, and
the prepare page. Students act only for their own delegation; the chair's actions need staff who run the class."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.db import one, rows, scalar
from app.errors import UserError
from app.modules.chair import service as C
from app.modules.chair.routes import _manage, _student_session, session_view
from app.modules.floor import service as F
from app.util import display_name
from app.web.auth import committee_access, require_any, require_staff, require_student
from app.web.http import form_data, form_int, redirect
from app.web.templating import render

router = APIRouter()
TABS = ("floor", "motions", "points", "messages", "speech", "amendments", "friends")


def tab_of(request: Request) -> str:
    t = request.query_params.get("tab")
    return t if t in TABS else "floor"


def _mine(conn, actor, committee_id: int) -> dict | None:
    if actor is None or actor.kind != "student":
        return None
    return one(conn, "SELECT d.*, c.name FROM delegation d JOIN delegation_member dm ON dm.delegation_id = d.id "
                     "JOIN country c ON c.iso3 = d.iso3 WHERE dm.student_id = ? AND d.committee_id = ? "
                     "AND dm.deleted_at IS NULL AND d.deleted_at IS NULL", (actor.id, committee_id))


def _need_mine(conn, actor, committee_id: int) -> dict:
    m = _mine(conn, actor, committee_id)
    if not m:
        raise UserError("You aren't in a delegation in this committee yet. Ask your teacher.", 403)
    return m


def _student_act(request: Request, sid: int, tab: str, fn, msg: str):
    with request.app.state.db.write(request.state.actor) as w:
        s = _student_session(w.conn, request, sid)
        mine = _need_mine(w.conn, request.state.actor, s["committee_id"])
        out = fn(w, s, mine)
    return redirect(f"/live/{sid}?tab={tab}", out if isinstance(out, str) else msg)


def _chair_act(request: Request, sid: int, fn, msg: str = ""):
    with request.app.state.db.write(request.state.actor) as w:
        s = _manage(w.conn, request, sid)
        out = fn(w, s)
    return redirect(f"/chair/{sid}", out if isinstance(out, str) else msg)


def _safe_next(url: str | None, default: str) -> str:
    return url if url and url.startswith(("/live/", "/me/", "/mun/", "/chair/")) and "//" not in url and "\\" not in url else default


# ---------------- students: the floor tabs ----------------

def student_tabs_context(conn, request: Request, sid: int) -> dict:
    ctx = session_view(conn, sid, request.state.actor)
    s, mine = ctx["s"], ctx["mine"]
    ctx["tab"] = tab_of(request)
    ctx["point_kinds"] = F.POINT_KINDS
    ctx["ff"] = F.ff_summary(conn, request.state.actor.id, s["committee_id"]) if mine else []
    ctx["my_drafts"] = F.drafts(conn, request.state.actor.id, s["committee_id"]) if mine else []
    ctx["speech_kinds"] = F.SPEECH_KINDS
    return ctx


@router.get("/live/{sid}/f/messages")
def live_messages(request: Request, sid: int, sess=Depends(require_student)):
    with request.app.state.db.read() as conn:
        s = _student_session(conn, request, sid)
        mine = _mine(conn, request.state.actor, s["committee_id"])
        msgs = F.inbox(conn, sid, mine["id"]) if mine else []
        dels = rows(conn, "SELECT d.id, c.name FROM delegation d JOIN country c ON c.iso3 = d.iso3 WHERE d.committee_id = ? "
                          "AND d.deleted_at IS NULL ORDER BY c.name", (s["committee_id"],))
    return render(request, "floor/_messages.html", {"s": s, "mine": mine, "msgs": msgs, "dels": dels, "max_len": F.MESSAGE_MAX})


@router.post("/live/{sid}/messages")
def live_send(request: Request, sid: int, sess=Depends(require_student), form=Depends(form_data)):
    return _student_act(request, sid, "messages", lambda w, s, mine: F.send_message(
        w, sid, mine["id"], request.state.actor.id, form_int(form.get("to_delegation_id")), form.get("body") or "") and None,
        "Message sent. The chair can read messages.")


@router.post("/live/{sid}/points")
def live_point(request: Request, sid: int, sess=Depends(require_student), form=Depends(form_data)):
    return _student_act(request, sid, "points", lambda w, s, mine: F.raise_point(
        w, sid, mine["id"], request.state.actor.id, form.get("kind") or "", form.get("note") or "") and None,
        "Point raised. Raise your placard too: the chair will recognise you.")


@router.post("/live/{sid}/points/{pid}/withdraw")
def live_point_withdraw(request: Request, sid: int, pid: int, sess=Depends(require_student), form=Depends(form_data)):
    return _student_act(request, sid, "points", lambda w, s, mine: F.withdraw_point(w, pid, mine["id"]), "Point withdrawn.")


@router.post("/live/{sid}/side")
def live_side(request: Request, sid: int, sess=Depends(require_student), form=Depends(form_data)):
    side = form.get("side") or ""
    return _student_act(request, sid, "floor", lambda w, s, mine: F.add_side_speaker(w, sid, mine["id"], request.state.actor.id, side)
                        and None, f"You're on the list to speak {side} the amendment.")


@router.post("/live/{sid}/unmod")
def live_unmod(request: Request, sid: int, sess=Depends(require_student), form=Depends(form_data)):
    """One-tap motion for an unmoderated caucus (up to 10 minutes)."""
    def act(w, s, mine):
        pm = one(w.conn, "SELECT id FROM procedure_motion WHERE rule_set_id IS ? AND code = 'unmod' AND deleted_at IS NULL",
                 (s["procedure_rule_set_id"],))
        if not pm:
            raise UserError("This committee's rules of procedure have no unmoderated caucus.")
        minutes = form_int(form.get("minutes"), 0) or 0
        if not 1 <= minutes <= F.UNMOD_MAX_S // 60:
            raise UserError(f"Choose between 1 and {F.UNMOD_MAX_S // 60} minutes.")
        C.propose_motion(w, sid, pm["id"], mine["id"], minutes * 60, None, form.get("topic") or "")
    return _student_act(request, sid, "motions", act, "Motion raised. Raise your placard: the chair will ask for a second.")


# ---------------- students: speech drafts (private) ----------------

@router.post("/me/committees/{cid}/speeches")
def speech_save(request: Request, cid: int, sess=Depends(require_student), form=Depends(form_data)):
    nxt = _safe_next(form.get("next"), f"/me/committees/{cid}/prepare")
    with request.app.state.db.write(request.state.actor) as w:
        if committee_access(w.conn, request.state.actor, cid) == "none":
            raise UserError("That committee isn't for your class.", 403)
        _need_mine(w.conn, request.state.actor, cid)
        if form.get("delete"):
            F.delete_draft(w, request.state.actor.id, form_int(form.get("draft_id")))
            return redirect(nxt, "Draft deleted.")
        F.save_draft(w, request.state.actor.id, cid, form.get("kind") or "speech", form.get("title") or "", form.get("body") or "",
                     form_int(form.get("draft_id")))
    return redirect(nxt, "Saved. Only you can see your drafts.")


# ---------------- students: prepare, friends and foes ----------------

@router.get("/me/committees/{cid}/prepare")
def prepare(request: Request, cid: int, sess=Depends(require_student)):
    with request.app.state.db.read() as conn:
        if committee_access(conn, request.state.actor, cid) == "none":
            raise UserError("That committee isn't for your class.", 403)
        com = one(conn, "SELECT cm.*, cf.name AS conference, t.name AS topic, vr.name AS rule FROM committee cm "
                        "JOIN conference cf ON cf.id = cm.conference_id LEFT JOIN topic t ON t.id = cm.topic_id "
                        "JOIN voting_rule vr ON vr.id = cm.voting_rule_id WHERE cm.id = ?", (cid,))
        mine = _mine(conn, request.state.actor, cid)
        brief = _country_brief(conn, mine, com) if mine else None
        clauses = rows(conn, "SELECT p.id, p.kind, p.position, r.title, v.text FROM paragraph p JOIN resolution r ON r.id = p.resolution_id "
                             "JOIN paragraph_version v ON v.id = p.current_version_id WHERE r.committee_id = ? AND r.deleted_at IS NULL "
                             "AND p.deleted_at IS NULL ORDER BY r.id, p.kind = 'operative', p.position", (cid,))
        drafts = F.drafts(conn, request.state.actor.id, cid)
        live = scalar(conn, "SELECT id FROM live_session WHERE committee_id = ? AND state != 'closed' ORDER BY id DESC LIMIT 1", (cid,))
    opening = next((d for d in drafts if d["kind"] == "opening"), None)
    return render(request, "floor/prepare.html", {"title": f"Prepare: {com['name']}", "com": com, "mine": mine, "brief": brief,
                                                  "clauses": clauses, "drafts": drafts, "opening": opening, "live": live,
                                                  "words": F.words, "seconds": F.speaking_seconds})


def _country_brief(conn, mine: dict, com: dict) -> dict:
    blocs = rows(conn, "SELECT b.name FROM bloc b JOIN bloc_member bm ON bm.bloc_id = b.id WHERE bm.iso3 = ? AND b.deleted_at IS NULL "
                       "ORDER BY b.name", (mine["iso3"],))
    arch = rows(conn, "SELECT a.name, a.blurb, ca.weight FROM country_archetype ca JOIN archetype a ON a.id = ca.archetype_id "
                      "WHERE ca.iso3 = ? AND (ca.topic_id IS ? OR ca.topic_id IS NULL) ORDER BY ca.weight DESC LIMIT 2",
                (mine["iso3"], com["topic_id"]))
    ev = rows(conn, "SELECT e.*, st.label AS source_label, st.code AS source_code FROM evidence e "
                    "JOIN source_type st ON st.code = e.source_type WHERE e.iso3 = ? AND e.deleted_at IS NULL "
                    "ORDER BY e.id DESC LIMIT 12", (mine["iso3"],))
    from app.engine.model import ESTIMATE_KINDS
    for e in ev:
        e["quality"] = "estimate" if (e["source_code"] in ESTIMATE_KINDS or not (e.get("source") or "").strip()) else "sourced"
    return {"blocs": blocs, "archetypes": arch, "evidence": ev}


@router.get("/me/committees/{cid}/friends-foes")
def friends_foes(request: Request, cid: int, sess=Depends(require_student)):
    with request.app.state.db.read() as conn:
        if committee_access(conn, request.state.actor, cid) == "none":
            raise UserError("That committee isn't for your class.", 403)
        com = one(conn, "SELECT * FROM committee WHERE id = ?", (cid,))
        mine = _need_mine(conn, request.state.actor, cid)
        clauses = F.operative_clauses(conn, cid)
        pid = form_int(request.query_params.get("clause")) or (clauses[0]["id"] if clauses else None)
        clause = next((c for c in clauses if c["id"] == pid), None)
        if pid and not clause:
            raise UserError("Choose an operative clause in this committee.", 404)
        sheet = F.ff_sheet(conn, request.state.actor.id, cid, pid, mine["id"]) if clause else []
        summary = F.ff_summary(conn, request.state.actor.id, cid)
        live = scalar(conn, "SELECT id FROM live_session WHERE committee_id = ? AND state != 'closed' ORDER BY id DESC LIMIT 1", (cid,))
    return render(request, "floor/friends_foes.html", {"title": f"Friends and foes: {com['name']}", "com": com, "mine": mine,
                                                       "clauses": clauses, "clause": clause, "sheet": sheet, "summary": summary,
                                                       "live": live})


@router.post("/me/committees/{cid}/friends-foes")
def friends_foes_save(request: Request, cid: int, sess=Depends(require_student), form=Depends(form_data)):
    pid = form_int(form.get("clause"))
    with request.app.state.db.write(request.state.actor) as w:
        if committee_access(w.conn, request.state.actor, cid) == "none":
            raise UserError("That committee isn't for your class.", 403)
        _need_mine(w.conn, request.state.actor, cid)
        entries = {}
        for k, v in form.items():
            if k.startswith("stance_") and k[7:].isdigit():
                did = int(k[7:])
                entries[did] = (v, form.get(f"note_{did}") or "")
        n = F.ff_save(w, request.state.actor.id, pid, cid, entries)
    return redirect(f"/me/committees/{cid}/friends-foes?clause={pid}", f"Saved your reading of {n} delegations.")


# ---------------- amendment board (students and staff) ----------------

def _board_access(conn, request, cid: int) -> tuple[str, dict | None]:
    a = committee_access(conn, request.state.actor, cid)
    if a == "none":
        raise UserError("You don't have access to that committee.", 403)
    return a, _mine(conn, request.state.actor, cid)


def _amendment_committee(conn, aid: int) -> int:
    cid = scalar(conn, "SELECT r.committee_id FROM amendment a JOIN paragraph p ON p.id = a.paragraph_id "
                       "JOIN resolution r ON r.id = p.resolution_id WHERE a.id = ? AND a.deleted_at IS NULL", (aid,))
    if not cid:
        raise UserError("That amendment doesn't exist.", 404)
    return cid


@router.get("/mun/committees/{cid}/amendments")
def amendment_board(request: Request, cid: int, sess=Depends(require_any)):
    with request.app.state.db.read() as conn:
        access, mine = _board_access(conn, request, cid)
        com = one(conn, "SELECT * FROM committee WHERE id = ? AND deleted_at IS NULL", (cid,))
        if not com:
            raise UserError("That committee doesn't exist.", 404)
        items = F.board(conn, cid, mine["id"] if mine else None, staff=access == "manage")
        paras = rows(conn, "SELECT p.id, p.kind, p.position, r.title, v.text FROM paragraph p JOIN resolution r ON r.id = p.resolution_id "
                           "JOIN paragraph_version v ON v.id = p.current_version_id WHERE r.committee_id = ? AND r.deleted_at IS NULL "
                           "AND p.deleted_at IS NULL ORDER BY r.id, p.kind = 'operative', p.position", (cid,))
        live = scalar(conn, "SELECT id FROM live_session WHERE committee_id = ? AND state != 'closed' ORDER BY id DESC LIMIT 1", (cid,))
        needed = F.signatories_needed(conn, cid)
    show = request.query_params.get("show") or "all"
    if show in ("draft", "submitted", "ready", "floor", "adopted", "rejected"):
        items = [a for a in items if a["state"] == show]
    return render(request, "floor/board.html", {"title": f"Amendments: {com['name']}", "com": com, "items": items, "paras": paras,
                                                "mine": mine, "staff": access == "manage", "live": live, "show": show,
                                                "needed": needed})


@router.post("/mun/committees/{cid}/amendments")
def amendment_draft_new(request: Request, cid: int, sess=Depends(require_any), form=Depends(form_data)):
    from app.modules.mun import service as S
    with request.app.state.db.write(request.state.actor) as w:
        access, mine = _board_access(w.conn, request, cid)
        pid = form_int(form.get("paragraph_id"))
        p = S.paragraph(w.conn, pid) if pid else None
        if not p or p["committee_id"] != cid:
            raise UserError("Choose a clause in this committee.")
        sponsor = mine["id"] if mine else form_int(form.get("sponsor_delegation_id"))
        if access != "manage" and not mine:
            raise UserError("Only delegation members can propose amendments.", 403)
        aid = S.table_amendment(w, pid, form.get("kind") or "replace", form.get("proposed_text"), [], sponsor,
                                form.get("rationale") or "", draft=form.get("submit_now") != "1")
    return redirect(f"/mun/committees/{cid}/amendments#a{aid}",
                    "Amendment submitted: everyone can see it now." if form.get("submit_now") == "1"
                    else "Draft saved. Only your delegation sees it until you submit it.")


@router.post("/mun/amendments/{aid}/act")
def amendment_act(request: Request, aid: int, sess=Depends(require_any), form=Depends(form_data)):
    action = form.get("action") or ""
    with request.app.state.db.write(request.state.actor) as w:
        cid = _amendment_committee(w.conn, aid)
        access, mine = _board_access(w.conn, request, cid)
        staff = access == "manage"
        my_id = mine["id"] if mine else None
        if action == "edit":
            F.edit_draft(w, aid, my_id, form.get("proposed_text") or "", form.get("rationale") or "", staff)
            msg = "Draft updated."
        elif action == "submit":
            F.submit(w, aid, my_id, staff)
            msg = "Submitted: everyone can see it and sign it now."
        elif action in ("sign", "unsign"):
            if not mine:
                raise UserError("Only delegations sign amendments.", 403)
            from app.modules.mun import service as S
            if action == "sign":
                if my_id in F.sponsors_of(w.conn, aid):
                    raise UserError("You sponsor this amendment already.")
                S.support_amendment(w, aid, my_id, "signatory")
                msg = "Signed. Signing lets it reach the floor; it doesn't commit your vote."
            else:
                sup = scalar(w.conn, "SELECT id FROM amendment_support WHERE amendment_id = ? AND delegation_id = ? AND kind = 'signatory' "
                                     "AND deleted_at IS NULL", (aid, my_id))
                if sup:
                    S.withdraw_support(w, sup)
                msg = "Signature removed."
        elif action == "suggest":
            if not mine:
                raise UserError("Only delegations suggest edits.", 403)
            F.suggest(w, aid, my_id, request.state.actor.id, form.get("proposed_text") or "", form.get("note") or "")
            msg = "Suggestion sent to the sponsors."
        elif action in ("accept", "decline"):
            F.decide_suggestion(w, form_int(form.get("suggestion_id")), action == "accept", my_id, staff)
            msg = "Suggestion accepted: the amendment's text has changed." if action == "accept" else "Suggestion declined."
        elif action == "withdraw_suggestion":
            F.withdraw_suggestion(w, form_int(form.get("suggestion_id")), my_id or -1)
            msg = "Suggestion withdrawn."
        elif action == "withdraw":
            from app.modules.mun import service as S
            a = one(w.conn, "SELECT * FROM amendment WHERE id = ?", (aid,))
            if not staff and my_id not in F.sponsors_of(w.conn, aid):
                raise UserError("Only its sponsors can withdraw an amendment.", 403)
            if a["status"] != "tabled":
                raise UserError("That amendment has already been decided.")
            if scalar(w.conn, "SELECT 1 FROM division WHERE target_kind = 'amendment' AND target_id = ? AND status = 'open'", (aid,)):
                raise UserError("It's being voted on: it can't be withdrawn now.")
            S.set_amendment_status(w, aid, "withdrawn")
            sid = scalar(w.conn, "SELECT id FROM live_session WHERE floor_amendment_id = ? AND state != 'closed'", (aid,))
            if sid:
                F.clear_floor(w, sid)
            msg = "Amendment withdrawn."
        else:
            raise UserError("Unknown action.")
    back = _safe_next(form.get("next"), f"/mun/committees/{cid}/amendments")
    return redirect(back + (f"#a{aid}" if "#" not in back else ""), msg)


# ---------------- chair ----------------

@router.post("/chair/{sid}/floor")
def chair_floor_act(request: Request, sid: int, sess=Depends(require_staff), form=Depends(form_data)):
    action = form.get("action") or ""
    pred = None
    aid = form_int(form.get("amendment_id"))
    if action == "vote_amendment" and aid:
        # As for any division, the engine's prediction for empty seats is made before the write (D-042).
        from app.modules.mun.predict import run_prediction
        with request.app.state.db.read() as conn:
            _manage(conn, request, sid)
            pred = run_prediction(conn, "amendment", aid, with_swing=False)

    def act(w, s):
        if action == "bring":
            F.bring_to_floor(w, sid, aid, override=form.get("override") == "1")
            return "Amendment on the floor. Take speakers for and against, then a motion to vote."
        if action == "clear":
            F.clear_floor(w, sid)
            return "The amendment is off the floor; debate on the resolution continues."
        if action == "friendly":
            F.accept_friendly(w, sid, aid)
            return "Accepted as friendly: the text has changed on every screen."
        if action == "vote_amendment":
            v = F.amendment_view(w.conn, aid, s["floor_amendment_id"])
            if v["committee_id"] != s["committee_id"]:
                raise UserError("That amendment isn't in this committee.", 404)
            C.open_division(w, sid, f"Amendment {aid}: {v['kind_label']}", "amendment", aid, pred=pred)
            return "Voting on the amendment is open."
        if action == "side":
            F.add_side_speaker(w, sid, form_int(form.get("delegation_id")), None, form.get("side") or "")
            return "Added to the list."
        if action == "draft":
            F.set_resolution(w, sid, form_int(form.get("resolution_id")))
            return "Draft resolution on the floor changed."
        if action == "reopen":
            F.reopen_with_draft(w, sid, form_int(form.get("resolution_id")))
            return "The floor is open again with the next draft resolution."
        raise UserError("Unknown action.")
    return _chair_act(request, sid, act)


@router.post("/chair/{sid}/points/{pid}")
def chair_point(request: Request, sid: int, pid: int, sess=Depends(require_staff), form=Depends(form_data)):
    def act(w, s):
        p = one(w.conn, "SELECT session_id FROM floor_point WHERE id = ?", (pid,))
        if not p or p["session_id"] != sid:
            raise UserError("That point isn't in this session.", 404)
        F.decide_point(w, pid, form.get("status") or "")
        return {"answered": "Point answered.", "granted": "Right of reply granted: they're next on the list.",
                "declined": "Point declined."}.get(form.get("status"), "Done.")
    return _chair_act(request, sid, act)


@router.get("/chair/{sid}/messages")
def chair_messages(request: Request, sid: int, sess=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        s = _manage(conn, request, sid)
        msgs = F.all_messages(conn, sid)
    return render(request, "floor/chair_messages.html", {"title": f"Delegate messages: {s['committee']}", "s": s, "msgs": msgs})


@router.get("/chair/{sid}/f/messages")
def chair_messages_fragment(request: Request, sid: int, sess=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        s = _manage(conn, request, sid)
        msgs = F.all_messages(conn, sid)
    return render(request, "floor/_chair_messages.html", {"s": s, "msgs": msgs})


@router.post("/chair/{sid}/messages/{mid}")
def chair_message_hide(request: Request, sid: int, mid: int, sess=Depends(require_staff), form=Depends(form_data)):
    with request.app.state.db.write(request.state.actor) as w:
        _manage(w.conn, request, sid)
        m = one(w.conn, "SELECT session_id FROM delegate_message WHERE id = ?", (mid,))
        if not m or m["session_id"] != sid:
            raise UserError("That message isn't in this session.", 404)
        F.hide_message(w, mid, form.get("action") != "show")
    return redirect(f"/chair/{sid}/messages", "Message hidden from the delegations." if form.get("action") != "show" else "Message shown again.")
