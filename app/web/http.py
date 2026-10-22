"""Request helpers shared by every module: redirects with a flash message, CSRF, form parsing."""
from __future__ import annotations

import secrets
from urllib.parse import quote, unquote

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse

from app.web.auth import CSRF_COOKIE

FLASH_COOKIE = "soc_flash"
UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


def redirect(url: str, flash: str | None = None, status: int = 303) -> RedirectResponse:
    resp = RedirectResponse(url, status_code=status)
    if flash:
        resp.set_cookie(FLASH_COOKIE, quote(flash[:300]), max_age=30, httponly=True, samesite="lax")
    return resp


def read_flash(request: Request) -> str | None:
    v = request.cookies.get(FLASH_COOKIE)
    return unquote(v) if v else None


def ensure_csrf(request: Request) -> str:
    tok = request.cookies.get(CSRF_COOKIE)
    if not tok or len(tok) < 20:
        tok = secrets.token_urlsafe(24)
        request.state.new_csrf = tok
    request.state.csrf = tok
    return tok


async def csrf_protect(request: Request) -> None:
    """Double-submit check on every unsafe request: the form field or header must
    match the cookie. Cookies are SameSite=Lax as a second layer."""
    if request.method not in UNSAFE:
        return
    cookie = request.cookies.get(CSRF_COOKIE, "")
    sent = request.headers.get("x-csrf-token", "")
    if not sent:
        ctype = request.headers.get("content-type", "")
        if ctype.startswith(("application/x-www-form-urlencoded", "multipart/form-data")):
            form = await request.form()
            sent = str(form.get("csrf", ""))
    if not cookie or not secrets.compare_digest(cookie, sent):
        raise HTTPException(status_code=403, detail="This form has expired. Go back, reload the page and try again.")


def form_int(value, default=None):
    try:
        return int(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def form_float(value, default=None):
    try:
        return float(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default
