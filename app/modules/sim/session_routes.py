"""The Session (D-101): the solo campaign's pages and moves.

- `/session` is the title screen: New session, Continue, Settings, Quick vote. Open to everyone.
- `/session/new` sets a game up: scenario, country, length, rivals, victory path, tutorial.
- `/session/s/{id}` is a signed-in student's saved campaign; `/session/guest` plays a guest's campaign, which lives
  in their browser (the page reads it from there and the server checks its signature on every move).
- `POST /session/api` takes one move (JSON with the CSRF header) and answers with the new view.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import RedirectResponse

from app.errors import UserError
from app.modules.sim import accounts as AC
from app.modules.sim.campaign import content as K
from app.modules.sim.campaign import engine as E
from app.modules.sim.campaign import store as S
from app.web.auth import require_coordinator, require_staff, require_student
from app.web.http import form_data
from app.web.templating import render

router = APIRouter()


def _student_id(request: Request) -> int | None:
    s = getattr(request.state, "session", None)
    return s.actor.id if s and s.actor.kind == "student" else None


def _account(request: Request):
    """The player account signed in on this browser (D-103), unless a student is signed in (a student comes first)."""
    if _student_id(request):
        return None
    tok = request.cookies.get(AC.COOKIE)
    if not tok:
        return None
    with request.app.state.db.read() as conn:
        return AC.load(conn, tok)


def _owner(request: Request):
    """Whose saves these are: ("student", id), ("account", id), or None for a guest."""
    me = _student_id(request)
    if me:
        return ("student", me)
    acc = _account(request)
    return ("account", acc["account_id"]) if acc else None


def _staff(request: Request) -> bool:
    s = getattr(request.state, "session", None)
    return bool(s and s.actor.kind == "staff")


def _common(request: Request) -> dict:
    acc = _account(request)
    return {"signed_in": bool(_student_id(request) or acc), "account": acc["username"] if acc else None,
            "save_base": "/session/a/" if acc else "/session/s/", "staff": _staff(request), "paths": K.PATHS,
            "lengths": E.LENGTHS, "difficulties": E.DIFFICULTIES, "signup_open": AC.open_signup(request.app.state.settings)}


@router.get("/session")
def session_title(request: Request):
    owner = _owner(request)
    saves = []
    if owner:
        with request.app.state.db.read() as conn:
            saves = S.my_saves(conn, owner)
    resp = render(request, "sim/session_title.html", {"title": "The Session", "saves": saves, **_common(request)})
    acc = _account(request)
    if acc:                                                      # a remembered sign-in is replaced at most daily
        with request.app.state.db.write(_who(request)) as w:
            new = AC.rotate(w.conn, acc)
        if new:
            resp.set_cookie(AC.COOKIE, new, **AC.cookie_kwargs(request, True))
    return resp


@router.get("/session/new")
def session_new(request: Request):
    cards, me = S.scenario_cards(), _owner(request)
    approaches = [{"code": c, "name": a["name"], "what": a["what"], "needs": a["needs"], "locked": False} for c, a in K.APPROACHES.items()]
    if me:                                                   # a signed-in player's scenarios and approaches open with medals (8 Nov)
        with request.app.state.db.read() as conn:
            prof = S.owner_profile(conn, me)
        locks = {x["code"]: x for x in prof["scenarios"]}
        cards = [{**c, "locked": locks[c["code"]]["locked"], "needs": locks[c["code"]]["needs"]} for c in cards]
        approaches = prof["approaches"]
    return render(request, "sim/session_new.html", {"title": "New session", "scenarios": cards, "approaches": approaches, **_common(request)})


@router.get("/session/profile")
def session_profile(request: Request):
    """Your record: a signed-in student's comes from their own saved sessions; a guest's is kept in their browser."""
    me, prof = _owner(request), None
    if me:
        with request.app.state.db.read() as conn:
            prof = S.owner_profile(conn, me)
    return render(request, "sim/session_profile.html", {"title": "Your record", "profile": prof, "cards": S.scenario_cards(),
                                                        "approaches": K.APPROACHES, "insignia": K.INSIGNIA, **_common(request)})


@router.get("/session/seats/{code}")
def session_seats(request: Request, code: str):
    """The seats in a scenario, with the map, for the country step of the setup (a fragment)."""
    from app.modules.chair.board import static_board
    db = request.app.state.db
    with db.read() as conn:
        with S.LOCK:
            scn = S.scenario(db, conn, code)
            seats = S.country_choices(scn)
        wmap = static_board(conn, scn.committee_id)
    return render(request, "sim/_session_seats.html", {"seats": seats, "wmap": wmap, "code": code, "scn_title": scn.title,
                                                       "veto": bool(scn.rule.veto)})


def _page(request: Request, conn, scn, view: dict, mode: str, save_id: int | None):
    from app.modules.chair.board import static_board
    return render(request, "sim/session_game.html", {"title": f"The Session: {scn.title}", "wmap": static_board(conn, scn.committee_id),
                                                     "view": view, "mode": mode, "save_id": save_id, "pack": scn.code,
                                                     **_common(request)})


@router.get("/session/s/{save_id}")
def session_saved(request: Request, save_id: int, sess=Depends(require_student)):
    db = request.app.state.db
    with db.read() as conn:
        r = S.mine(conn, save_id, request.state.actor.id)
        with S.LOCK:
            scn = S.scenario(db, conn, r["pack"])
            view = S.view(scn, r["state"])
        return _page(request, conn, scn, view, "saved", save_id)


@router.get("/session/a/{save_id}")
def session_account_saved(request: Request, save_id: int):
    """A player account's saved campaign (D-103): only the account that owns it."""
    owner = _owner(request)
    if not owner or owner[0] != "account":
        return RedirectResponse("/session/account", status_code=303)
    db = request.app.state.db
    with db.read() as conn:
        r = S.mine(conn, save_id, owner)
        with S.LOCK:
            scn = S.scenario(db, conn, r["pack"])
            view = S.view(scn, r["state"])
        return _page(request, conn, scn, view, "saved", save_id)


@router.get("/session/guest/{code}")
def session_guest(request: Request, code: str):
    """A guest's game: the page loads the game from this browser and asks the server for the view."""
    db = request.app.state.db
    with db.read() as conn:
        with S.LOCK:
            scn = S.scenario(db, conn, code)
        return _page(request, conn, scn, {}, "guest", None)


def _apply(scn, g: dict, action: dict):
    try:
        return E.apply(scn, g, action)
    except E.GameError as e:
        raise UserError(str(e)) from None


def _new(scn, payload: dict) -> dict:
    iso = str(payload.get("iso3") or "").upper()
    try:
        return _start(scn, iso, payload)
    except E.GameError as e:
        raise UserError(str(e)) from None


def _start(scn, iso: str, payload: dict) -> dict:
    return E.new_game(scn, iso, str(payload.get("length") or "standard"), str(payload.get("difficulty") or "standard"),
                      str(payload.get("path") or "mandate"), seed=E.random.SystemRandom().randrange(1, 2 ** 31),
                      approach=str(payload.get("approach") or "diplomat"))


@router.post("/session/api")
def session_api(request: Request, payload: dict = Body(...)):
    """Start a game or make a move. A signed-in student's game is saved under their account; a guest's comes back
    signed, to be kept in their browser."""
    db = request.app.state.db
    me = _owner(request)
    do = payload.get("do")
    action = payload.get("action") if isinstance(payload.get("action"), dict) else {}
    if do == "new":
        code = str(payload.get("pack") or "")
        if me:
            with db.read() as conn:
                prof = S.owner_profile(conn, me)
            rung = next((x for x in prof["scenarios"] if x["code"] == code), None)
            if rung and rung["locked"]:
                raise UserError(f"That scenario opens when you win gold on Standard or Hard in {rung['needs']}.", 403)
            way = next((x for x in prof["approaches"] if x["code"] == (payload.get("approach") or "diplomat")), None)
            if way and way["locked"]:
                raise UserError(f"{way['name']} opens with: {way['needs'].lower()}.", 403)
        with db.read() as conn:
            with S.LOCK:
                scn = S.scenario(db, conn, code)
                g = _new(scn, payload)
                view = S.view(scn, g)
        if me and payload.get("save", True):
            with db.write(_who(request)) as w:
                sid = S.save_new(w, me, g)
            return {"url": f"/session/{'a' if me[0] == 'account' else 's'}/{sid}", "view": view}
        return {"url": f"/session/guest/{code}", "state": g, "sig": S.sign(db, g), "view": view}
    if do == "export":                                     # the adopted resolution as a Word document
        import base64
        if payload.get("save_id"):
            if not me:
                raise UserError("Sign in first.", 403)
            with db.read() as conn:
                r = S.mine(conn, int(payload["save_id"]), me)
                g = r["state"]
                with S.LOCK:
                    scn = S.scenario(db, conn, r["pack"])
        else:
            g = S.verify(db, payload.get("state"), payload.get("sig"))
            with db.read() as conn:
                with S.LOCK:
                    scn = S.scenario(db, conn, str(g.get("pack") or ""))
        if g.get("phase") != "done" or not ((g.get("summit") or {}).get("final") or {}).get("passed"):
            raise UserError("Only an adopted resolution can be exported.")
        return {"name": scn.title + ".docx", "docx": base64.b64encode(S.resolution_docx(scn, g)).decode()}
    if do == "view" or do == "move":
        if payload.get("save_id"):
            if not me:
                raise UserError("Sign in to keep playing this saved session.", 403)
            with db.write(_who(request)) as w:
                r = S.mine(w.conn, int(payload["save_id"]), me)
                with S.LOCK:
                    scn = S.scenario(db, w.conn, r["pack"])
                    g, out = (r["state"], {}) if do == "view" else _apply(scn, r["state"], action)
                    view = S.view(scn, g)
                if do == "move":
                    S.save_move(w, r["id"], g, action, owner=me)
            return {"view": view, "out": out}
        g = S.verify(db, payload.get("state"), payload.get("sig"))
        with db.read() as conn:
            with S.LOCK:
                scn = S.scenario(db, conn, str(g.get("pack") or ""))
                g, out = (g, {}) if do == "view" else _apply(scn, g, action)
                view = S.view(scn, g)
        return {"view": view, "out": out, "state": g, "sig": S.sign(db, g)}
    if do == "abandon" and payload.get("save_id"):
        if not me:
            raise UserError("Sign in first.", 403)
        with db.write(_who(request)) as w:
            r = S.mine(w.conn, int(payload["save_id"]), me)
            w.soft_delete(S.TABLES[me[0]][0], r["id"])
        return {"ok": True}
    raise UserError("That isn't something The Session can do.")


@router.get("/session/almanac")
def session_almanac_index(request: Request):
    return render(request, "sim/session_almanac.html", {"title": "The Almanac", "scn": None, "scenarios": S.scenario_cards()})


@router.get("/session/almanac/{code}")
def session_almanac(request: Request, code: str):
    """Everything a delegate can look up for one scenario: how votes are decided, procedure, the paths, the skills,
    and every country file with its sources. Open to everyone; nothing personal."""
    db = request.app.state.db
    with db.read() as conn:
        with S.LOCK:
            scn = S.scenario(db, conn, code)
            files = [E.country_file(scn, {"skills": [], "moods": {}}, iso) for iso in scn.isos]
            veto = bool(scn.rule.veto)
    return render(request, "sim/session_almanac.html", {
        "title": "The Almanac", "scn": scn, "scn_veto": veto, "files": sorted(files, key=lambda f: f["name"]),
        "questions": K.QUESTIONS, "paths": K.PATHS, "skills": K.SKILLS, "skill_cost": K.SKILL_COST,
        "words": {2: "Strongly for", 1: "For", 0: "Neutral", -1: "Against", -2: "Strongly against"}})


@router.get("/session/results")
def session_results(request: Request, sess=Depends(require_staff)):
    """Teachers see their students' finished sessions: the scenario, the path chased and the grades. Never what a
    student wrote (D-101: Ben's answer)."""
    from app.web.auth import staff_class_ids
    with request.app.state.db.read() as conn:
        ids = staff_class_ids(conn, request.state.actor)
        data = S.results_for_staff(conn, ids)
    return render(request, "sim/session_results.html", {"title": "The Session: results", "results": data, "paths": K.PATHS,
                                                        "grades": E.GRADES})


# ---------------------------------------------------------------- player accounts (D-103)

def _who(request: Request):
    """Who to log a player-account change as: the signed-in staff member or student, else the player themselves."""
    from app.db import Actor
    if getattr(request.state, "actor", None):
        return request.state.actor
    acc = _account(request)
    return Actor("player", acc["account_id"] if acc else None, acc["username"] if acc else "A player")


def _ip(request: Request) -> str:
    return request.client.host if request.client else "anon"


@router.get("/session/account")
def session_account(request: Request):
    """Sign in, or create an account (when the school has approved open sign-up); signed in: your account."""
    return render(request, "sim/session_account.html", {"title": "Your account", **_common(request)})


@router.post("/session/account/signin")
def session_account_signin(request: Request, form=Depends(form_data)):
    username, password = str(form.get("username") or "")[:40], str(form.get("password") or "")[:200]
    keys = [f"acct:{username.strip().lower()}", f"acctip:{_ip(request)}"]
    wait = max(AC.signin_throttle.check(k) for k in keys)
    if wait:
        raise UserError(f"Too many tries. Wait {wait} seconds, then try again.", 429)
    with request.app.state.db.write(_who(request)) as w:
        acc = AC.authenticate(w.conn, username, password)
        if not acc:
            for k in keys:
                AC.signin_throttle.fail(k)
            raise UserError("Username or password is wrong.", 401)
        for k in keys:
            AC.signin_throttle.ok(k)
        remember = form.get("remember") == "1"
        token = AC.start(w.conn, acc["id"], remember)
    resp = RedirectResponse("/session", status_code=303)
    resp.set_cookie(AC.COOKIE, token, **AC.cookie_kwargs(request, remember))
    return resp


@router.post("/session/account/create")
def session_account_create(request: Request, form=Depends(form_data)):
    if not AC.open_signup(request.app.state.settings):
        raise UserError("New accounts are switched off right now. You can play as a guest.", 403)
    key = f"signup:{_ip(request)}"
    wait = AC.signup_throttle.check(key)
    if wait:
        raise UserError("Too many new accounts from this computer. Try again later.", 429)
    username, password = str(form.get("username") or "")[:40].strip(), str(form.get("password") or "")[:200]
    if password != str(form.get("password2") or "")[:200]:
        raise UserError("The two passwords don't match.")
    with request.app.state.db.write(_who(request)) as w:
        aid = AC.create(w, username, password)
        AC.signup_throttle.fail(key)                            # every account made counts towards this computer's limit
        remember = form.get("remember") == "1"
        token = AC.start(w.conn, aid, remember)
    resp = RedirectResponse("/session", status_code=303)
    resp.set_cookie(AC.COOKIE, token, **AC.cookie_kwargs(request, remember))
    return resp


@router.post("/session/account/signout")
def session_account_signout(request: Request):
    with request.app.state.db.write(_who(request)) as w:
        AC.end(w.conn, request.cookies.get(AC.COOKIE))
    resp = RedirectResponse("/session", status_code=303)
    resp.delete_cookie(AC.COOKIE, path="/")
    return resp


def _need_account(request: Request, password: str):
    acc = _account(request)
    if not acc:
        raise UserError("Sign in first.", 401)
    with request.app.state.db.read() as conn:
        row = one_account(conn, acc["account_id"])
    if not AC.authenticate_row(row, password):
        raise UserError("Your current password is wrong.", 401)
    return acc


def one_account(conn, aid: int):
    from app.db import one
    return one(conn, "SELECT * FROM player_account WHERE id = ? AND deleted_at IS NULL", (aid,))


@router.post("/session/account/password")
def session_account_password(request: Request, form=Depends(form_data)):
    acc = _need_account(request, str(form.get("password") or "")[:200])
    new = str(form.get("new_password") or "")[:200]
    if new != str(form.get("new_password2") or "")[:200]:
        raise UserError("The two new passwords don't match.")
    with request.app.state.db.write(_who(request)) as w:
        AC.change_password(w, acc["account_id"], new)           # every other sign-in ends
        token = AC.start(w.conn, acc["account_id"], bool(acc["remember"]))
    resp = RedirectResponse("/session/account", status_code=303)
    resp.set_cookie(AC.COOKIE, token, **AC.cookie_kwargs(request, bool(acc["remember"])))
    return resp


@router.post("/session/account/delete")
def session_account_delete(request: Request, form=Depends(form_data)):
    acc = _need_account(request, str(form.get("password") or "")[:200])
    with request.app.state.db.write(_who(request)) as w:
        AC.delete(w, acc["account_id"])
    resp = RedirectResponse("/session", status_code=303)
    resp.delete_cookie(AC.COOKIE, path="/")
    return resp


@router.get("/session/accounts")
def session_accounts_manage(request: Request, sess=Depends(require_coordinator)):
    """The coordinator: every account, who's active, and whether new accounts are allowed."""
    with request.app.state.db.read() as conn:
        listing = AC.listing(conn)
    cfg = request.app.state.settings.get("session_accounts", {}) or {}
    return render(request, "sim/session_accounts.html", {"title": "The Session: player accounts", "accounts": listing, "cfg": cfg,
                                                         "open": AC.open_signup(request.app.state.settings), "reset": None})


@router.post("/session/accounts/settings")
def session_accounts_settings(request: Request, sess=Depends(require_coordinator), form=Depends(form_data)):
    want = form.get("open") == "1"
    request.app.state.settings.set("session_accounts", {"open": want})
    from app.web.http import redirect
    return redirect("/session/accounts", "New accounts are " + ("allowed." if want else "switched off."))


@router.post("/session/accounts/erase-stale")
def session_accounts_erase_stale(request: Request, sess=Depends(require_coordinator)):
    with request.app.state.db.write(request.state.actor) as w:
        n = AC.erase_stale(w)
    from app.web.http import redirect
    return redirect("/session/accounts", f"Erased {n} account{'s' if n != 1 else ''} not used for a year.")


@router.post("/session/accounts/{aid}/delete")
def session_accounts_delete(request: Request, aid: int, sess=Depends(require_coordinator)):
    with request.app.state.db.write(request.state.actor) as w:
        AC.delete(w, aid)
    from app.web.http import redirect
    return redirect("/session/accounts", "The account and its saves were erased.")


@router.post("/session/accounts/{aid}/reset")
def session_accounts_reset(request: Request, aid: int, sess=Depends(require_coordinator)):
    """A temporary password, shown once, for a player who forgot theirs. Every sign-in on the account ends."""
    import secrets
    temp = "-".join(secrets.choice(["amber", "brisk", "cedar", "delta", "ember", "fjord", "grove", "harbor", "ivory", "jade",
                                    "kite", "lumen", "maple", "north", "onyx", "pine", "quill", "river", "slate", "tidal"]) for _ in range(3))
    with request.app.state.db.write(request.state.actor) as w:
        row = one_account(w.conn, aid)
        if not row:
            raise UserError("That account doesn't exist.", 404)
        AC.change_password(w, aid, temp)
        listing = AC.listing(w.conn)
    cfg = request.app.state.settings.get("session_accounts", {}) or {}
    return render(request, "sim/session_accounts.html", {"title": "The Session: player accounts", "accounts": listing, "cfg": cfg,
                                                         "open": AC.open_signup(request.app.state.settings),
                                                         "reset": {"username": row["username"], "password": temp}})
