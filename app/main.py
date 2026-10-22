"""Application factory. One process serves pages, API and WebSocket on one port (spec §7.2)."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import Settings
from app.datasets import open_dataset
from app.errors import UserError
from app.web.auth import CSRF_COOKIE, SESSION_COOKIE, NeedsLogin, load_session, touch
from app.web.http import FLASH_COOKIE, csrf_protect, ensure_csrf, read_flash
from app.web.live import Hub
from app.web.templating import render

log = logging.getLogger("soc")
APP_DIR = Path(__file__).resolve().parent


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings().load()
    hub = Hub()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        hub.bind(asyncio.get_running_loop())
        tasks = []
        from app.backup import nightly_loop
        tasks.append(asyncio.create_task(nightly_loop(app)))
        yield
        for t in tasks:
            t.cancel()

    app = FastAPI(title="South Oakleigh Debating & MUN", lifespan=lifespan, docs_url=None, redoc_url=None,
                  openapi_url=None, dependencies=[Depends(csrf_protect)])
    app.state.settings = settings
    app.state.hub = hub
    app.state.db = open_dataset(settings, settings.dataset, hub)

    app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")

    @app.middleware("http")
    async def session_middleware(request: Request, call_next):
        ensure_csrf(request)
        request.state.flash = read_flash(request)
        db = request.app.state.db
        conn = db.connect()
        try:
            sess = load_session(conn, request.cookies.get(SESSION_COOKIE))
            if sess:
                touch(conn, sess)
        finally:
            conn.close()
        request.state.session = sess
        request.state.actor = sess.actor if sess else None
        response = await call_next(request)
        if getattr(request.state, "new_csrf", None):
            response.set_cookie(CSRF_COOKIE, request.state.new_csrf, httponly=False, samesite="lax", max_age=60 * 60 * 24 * 365)
        if request.state.flash and FLASH_COOKIE in request.cookies and response.status_code < 300:
            response.delete_cookie(FLASH_COOKIE)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        return response

    @app.exception_handler(NeedsLogin)
    async def needs_login(request: Request, exc: NeedsLogin):
        target = "/join" if exc.next_url.startswith(("/me", "/join")) else "/login?next=" + exc.next_url
        if request.headers.get("hx-request"):
            from fastapi.responses import Response
            return Response(status_code=204, headers={"HX-Redirect": target})
        return RedirectResponse(target, status_code=303)

    @app.exception_handler(UserError)
    async def user_error(request: Request, exc: UserError):
        return render(request, "error.html", {"title": "That didn't work", "message": exc.message}, status=exc.status)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        titles = {403: "Not allowed", 404: "Page not found", 405: "Not allowed", 409: "Conflict"}
        msg = exc.detail if isinstance(exc.detail, str) and exc.status_code != 404 else \
            "That page doesn't exist. Check the address, or go back to the home page."
        return render(request, "error.html", {"title": titles.get(exc.status_code, "Something went wrong"),
                                              "message": msg}, status=exc.status_code)

    from app.modules.core.routes import router as core_router
    app.include_router(core_router)
    from app.modules.admin.routes import router as admin_router
    app.include_router(admin_router)
    if settings.module_on("people"):
        from app.modules.people.routes import router as people_router
        app.include_router(people_router)
    if settings.module_on("mun"):
        from app.modules.mun.routes import router as mun_router
        app.include_router(mun_router)
    for name in ("chair", "debating", "intelligence"):
        if settings.module_on(name):
            try:
                mod = __import__(f"app.modules.{name}.routes", fromlist=["router"])
            except ModuleNotFoundError as e:
                if e.name != f"app.modules.{name}.routes" and not str(e.name).startswith(f"app.modules.{name}"):
                    raise
                continue
            app.include_router(mod.router)
    return app
