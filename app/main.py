from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Form, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes import router
from app.auth import authenticate, ensure_admin_password
from app.collectors.hamqsl import collector_loop
from app.database import init_db, is_setup_complete
from app.layout_exports import router as layout_exports_router
from app.layout_imports import router as layout_imports_router
from app.map_adapter import router as map_adapter_router
from app.paths import static_dir, templates_dir
from app.proxy import fetch_proxied
from app.proxy_diagnostics import router as proxy_diagnostics_router
from app.screenshots import router as screenshots_router
from app.setup import router as setup_router
from app.themes import router as themes_router
from app.updates import router as updates_router, update_check_loop
from app.version import APP_VERSION, PRODUCT_FULL_NAME
from app.websocket import manager


async def heartbeat() -> None:
    while True:
        await asyncio.sleep(15)
        await manager.broadcast({"event": "heartbeat"})


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    ensure_admin_password()
    tasks = [asyncio.create_task(heartbeat())]
    if os.getenv("DASHBOARD_MATRIX_DISABLE_HAMQSL", "").lower() not in {
        "1",
        "true",
        "yes",
    }:
        tasks.append(asyncio.create_task(collector_loop()))
    if os.getenv("DASHBOARD_MATRIX_DISABLE_UPDATE_CHECKS", "").lower() not in {
        "1",
        "true",
        "yes",
    }:
        tasks.append(asyncio.create_task(update_check_loop()))
    yield
    for task in tasks:
        task.cancel()
    for task in tasks:
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title=PRODUCT_FULL_NAME,
    version=APP_VERSION,
    lifespan=lifespan,
)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv(
        "DASHBOARD_MATRIX_SESSION_SECRET",
        "change-this-session-secret",
    ),
    same_site="lax",
    https_only=os.getenv("DASHBOARD_MATRIX_HTTPS_ONLY", "0").lower()
    in {"1", "true", "yes"},
)
app.include_router(router)
app.include_router(setup_router)
app.include_router(map_adapter_router)
app.include_router(layout_exports_router)
app.include_router(layout_imports_router)
app.include_router(updates_router)
app.include_router(themes_router)
app.include_router(proxy_diagnostics_router)
app.include_router(screenshots_router)
app.mount("/static", StaticFiles(directory=static_dir()), name="static")
templates = Jinja2Templates(directory=templates_dir())


@app.middleware("http")
async def first_run_gate(request: Request, call_next):
    path = request.url.path
    allowed = (
        path.startswith("/static/")
        or path.startswith("/api/setup")
        or path in {"/setup", "/health"}
    )
    if not allowed and not is_setup_complete():
        return RedirectResponse("/setup", status_code=303)
    if path == "/setup" and is_setup_complete():
        return RedirectResponse("/admin", status_code=303)
    return await call_next(request)


def _dashboard_response(request: Request, slug: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"slug": slug, "app_version": APP_VERSION},
    )


@app.get("/setup", response_class=HTMLResponse)
def setup_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="setup.html",
        context={"app_version": APP_VERSION},
    )


@app.get("/", response_class=HTMLResponse)
def dashboard_root(request: Request, slug: str = "main") -> HTMLResponse:
    return _dashboard_response(request, slug)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_alias(request: Request, slug: str = "main") -> HTMLResponse:
    return _dashboard_response(request, slug)


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request):
    if not request.session.get("admin_authenticated"):
        return RedirectResponse("/admin/login", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={"app_version": APP_VERSION},
    )


@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_page(request: Request):
    if request.session.get("admin_authenticated"):
        return RedirectResponse("/admin", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": "", "app_version": APP_VERSION},
    )


@app.post("/admin/login", response_class=HTMLResponse)
def admin_login(request: Request, password: str = Form(...)):
    if authenticate(password):
        request.session["admin_authenticated"] = True
        return RedirectResponse("/admin", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "error": "Incorrect password.",
            "app_version": APP_VERSION,
        },
        status_code=401,
    )


@app.post("/admin/logout")
def admin_logout(request: Request):
    request.session.clear()
    return RedirectResponse("/admin/login", status_code=303)


@app.get("/proxy/{source_id}")
@app.get("/proxy/{source_id}/{path:path}")
async def proxy_source(request: Request, source_id: str, path: str = ""):
    return await fetch_proxied(source_id, path, request)


@app.get("/health")
def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "product": "dashboard-matrix",
        "version": APP_VERSION,
        "setup_complete": is_setup_complete(),
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
