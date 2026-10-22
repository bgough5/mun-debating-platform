"""MUN workflow writes: conferences, committees, delegations, the resolution
workspace (paragraphs, versions, amendments, sponsors), evidence, tasks and
actual votes. Every function takes a `Writer`, so each change is one logged
action that can be undone.
"""
from __future__ import annotations

from app.db import Writer, one, rows, scalar
from app.engine import sponsorship
from app.engine.calibration import CLASSES, Item, point_probs, report
from app.errors import UserError
from app.util import now_iso, today_iso

VOTES = ("yes", "abstain", "no", "absent")


def _req(value: str, what: str, limit: int = 200) -> str:
    v = (value or "").strip()
    if not v:
        raise UserError(f"Please enter {what}.")
    if len(v) > limit:
        raise UserError(f"{what.capitalize()} is too long (limit {limit} characters).")
    return v


def committee_channel(committee_id: int) -> str:
    return f"committee:{committee_id}"


def resolution_channel(resolution_id: int) -> str:
    return f"resolution:{resolution_id}"


# ---------- conferences, committees, delegations ----------

def create_conference(w: Writer, name: str, starts_on: str = "", ends_on: str = "", organiser: str = "", notes: str = "") -> int:
    return w.insert("conference", {"name": _req(name, "a conference name"), "starts_on": starts_on or "",
                                   "ends_on": ends_on or "", "organiser": organiser or "", "notes": notes or ""})


def create_committee(w: Writer, conference_id: int, name: str, committee_type_id: int | None, voting_rule_id: int | None,
                     topic_id: int | None, class_id: int | None = None, procedure_rule_set_id: int | None = None) -> int:
    ct = one(w.conn, "SELECT * FROM committee_type WHERE id = ?", (committee_type_id,)) if committee_type_id else None
    rule_id = voting_rule_id or (ct["default_rule_id"] if ct else None)
    if not rule_id:
        raise UserError("Choose a voting rule (or a committee type that has one).")
    return w.insert("committee", {
        "conference_id": conference_id, "name": _req(name, "a committee name"), "committee_type_id": committee_type_id,
        "voting_rule_id": rule_id, "procedure_rule_set_id": procedure_rule_set_id or (ct["default_procedure_id"] if ct else None),
        "topic_id": topic_id, "class_id": class_id})


def add_delegations(w: Writer, committee_id: int, iso3s: list[str]) -> list[int]:
    ids = []
    for iso in iso3s:
        iso = iso.strip().upper()
        if not iso:
            continue
        if not one(w.conn, "SELECT 1 FROM country WHERE iso3 = ? AND deleted_at IS NULL", (iso,)):
            raise UserError(f"{iso} isn't in the country list. Add it under Admin → Countries first.")
        existing = one(w.conn, "SELECT id, deleted_at FROM delegation WHERE committee_id = ? AND iso3 = ?", (committee_id, iso))
        if existing:
            if existing["deleted_at"]:
                w.restore("delegation", existing["id"], committee_channel(committee_id))
            ids.append(existing["id"])
            continue
        ids.append(w.insert("delegation", {"committee_id": committee_id, "iso3": iso}, committee_channel(committee_id)))
    return ids


def assign_member(w: Writer, delegation_id: int, student_id: int, role: str = "delegate") -> int:
    d = one(w.conn, "SELECT * FROM delegation WHERE id = ?", (delegation_id,))
    if not d:
        raise UserError("That delegation doesn't exist.", 404)
    if role not in ("head", "delegate"):
        raise UserError("Role must be head or delegate.")
    clash = one(w.conn, "SELECT d.iso3 FROM delegation_member dm JOIN delegation d ON d.id = dm.delegation_id "
                        "WHERE dm.student_id = ? AND d.committee_id = ? AND dm.deleted_at IS NULL AND d.deleted_at IS NULL",
                (student_id, d["committee_id"]))
    if clash:
        raise UserError(f"That student is already in the {clash['iso3']} delegation in this committee. Remove them there first.")
    existing = one(w.conn, "SELECT * FROM delegation_member WHERE delegation_id = ? AND student_id = ?", (delegation_id, student_id))
    if existing:
        w.update("delegation_member", existing["id"], {"deleted_at": None, "role": role}, committee_channel(d["committee_id"]))
        return existing["id"]
    return w.insert("delegation_member", {"delegation_id": delegation_id, "student_id": student_id, "role": role},
                    committee_channel(d["committee_id"]))


def remove_member(w: Writer, member_id: int) -> None:
    m = one(w.conn, "SELECT dm.*, d.committee_id FROM delegation_member dm JOIN delegation d ON d.id = dm.delegation_id "
                    "WHERE dm.id = ?", (member_id,))
    if m:
        w.soft_delete("delegation_member", member_id, committee_channel(m["committee_id"]))


def allocate_round_robin(w: Writer, committee_id: int, student_ids: list[int]) -> int:
    """Give each unallocated student a delegation, filling empty delegations first (ISO-3 order)."""
    dels = rows(w.conn, "SELECT d.id, d.iso3, (SELECT COUNT(*) FROM delegation_member dm WHERE dm.delegation_id = d.id "
                        "AND dm.deleted_at IS NULL) AS n FROM delegation d WHERE d.committee_id = ? AND d.deleted_at IS NULL "
                        "ORDER BY d.iso3", (committee_id,))
    if not dels:
        raise UserError("Add delegations before allocating students.")
    taken = {r["student_id"] for r in rows(w.conn, "SELECT dm.student_id FROM delegation_member dm JOIN delegation d "
                                                   "ON d.id = dm.delegation_id WHERE d.committee_id = ? AND dm.deleted_at IS NULL",
                                           (committee_id,))}
    count = 0
    for sid in student_ids:
        if sid in taken:
            continue
        dels.sort(key=lambda d: (d["n"], d["iso3"]))
        target = dels[0]
        assign_member(w, target["id"], sid, "head" if target["n"] == 0 else "delegate")
        target["n"] += 1
        count += 1
    return count


# ---------- resolution workspace ----------

def create_resolution(w: Writer, committee_id: int, title: str) -> int:
    return w.insert("resolution", {"committee_id": committee_id, "title": _req(title, "a title")},
                    committee_channel(committee_id))


def _clean_tags(conn, committee_id: int, tags) -> str:
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",")]
    tags = [t for t in dict.fromkeys(t for t in (tags or []) if t)]
    topic = scalar(conn, "SELECT topic_id FROM committee WHERE id = ?", (committee_id,))
    if topic:
        known = {r["code"] for r in rows(conn, "SELECT code FROM tag WHERE topic_id = ? AND deleted_at IS NULL", (topic,))}
        unknown = [t for t in tags if t not in known]
        if unknown:
            raise UserError("Unknown tag(s) for this topic: " + ", ".join(unknown) + ". Add them under Admin → Tags.")
    return ",".join(tags)


def _res(conn, resolution_id):
    r = one(conn, "SELECT * FROM resolution WHERE id = ? AND deleted_at IS NULL", (resolution_id,))
    if not r:
        raise UserError("That resolution doesn't exist.", 404)
    return r


def add_paragraph(w: Writer, resolution_id: int, kind: str, text: str, tags="", owner_delegation_id: int | None = None,
                  position: int | None = None) -> int:
    r = _res(w.conn, resolution_id)
    if kind not in ("preambular", "operative"):
        raise UserError("A paragraph is preambular or operative.")
    text = _req(text, "the paragraph text", 4000)
    tags = _clean_tags(w.conn, r["committee_id"], tags)
    last = scalar(w.conn, "SELECT COALESCE(MAX(position), 0) FROM paragraph WHERE resolution_id = ? AND kind = ? "
                          "AND deleted_at IS NULL", (resolution_id, kind))
    pos = position or last + 1
    if position:
        for p in rows(w.conn, "SELECT id, position FROM paragraph WHERE resolution_id = ? AND kind = ? AND position >= ? "
                              "AND deleted_at IS NULL ORDER BY position DESC", (resolution_id, kind, position)):
            w.update("paragraph", p["id"], {"position": p["position"] + 1}, resolution_channel(resolution_id))
    ch = resolution_channel(resolution_id)
    pid = w.insert("paragraph", {"resolution_id": resolution_id, "kind": kind, "position": pos,
                                 "owner_delegation_id": owner_delegation_id}, ch)
    vid = w.insert("paragraph_version", {"paragraph_id": pid, "text": text, "tags": tags, "author_label": w.actor.label,
                                         "created_at": now_iso(), "parent_version_id": None, "note": "First draft"}, ch)
    w.update("paragraph", pid, {"current_version_id": vid}, ch)
    return pid


def paragraph(conn, paragraph_id: int) -> dict:
    p = one(conn, "SELECT p.*, v.text, v.tags, r.committee_id FROM paragraph p "
                  "JOIN paragraph_version v ON v.id = p.current_version_id JOIN resolution r ON r.id = p.resolution_id "
                  "WHERE p.id = ? AND p.deleted_at IS NULL", (paragraph_id,))
    if not p:
        raise UserError("That paragraph doesn't exist.", 404)
    return p


def edit_paragraph(w: Writer, paragraph_id: int, text: str, tags, expected_version_id: int | None = None,
                   note: str = "") -> int:
    p = paragraph(w.conn, paragraph_id)
    if expected_version_id and p["current_version_id"] != expected_version_id:
        raise UserError("Someone saved a newer version of this paragraph while you were editing. "
                        "Your text is below; reload to see theirs and try again.", 409)
    text = _req(text, "the paragraph text", 4000)
    tags = _clean_tags(w.conn, p["committee_id"], tags)
    if text == p["text"] and tags == p["tags"]:
        return p["current_version_id"]
    ch = resolution_channel(p["resolution_id"])
    vid = w.insert("paragraph_version", {"paragraph_id": paragraph_id, "text": text, "tags": tags,
                                         "author_label": w.actor.label, "created_at": now_iso(),
                                         "parent_version_id": p["current_version_id"], "note": note or ""}, ch)
    w.update("paragraph", paragraph_id, {"current_version_id": vid}, ch)
    return vid


def restore_paragraph_version(w: Writer, paragraph_id: int, version_id: int) -> int:
    v = one(w.conn, "SELECT * FROM paragraph_version WHERE id = ? AND paragraph_id = ?", (version_id, paragraph_id))
    if not v:
        raise UserError("That version doesn't belong to this paragraph.", 404)
    return edit_paragraph(w, paragraph_id, v["text"], v["tags"], note=f"Restored version {version_id}")


def set_owner(w: Writer, paragraph_id: int, delegation_id: int | None) -> None:
    p = paragraph(w.conn, paragraph_id)
    w.update("paragraph", paragraph_id, {"owner_delegation_id": delegation_id}, resolution_channel(p["resolution_id"]))


def next_seq(conn) -> int:
    return (scalar(conn, "SELECT COALESCE(MAX(seq), 0) FROM event_log") or 0) + 1


def table_amendment(w: Writer, paragraph_id: int, kind: str, proposed_text: str, tags, sponsor_delegation_id: int | None,
                    rationale: str = "") -> int:
    p = paragraph(w.conn, paragraph_id)
    if kind not in ("add", "delete", "replace"):
        raise UserError("An amendment adds, deletes or replaces a paragraph.")
    if kind == "delete":
        proposed_text, tags = "", p["tags"]
    else:
        proposed_text = _req(proposed_text, "the proposed text", 4000)
        tags = _clean_tags(w.conn, p["committee_id"], tags)
    ch = resolution_channel(p["resolution_id"])
    aid = w.insert("amendment", {"paragraph_id": paragraph_id, "base_version_id": p["current_version_id"], "kind": kind,
                                 "proposed_text": proposed_text, "tags": tags, "sponsor_delegation_id": sponsor_delegation_id,
                                 "rationale": rationale or "", "created_at": now_iso()}, ch)
    if sponsor_delegation_id:
        support_amendment(w, aid, sponsor_delegation_id, "sponsor")
    return aid


def support_amendment(w: Writer, amendment_id: int, delegation_id: int, kind: str) -> None:
    a = one(w.conn, "SELECT a.*, p.resolution_id FROM amendment a JOIN paragraph p ON p.id = a.paragraph_id WHERE a.id = ?",
            (amendment_id,))
    if not a:
        raise UserError("That amendment doesn't exist.", 404)
    if kind not in ("sponsor", "second", "signatory"):
        raise UserError("Support is sponsor, second or signatory.")
    if kind == "second" and one(w.conn, "SELECT 1 FROM amendment_support WHERE amendment_id = ? AND delegation_id = ? "
                                        "AND kind = 'sponsor' AND deleted_at IS NULL", (amendment_id, delegation_id)):
        raise UserError("A sponsor can't second its own amendment.")
    ch = resolution_channel(a["resolution_id"])
    existing = one(w.conn, "SELECT * FROM amendment_support WHERE amendment_id = ? AND delegation_id = ? AND kind = ?",
                   (amendment_id, delegation_id, kind))
    if existing:
        if existing["deleted_at"]:
            w.update("amendment_support", existing["id"], {"deleted_at": None, "seq": next_seq(w.conn)}, ch)
        return
    w.insert("amendment_support", {"amendment_id": amendment_id, "delegation_id": delegation_id, "kind": kind,
                                   "seq": next_seq(w.conn)}, ch)


def withdraw_support(w: Writer, support_id: int) -> None:
    s = one(w.conn, "SELECT s.*, p.resolution_id FROM amendment_support s JOIN amendment a ON a.id = s.amendment_id "
                    "JOIN paragraph p ON p.id = a.paragraph_id WHERE s.id = ?", (support_id,))
    if s:
        w.soft_delete("amendment_support", support_id, resolution_channel(s["resolution_id"]))


def amendment_on_floor(conn, paragraph_id: int) -> int | None:
    """Which tabled amendment goes to the floor first: most seconds, ties to the earliest sponsor (ported v2 rule)."""
    events = []
    for s in rows(conn, "SELECT s.* FROM amendment_support s JOIN amendment a ON a.id = s.amendment_id "
                        "WHERE a.paragraph_id = ? AND a.status = 'tabled' AND a.deleted_at IS NULL AND s.deleted_at IS NULL "
                        "AND s.kind IN ('sponsor','second') ORDER BY s.seq", (paragraph_id,)):
        if s["kind"] == "sponsor":
            events.append({"seq": s["seq"], "player": f"d{s['delegation_id']}:{s['amendment_id']}", "kind": "sponsor",
                           "payload": {"id": str(s["amendment_id"])}})
        else:
            events.append({"seq": s["seq"], "player": f"d{s['delegation_id']}", "kind": "second",
                           "payload": {"id": str(s["amendment_id"]), "seconded": True}})
    # Co-sponsorship across amendments is allowed here (a delegation may sponsor
    # several), so each (delegation, amendment) sponsorship is its own "player".
    win = sponsorship.resolve(events, "sponsor", "second", "id")
    return int(win) if win else None


def set_amendment_status(w: Writer, amendment_id: int, status: str) -> None:
    a = one(w.conn, "SELECT a.*, p.resolution_id, p.kind AS pkind, p.position FROM amendment a "
                    "JOIN paragraph p ON p.id = a.paragraph_id WHERE a.id = ?", (amendment_id,))
    if not a:
        raise UserError("That amendment doesn't exist.", 404)
    if status not in ("tabled", "passed", "failed", "withdrawn", "friendly"):
        raise UserError("Unknown amendment status.")
    if a["status"] in ("passed", "friendly") and status != a["status"]:
        raise UserError("This amendment has already been applied to the text. Use undo, or restore an earlier version.")
    ch = resolution_channel(a["resolution_id"])
    w.update("amendment", amendment_id, {"status": status}, ch)
    if status in ("passed", "friendly"):
        p = paragraph(w.conn, a["paragraph_id"])
        if a["kind"] == "replace":
            vid = w.insert("paragraph_version", {"paragraph_id": a["paragraph_id"], "text": a["proposed_text"],
                                                 "tags": a["tags"], "author_label": f"Amendment {amendment_id}",
                                                 "created_at": now_iso(), "parent_version_id": p["current_version_id"],
                                                 "note": f"Amendment {amendment_id} {status}"}, ch)
            w.update("paragraph", a["paragraph_id"], {"current_version_id": vid}, ch)
        elif a["kind"] == "delete":
            w.soft_delete("paragraph", a["paragraph_id"], ch)
        elif a["kind"] == "add":
            add_paragraph(w, a["resolution_id"], a["pkind"], a["proposed_text"], a["tags"],
                          a["sponsor_delegation_id"], position=a["position"] + 1)


# ---------- evidence ----------

def add_evidence(w: Writer, *, subject_kind: str, iso3: str | None = None, bloc_id: int | None = None,
                 target_kind: str, target_id: int | None = None, tag_code: str = "", topic_id: int | None = None,
                 position, strength: str = "moderate", conditional: bool = False, condition_text: str = "",
                 source: str = "", source_type: str, stated_on: str = "", summary: str = "", channel: str = "") -> int:
    st = one(w.conn, "SELECT * FROM source_type WHERE code = ? AND deleted_at IS NULL", (source_type,))
    if not st:
        raise UserError("Choose a source type.")
    if subject_kind == "country":
        if not iso3 or not one(w.conn, "SELECT 1 FROM country WHERE iso3 = ?", (iso3.upper(),)):
            raise UserError("Choose which country this evidence is about.")
        iso3, bloc_id = iso3.upper(), None
    elif subject_kind == "bloc":
        if not bloc_id or not one(w.conn, "SELECT 1 FROM bloc WHERE id = ?", (bloc_id,)):
            raise UserError("Choose which bloc this evidence is about.")
        iso3 = None
    else:
        raise UserError("Evidence is about a country or a bloc.")
    if target_kind not in ("paragraph", "amendment", "resolution", "tag", "topic"):
        raise UserError("Choose what the evidence is about (paragraph, amendment, resolution, tag or topic).")
    if target_kind in ("paragraph", "amendment", "resolution") and not target_id:
        raise UserError("Choose the paragraph, amendment or resolution this evidence is about.")
    if target_kind == "tag" and not tag_code:
        raise UserError("Choose the tag this evidence is about.")
    if position not in (None, ""):
        try:
            position = int(position)
        except (TypeError, ValueError):
            raise UserError("Position must be from -2 (strongly oppose) to +2 (strongly support).")
        if not -2 <= position <= 2:
            raise UserError("Position must be from -2 (strongly oppose) to +2 (strongly support).")
    else:
        position = None
    source = (source or "").strip()
    if source_type == "ai_estimate" and not source:
        # AI positions without a source are stored as unknown (spec §5.3, CLAUDE.md).
        position = None
        summary = (summary + " " if summary else "") + "[No source given: stored as unknown, not counted.]"
    elif st["requires_source"] and not source:
        raise UserError(f"{st['label']} needs a source: a link, a citation, or who said it and when.")
    if strength not in ("weak", "moderate", "strong"):
        raise UserError("Strength is weak, moderate or strong.")
    return w.insert("evidence", {
        "subject_kind": subject_kind, "iso3": iso3, "bloc_id": bloc_id, "target_kind": target_kind,
        "target_id": target_id, "tag_code": tag_code or "", "topic_id": topic_id, "position": position,
        "strength": strength, "conditional": int(bool(conditional)), "condition_text": condition_text or "",
        "source": source, "source_type": source_type, "stated_on": stated_on or "", "recorded_on": now_iso(),
        "recorded_by": w.actor.label, "summary": (summary or "").strip()[:1000]}, channel)


# ---------- tasks ----------

def create_tasks_from_swing(w: Writer, delegation_id: int, swing_rows, amendment_id: int | None, paragraph_id: int | None,
                            top_n: int = 3, assignees: list[int] | None = None) -> list[int]:
    """Turn the top swing blocs and countries into lobbying tasks, shared round-robin among assignees."""
    d = one(w.conn, "SELECT * FROM delegation WHERE id = ?", (delegation_id,))
    if not d:
        raise UserError("Choose your delegation.", 404)
    if assignees is None:
        assignees = [r["student_id"] for r in rows(w.conn, "SELECT student_id FROM delegation_member WHERE delegation_id = ? "
                                                         "AND deleted_at IS NULL ORDER BY role = 'head' DESC, id", (delegation_id,))]
    picked = [r for r in swing_rows if r.delta_p > 0 and r.key != d["iso3"]][:top_n]
    if not picked:
        raise UserError("No country or bloc would change the outcome by moving, so there is nothing to lobby. "
                        "Try a different amendment, or record more evidence first.")
    ids = []
    for i, r in enumerate(picked):
        bloc_id = scalar(w.conn, "SELECT id FROM bloc WHERE code = ?", (r.key,)) if r.kind == "bloc" else None
        ids.append(w.insert("task", {
            "delegation_id": delegation_id, "assignee_student_id": assignees[i % len(assignees)] if assignees else None,
            "target_iso3": r.key if r.kind == "country" else None, "target_bloc_id": bloc_id,
            "amendment_id": amendment_id, "paragraph_id": paragraph_id,
            "title": f"Lobby {r.name}" + (" (bloc)" if r.kind == "bloc" else ""),
            "talking_points": "", "notes": f"Moving them one step toward yes changes P(pass) by {r.delta_p:+.0%}.",
            "created_at": now_iso()}, committee_channel(d["committee_id"])))
    return ids


def update_task(w: Writer, task_id: int, **changes) -> None:
    t = one(w.conn, "SELECT t.*, d.committee_id FROM task t JOIN delegation d ON d.id = t.delegation_id WHERE t.id = ?", (task_id,))
    if not t:
        raise UserError("That task doesn't exist.", 404)
    allowed = {k: v for k, v in changes.items() if k in ("status", "talking_points", "notes", "assignee_student_id", "due_on", "title")}
    if "status" in allowed and allowed["status"] not in ("todo", "doing", "done"):
        raise UserError("Status is to do, doing or done.")
    w.update("task", task_id, allowed, committee_channel(t["committee_id"]))


# ---------- actual votes and calibration ----------

def record_actual_votes(w: Writer, target_kind: str, target_id: int, votes: dict[str, str], context: str = "conference",
                        prediction_id: int | None = None) -> int:
    if context not in ("conference", "real_un"):
        raise UserError("Context is conference or real UN.")
    n = 0
    for iso, vote in votes.items():
        if vote in ("", None):
            continue
        if vote not in VOTES:
            raise UserError(f"Vote for {iso} must be yes, abstain, no or absent.")
        existing = one(w.conn, "SELECT id FROM actual_vote WHERE target_kind = ? AND target_id = ? AND iso3 = ? AND context = ?",
                       (target_kind, target_id, iso, context))
        if existing:
            w.update("actual_vote", existing["id"], {"vote": vote, "prediction_id": prediction_id})
        else:
            w.insert("actual_vote", {"target_kind": target_kind, "target_id": target_id, "iso3": iso, "vote": vote,
                                     "context": context, "prediction_id": prediction_id, "recorded_by": w.actor.label,
                                     "recorded_at": now_iso()})
        n += 1
    return n


def calibration_items(conn, context: str = "conference") -> tuple[list[Item], dict[str, list[Item]]]:
    """Items: for each recorded vote, the latest prediction snapshot made before it, per country.

    Baselines (spec §5.6): everyone votes yes; everyone votes with the majority of the
    rest of their bloc on the same vote (leave-one-out); the archetype prior alone.
    """
    targets = rows(conn, "SELECT DISTINCT target_kind, target_id FROM actual_vote WHERE context = ? AND vote != 'absent'",
                   (context,))
    items: list[Item] = []
    base_yes: list[Item] = []
    base_bloc: list[Item] = []
    base_arch: list[Item] = []
    from app.engine.model import ModelParams, distribution, CountryInput, Source
    import json
    for t in targets:
        votes = {r["iso3"]: r for r in rows(conn, "SELECT * FROM actual_vote WHERE target_kind = ? AND target_id = ? "
                                                  "AND context = ? AND vote != 'absent'", (t["target_kind"], t["target_id"], context))}
        pid = None
        linked = [v["prediction_id"] for v in votes.values() if v["prediction_id"]]
        if linked:
            pid = max(linked)
        else:
            first = min(v["recorded_at"] for v in votes.values())
            pid = scalar(conn, "SELECT id FROM prediction WHERE target_kind = ? AND target_id = ? AND created_at <= ? "
                               "ORDER BY id DESC LIMIT 1", (t["target_kind"], t["target_id"], first))
        if not pid:
            continue
        pred = {r["iso3"]: r for r in rows(conn, "SELECT * FROM prediction_country WHERE prediction_id = ?", (pid,))}
        payload = json.loads(scalar(conn, "SELECT inputs_json FROM prediction WHERE id = ?", (pid,)))
        params = ModelParams.from_dict(payload["params"])
        arch_src = {c["iso3"]: [s for s in c["sources"] if s[3] == "archetype"] for c in payload["countries"]}
        group = f"{t['target_kind']}:{t['target_id']}"
        blocs: dict[str, list[str]] = {}
        for r in rows(conn, "SELECT b.code, bm.iso3 FROM bloc_member bm JOIN bloc b ON b.id = bm.bloc_id "
                            "WHERE bm.deleted_at IS NULL AND b.deleted_at IS NULL"):
            blocs.setdefault(r["iso3"], []).append(r["code"])
        members_of: dict[str, list[str]] = {}
        for iso, codes in blocs.items():
            for c in codes:
                members_of.setdefault(c, []).append(iso)
        for iso, v in sorted(votes.items()):
            if iso not in pred:
                continue
            p = pred[iso]
            items.append(Item((p["p_yes"], p["p_abstain"], p["p_no"]), v["vote"], group))
            base_yes.append(Item(point_probs("yes"), v["vote"], group))
            # bloc majority, leave-one-out, using the country's largest bloc present in this vote
            best = None
            for code in sorted(blocs.get(iso, []), key=lambda c: (-len([m for m in members_of[c] if m in votes]), c)):
                others = [votes[m]["vote"] for m in members_of[code] if m in votes and m != iso]
                if others:
                    best = max(CLASSES, key=lambda c: (others.count(c), -CLASSES.index(c)))
                    break
            base_bloc.append(Item(point_probs(best) if best else (1 / 3, 1 / 3, 1 / 3), v["vote"], group))
            a = arch_src.get(iso) or []
            ad = distribution(CountryInput(iso, iso, tuple(Source(s[0], s[1], s[2], s[2]) for s in a)), params)
            base_arch.append(Item((ad.p_yes, ad.p_abstain, ad.p_no), v["vote"], group))
    return items, {"Everyone votes yes": base_yes, "Everyone votes with their bloc majority": base_bloc,
                   "Archetype prior alone": base_arch}


def calibration_report(conn, context: str = "conference"):
    items, baselines = calibration_items(conn, context)
    if not items:
        return None
    return report(items, baselines)
