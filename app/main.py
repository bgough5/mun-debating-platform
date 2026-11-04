"""Application factory. One process serves pages, API and WebSocket on one port (spec §7.2)."""
from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import Settings
from app.datasets import open_dataset
from app.errors import UserError
from app.util import process_rss_mb
from app.web.auth import CSRF_COOKIE, SESSION_COOKIE, NeedsLogin, session_for
from app.web.http import FLASH_COOKIE, csrf_protect, ensure_csrf, read_flash
from app.web.live import Hub
from app.web.templating import render

log = logging.getLogger("soc")
APP_DIR = Path(__file__).resolve().parent


async def _stats_loop(app, path: str, every_s: float = 60.0):
    """Diagnostics for soak tests (only when SOC_TIMING_LOG is set): every minute, one STATS line with the sizes of
    everything that could grow during a lesson. With SOC_TRACEMALLOC=1 it also logs the code locations whose
    allocations grew most since start-up (slower; for finding a leak, not for timing)."""
    import gc
    import threading
    import tracemalloc
    from app.modules.chair import routes as chair_routes
    from app.web import auth
    trace = os.environ.get("SOC_TRACEMALLOC") == "1"
    if trace:
        tracemalloc.start(8)
    base = None
    while True:
        await asyncio.sleep(every_s)
        try:
            hub = app.state.hub
            subs = sum(len(v) for v in hub.subs.values())
            rss = process_rss_mb()
            line = (f"{time.time():.3f} STATS rss_mb={rss if rss is None else round(rss, 1)} "
                    f"pooled={app.state.db.pooled_count()} threads={threading.active_count()} "
                    f"session_cache={len(auth._SESSION_CACHE)} view_cache={len(chair_routes._VIEW_CACHE)} "
                    f"hub_channels={len(hub.subs)} hub_subs={subs} gc_objects={len(gc.get_objects())} "
                    f"throttle={len(auth.login_throttle.fails) + len(auth.join_throttle.fails)}")
            if trace:
                snap = tracemalloc.take_snapshot()
                if base is None:
                    base = snap
                else:
                    top = snap.compare_to(base, "traceback")[:6]
                    line += " TOP " + " | ".join(f"{st.size_diff / 1024:.0f}KiB {st.traceback.format()[-1].strip()[:120]}"
                                                 for st in top)
            with open(path, "a") as f:
                f.write(line + "\n")
        except Exception:      # diagnostics must never take the server down
            log.exception("stats loop")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings().load()
    hub = Hub()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        hub.bind(asyncio.get_running_loop())
        # Request handlers are mostly Python (GIL-bound): a few worker threads keep up
        # better than anyio's default 40, which starve each other and the writer.
        import anyio.to_thread
        anyio.to_thread.current_default_thread_limiter().total_tokens = int(os.environ.get("SOC_THREADS", "8"))
        tasks = []
        from app.backup import nightly_loop
        tasks.append(asyncio.create_task(nightly_loop(app)))
        if os.environ.get("SOC_TIMING_LOG"):
            tasks.append(asyncio.create_task(_stats_loop(app, os.environ["SOC_TIMING_LOG"])))
        yield
        for t in tasks:
            t.cancel()

    app = FastAPI(title="South Oakleigh Debating & MUN", lifespan=lifespan, docs_url=None, redoc_url=None,
                  openapi_url=None, dependencies=[Depends(csrf_protect)])
    app.state.settings = settings
    app.state.hub = hub
    app.state.db = open_dataset(settings, settings.dataset, hub)

    app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")

    timing_log = os.environ.get("SOC_TIMING_LOG")

    @app.middleware("http")
    async def session_middleware(request: Request, call_next):
        t0 = time.perf_counter()
        ensure_csrf(request)
        request.state.flash = read_flash(request)
        db = request.app.state.db
        token = request.cookies.get(SESSION_COOKIE)
        sess = await asyncio.to_thread(session_for, db, token) if token else None
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
        if timing_log:
            with open(timing_log, "a") as f:
                f.write(f"{time.time():.3f} {time.perf_counter() - t0:.4f} {request.method} {request.url.path} {response.status_code}\n")
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
        if request.url.path.startswith(("/play/api", "/session/api")):   # single player's moves are JSON (D-099, D-101)
            from fastapi.responses import JSONResponse
            return JSONResponse({"error": exc.message}, status_code=exc.status)
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
    from app.modules.core.start import router as start_router
    app.include_router(start_router)
    from app.modules.core.resume import router as resume_router
    app.include_router(resume_router)
    from app.modules.core.wizard import router as wizard_router
    from app.modules.core.help import router as help_router
    app.include_router(wizard_router)
    app.include_router(help_router)
    from app.modules.admin.routes import router as admin_router
    app.include_router(admin_router)
    from app.web.ws import router as ws_router
    app.include_router(ws_router)
    if settings.module_on("people"):
        from app.modules.people.routes import router as people_router
        from app.modules.people.student_routes import router as student_router
        from app.modules.people.groups import router as groups_router
        app.include_router(groups_router)
        app.include_router(people_router)
        app.include_router(student_router)
    if settings.module_on("mun"):
        from app.modules.mun.routes import router as mun_router
        app.include_router(mun_router)
    if settings.module_on("chair"):
        from app.modules.chair.routes import router as chair_router
        from app.modules.sim.routes import router as sim_router
        from app.modules.floor.routes import router as floor_router
        app.include_router(chair_router)
        app.include_router(sim_router)
        from app.modules.sim.session_routes import router as session_router
        app.include_router(session_router)
        app.include_router(floor_router)
    if settings.module_on("debating"):
        from app.modules.debating.routes import router as debating_router
        from app.modules.debating.classroom_routes import router as classroom_router
        app.include_router(debating_router)
        app.include_router(classroom_router)
        from app.modules.debating.prep_routes import router as prep_router
        app.include_router(prep_router)
    if settings.module_on("intelligence"):
        try:
            from app.modules.intelligence.routes import router as intel_router
        except ModuleNotFoundError as e:       # module not built yet in this checkout
            if not str(e.name).startswith("app.modules.intelligence"):
                raise
        else:
            app.include_router(intel_router)
    return app
