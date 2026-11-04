"""Start an activity (D-084 stage 2): one screen for every kind of session.

Pick what you're running (UNAA, Evatt, a class debate, a public speaking round or your own format), tick who's taking
part today from the one student list (or add first-timers), choose a difficulty, and go. Works for any number of
students: MUN seats are shared out (empty ones are voted by the engine), debates split into rooms of up to eight,
and speaking rounds take everyone ticked.
"""
from __future__ import annotations

import math
import random
import statistics

from fastapi import APIRouter, Depends, Request

from app.db import one, rows
from app.errors import UserError
from app.modules.mun import choice as CH
from app.util import display_name, today_iso
from app.web.auth import can_run_class, require_staff
from app.web.http import form_data
from app.web.templating import render

router = APIRouter()

# The one front door (D-099): four activities. "unaa" and "evatt" are older names for Model UN with a set scenario and
# are still accepted from links and forms; the Start page offers "mun" with a scenario card instead.
KINDS = {
    "mun": ("Model UN", "A committee from a scenario: roll call, debate, amendments and the vote, with the board on the projector."),
    "debate": ("Class debate", "Two teams. Up to eight students make one debate; more are split into several debates."),
    "speeches": ("Public speaking", "Everyone ticked speaks in turn: prepared speeches, or impromptu topics drawn as each turn starts."),
    "custom": ("Your own format", "A timed round of speakers with every setting yours: times, topics, order and names."),
}
LEGACY_KINDS = {"unaa": "climate2026", "evatt": "veloria"}       # kind -> the scenario it always meant
CLIMATE = {"code": "climate2026", "title": "Climate finance (UNAA 2026)", "type": "ga_plenary", "level": "middle",
           "fictional": False, "countries": [None] * 31,
           "summary": "The UNAA Victoria 2026 General Assembly: 31 delegations and a nine-clause draft on climate finance. "
                      "Positions are unsourced estimates from the original practice pack."}

# What a difficulty level changes. Every value can still be edited once the activity is open.
LEVELS = {
    "junior": {"label": "Junior", "years": "about Years 7–8", "mun": 60, "debate": 180, "reply": 90, "speech": 90, "think": 90},
    "middle": {"label": "Middle", "years": "about Years 9–10", "mun": 90, "debate": 240, "reply": 120, "speech": 120, "think": 60},
    "senior": {"label": "Senior", "years": "about Years 11–12", "mun": 120, "debate": 360, "reply": 180, "speech": 180, "think": 45},
}
DEBATE_ROOM_MAX = 8
NEEDS = {"mun": ("mun", "chair"), "unaa": ("mun", "chair"), "evatt": ("mun", "chair"), "debate": ("debating",),
         "speeches": ("debating",), "custom": ("debating",)}


def available_kinds(settings) -> dict:
    """Only the kinds whose modules are switched on (Admin → Modules)."""
    return {k: v for k, v in KINDS.items() if all(settings.module_on(m) for m in NEEDS[k])}


def accepted_kind(settings, kind: str) -> bool:
    return kind in NEEDS and all(settings.module_on(m) for m in NEEDS[kind])


def suggest_level(year_levels: list) -> str:
    """Junior for a group that is mostly Years 7–8 or younger, senior for mostly 11–12, middle otherwise or unknown."""
    ys = [y for y in year_levels if y]
    if not ys:
        return "middle"
    m = statistics.median(ys)
    return "junior" if m <= 8 else "senior" if m >= 11 else "middle"


def _mmss(s: int) -> str:
    return f"{s // 60}:{s % 60:02d}"


def level_summary(level: str) -> str:
    v = LEVELS[level]
    return (f"MUN speeches {_mmss(v['mun'])}, debate speeches {_mmss(v['debate'])}, public speaking {_mmss(v['speech'])}; "
            f"motions and impromptu topics for {v['label'].lower()} level")


def picker(conn, actor) -> dict:
    """The student tick list: everyone this person may see, grouped by year level (core/_pick_students.html)."""
    from app.modules.people.routes import YEARS, visible_students
    students = visible_students(conn, actor)
    seen: dict = {}
    for st in students:
        seen[st["name"]] = seen.get(st["name"], 0) + 1
    for st in students:                      # two "Ken"s from different groups: say which is which
        st["also"] = st["group_name"] if seen[st["name"]] > 1 else ""
    by_year: dict = {}
    for st in students:
        by_year.setdefault(st["year_level"], []).append(st)
    groups = [(y, by_year[y]) for y in sorted(k for k in by_year if k)] + ([(None, by_year[None])] if None in by_year else [])
    return {"groups": groups, "total": len(students), "years": YEARS}


def _context(conn, request, ticked: set[int], form: dict | None = None) -> dict:
    motions = rows(conn, "SELECT id, motion, level FROM motion_bank WHERE deleted_at IS NULL ORDER BY level, motion")
    form = form or {}
    from app.modules.people.groups import saved_groups
    return {"title": "Start an activity", "saved": saved_groups(conn, request.state.actor), "offer_save": False, "kinds": available_kinds(request.app.state.settings), "levels": LEVELS, "summaries": {k: level_summary(k) for k in LEVELS},
            **picker(conn, request.state.actor), "ticked": ticked, "motions": motions,
            "kind": form.get("kind") or "", "level": form.get("level") or "suggested",
            "motion_id": form.get("motion_id") or "", "topic_mode": form.get("topic_mode") or "prepared",
            "country_mode": form.get("country_mode") or "random", "country_modes": CH.MODES,
            "scenarios": _packs() + [CLIMATE], "pack": form.get("pack") or "veloria", "group_name": form.get("group_name") or "",
            "suggested": suggest_level([st["year_level"] for _y, people in picker(conn, request.state.actor)["groups"]
                                        for st in people if st["id"] in ticked]) if ticked else ""}


def _packs() -> list[dict]:
    from app.modules.mun.packfile import available
    return available()


@router.get("/start")
def start_page(request: Request, group: int | None = None, s=Depends(require_staff)):
    with request.app.state.db.read() as conn:
        ticked: set[int] = set()
        if group and request.app.state.settings.module_on("people"):
            from app.modules.people.groups import get_group
            ticked = set(get_group(conn, request.state.actor, group)["members"])
        q = request.query_params                  # links from the libraries: /start?kind=mun&pack=ga_migration
        ctx = _context(conn, request, ticked, {k: q.get(k) for k in ("kind", "pack", "motion_id", "topic_mode") if q.get(k)})
    return render(request, "core/start.html", ctx)


@router.post("/start")
def start_submit(request: Request, s=Depends(require_staff), form=Depends(form_data)):
    ticked = {int(x) for x in form.getlist("student_id") if str(x).isdigit()}
    from app.modules.people.groups import picker_op
    done = picker_op(request.app.state.db, request.state.actor, form, ticked)
    if done is not None:                     # first-timers added, a saved group ticked or saved: show the form again
        with request.app.state.db.read() as conn:
            ctx = _context(conn, request, done[0], form)
        ctx["flash"] = done[1]
        return render(request, "core/start.html", ctx)
    kind = form.get("kind")
    if not accepted_kind(request.app.state.settings, kind):
        raise UserError("Choose what you're running first: Model UN, a class debate, public speaking or your own format.")
    with request.app.state.db.write(request.state.actor) as w:
        from app.modules.people.routes import visible_students
        allowed = {st["id"]: st for st in visible_students(w.conn, request.state.actor)}
        chosen = [allowed[i] for i in ticked if i in allowed]
        if not chosen:
            raise UserError("Tick at least one student who is taking part today.")
        level = form.get("level")
        if level not in LEVELS:
            level = suggest_level([st["year_level"] for st in chosen])
        url, msg = create_activity(w, request.state.actor, kind, chosen, level, form)
        name = (form.get("group_name") or "").strip()
        if name and request.app.state.settings.module_on("people"):      # "and save these students as a group"
            from app.modules.people.groups import save_group
            _gid, gmsg = save_group(w, request.state.actor, name, {st["id"] for st in chosen})
            msg = f"{msg} {gmsg}"
    from app.web.http import redirect
    return redirect(url, msg)


# ---------- creating each kind ----------

def _activity_class(conn, actor, chosen: list[dict]) -> int | None:
    """The group the new activity belongs to (it decides which teachers can run it): the default Students group when
    this person can run it, else the group most of the ticked students are in that they can run."""
    from app.modules.people.routes import POOL_NAME
    pool = one(conn, "SELECT id FROM class WHERE name = ? AND deleted_at IS NULL ORDER BY id LIMIT 1", (POOL_NAME,))
    if pool and can_run_class(conn, actor, pool["id"]):
        return pool["id"]
    counts: dict = {}
    for st in chosen:
        counts[st["class_id"]] = counts.get(st["class_id"], 0) + 1
    for cid, _ in sorted(counts.items(), key=lambda kv: -kv[1]):
        if can_run_class(conn, actor, cid):
            return cid
    return None


def create_activity(w, actor, kind: str, chosen: list[dict], level: str, form) -> tuple[str, str]:
    lv = LEVELS[level]
    cid = _activity_class(w.conn, actor, chosen)
    if kind in ("mun", "unaa", "evatt"):
        pack = form.get("pack") or LEGACY_KINDS.get(kind, "veloria")
        return _mun(w, kind, cid, chosen, lv, level, form.get("country_mode") or "random", pack)
    if kind == "debate":
        return _debates(w, cid, chosen, lv, level, form)
    return _speeches(w, kind, cid, chosen, lv, level, form)


def _mun(w, kind, cid, chosen, lv, level, mode: str = "random", pack: str = "") -> tuple[str, str]:
    from app.modules.chair import service as C
    from app.modules.mun import packs, service as M
    stamp = today_iso()
    # The scenario the teacher picked (D-097, D-099); the climate conference is the original v2 pack.
    if pack == "climate2026":
        info = packs.load_climate_conference(w, cid, name_suffix=f" · {stamp}")
    elif pack in {p["code"] for p in _packs()}:
        from app.modules.mun.packfile import install
        info = install(w, pack, cid, name_suffix=f" · {stamp}") if pack != "veloria" else packs.load_evatt_scenario(w, cid)
    else:
        raise UserError("Choose a scenario for the committee.")
    com = info["committee_id"]
    ids = [st["id"] for st in chosen]
    # Today's students, and how they get their countries (D-094).
    CH.set_roster(w, com, ids)
    CH.set_mode(w, com, mode if mode in CH.MODES else "random")
    if mode not in ("choose", "chair"):
        CH.allocate_random(w, com, ids)
    sid = C.open_session(w, com)
    w.update("live_session", sid, {"speaking_time_s": lv["mun"]}, C.ch(sid), action="speaking_time")
    seats = one(w.conn, "SELECT COUNT(*) AS n FROM delegation WHERE committee_id = ? AND deleted_at IS NULL", (com,))["n"]
    how = {"choose": f"{len(chosen)} student(s) choose their countries from {seats} as they sign in",
           "chair": f"{len(chosen)} student(s) to seat: give out the {seats} countries on the committee page"}.get(
        mode, f"{len(chosen)} student(s) seated at random across {seats} delegations")
    return (f"/chair/{sid}", f"Model UN ready: {how} ({LEVELS[level]['label'].lower()} level, {_mmss(lv['mun'])} speeches). "
                             "Countries without a student are voted by the engine and labelled computed.")


def _pick_motion(w, level: str, form) -> str:
    mid = form.get("motion_id")
    if mid and str(mid).isdigit():
        m = one(w.conn, "SELECT motion FROM motion_bank WHERE id = ? AND deleted_at IS NULL", (int(mid),))
        if m:
            return m["motion"]
    ms = [r["motion"] for r in rows(w.conn, "SELECT motion FROM motion_bank WHERE level = ? AND deleted_at IS NULL", (level,))] or \
         [r["motion"] for r in rows(w.conn, "SELECT motion FROM motion_bank WHERE deleted_at IS NULL")]
    return random.choice(ms) if ms else ""


def _set_student_ids(w, rid: int, by_slot: dict) -> None:
    """Link each speaking slot to the ticked student directly (students can come from any group, so matching typed
    names against one group's roster isn't enough)."""
    from app.modules.debating.classroom import ch, speakers
    for sp in speakers(w.conn, rid):
        sid = by_slot.get((sp["side"], sp["position"]))
        if sid and sp["student_id"] != sid:
            w.update("class_run_speaker", sp["id"], {"student_id": sid}, ch(rid))


def _debates(w, cid, chosen, lv, level, form) -> tuple[str, str]:
    from app.modules.debating import classroom as R
    if len(chosen) < 2:
        raise UserError("A debate needs at least two students. For one student, choose Public speaking.")
    people = chosen[:]
    random.shuffle(people)
    rooms = math.ceil(len(people) / DEBATE_ROOM_MAX)
    groups = [people[i::rooms] for i in range(rooms)]           # sizes differ by at most one
    motion = _pick_motion(w, level, form)
    made = []
    for n, group in enumerate(groups, 1):
        per_side = math.ceil(len(group) / 2)
        aff, neg = group[:per_side], group[per_side:]
        f = {"motion": motion, "speakers_per_side": str(per_side), "speech_seconds": str(lv["debate"]), "warning_seconds": "60",
             "reply": "1" if level == "senior" else "", "reply_seconds": str(lv["reply"]), "prep_minutes": "0", "level": level,
             "title": (f"Debate {n} of {rooms}: " if rooms > 1 else "") + motion[:60]}
        slots = {}
        for side, team in (("aff", aff), ("neg", neg)):
            for p, st in enumerate(team, 1):
                f[f"{side}_{p}"] = display_name(st["first_name"], st["last_initial"])
                slots[(side, p)] = st["id"]
        rid = R.create_run(w, "debate", cid, f)
        _set_student_ids(w, rid, slots)
        made.append(rid)
    gap = " One side has a spare slot (an odd number of students): a student can speak twice, or edit the run." \
        if any(len(g) % 2 for g in groups) else ""
    if rooms == 1:
        return (f"/debating/runs/{made[0]}", f"Class debate ready ({LEVELS[level]['label'].lower()} level). Motion: {motion}.{gap}")
    return ("/debating", f"{rooms} debates set up for {len(chosen)} students (rooms of up to {DEBATE_ROOM_MAX}). Motion: {motion}. "
                         f"Open each one from the list below.{gap}")


def _speeches(w, kind, cid, chosen, lv, level, form) -> tuple[str, str]:
    from app.modules.debating import classroom as R
    people = chosen[:]
    random.shuffle(people)
    chunks = [people[i:i + R.MAX_SPEAKERS] for i in range(0, len(people), R.MAX_SPEAKERS)]
    made = []
    for n, chunk in enumerate(chunks, 1):
        names = [display_name(st["first_name"], st["last_initial"]) for st in chunk]
        f = {"names": "\n".join(names), "speech_seconds": str(lv["speech"]), "warning_seconds": "30", "level": level,
             "topic_mode": "impromptu" if form.get("topic_mode") == "impromptu" else "prepared", "think_seconds": str(lv["think"]),
             "title": ("Your own format" if kind == "custom" else "Public speaking") + (f" ({n} of {len(chunks)})" if len(chunks) > 1 else "")}
        rid = R.create_run(w, "speeches", cid, f)
        _set_student_ids(w, rid, {("", p): st["id"] for p, st in enumerate(chunk, 1)})
        made.append(rid)
    if kind == "custom":
        return (f"/debating/runs/{made[0]}/edit", "Your own format: everyone ticked is listed. Change any time, topic, order or name, then save.")
    return (f"/debating/runs/{made[0]}", f"Public speaking ready: {len(chosen)} speaker(s), {_mmss(lv['speech'])} each "
                                         f"({LEVELS[level]['label'].lower()} level, {'impromptu' if form.get('topic_mode') == 'impromptu' else 'prepared'}).")
