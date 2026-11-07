"""
Main Application Entrypoint for Telugu AI Caller & Lead Closing CRM.
FastAPI Web Server with modular routers for auth, pages, leads, calls, employees,
integrations, developer APIs, messaging, campaigns, dialer, and telephony.
"""

from contextlib import asynccontextmanager
import socket

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import uvicorn

from config import CORS_ORIGINS, HOST, PORT
from database import init_db
from providers import sync_providers_with_db

from core.web import BASE_DIR
from routers import (
    auth,
    pages,
    leads,
    employees,
    calls,
    campaigns,
    dialer,
    quotations,
    admin_panel,
    integrations,
    messaging,
    developer,
    telephony,
    knowledge,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager replacing deprecated @app.on_event.
    Initializes database, synchronizes third-party providers, and starts the
    restart-safe outbound campaign queue on startup.
    """
    init_db()
    sync_providers_with_db()
    logger.info("Database & Multi-Provider Architecture initialized. Telugu AI Caller ready.")
    from voice_agent import webhook_auth
    if not webhook_auth.enabled():
        logger.warning("VOBIZ_WEBHOOK_SECRET is not set: the Vobiz answer/hangup/stream routes accept any request. "
                       "Set it before exposing this app to the internet.")
    try:
        from voice_agent.dialer import call_queue
        call_queue.start()
    except Exception as e:
        logger.warning(f"Outbound call queue startup warning: {e}")
        call_queue = None
    yield
    if call_queue:
        await call_queue.stop()


app = FastAPI(
    title="Telugu AI Caller & Lead Closer",
    description="Natural language Multilingual AI calling agent to qualify and close software leads.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/js") or request.url.path.endswith(".html") or request.url.path == "/" or request.url.path == "/crm":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Ensure directories exist
(BASE_DIR / "static").mkdir(parents=True, exist_ok=True)
(BASE_DIR / "templates").mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Include modular routers
app.include_router(auth.router)
app.include_router(pages.router)
app.include_router(leads.router)
app.include_router(employees.router)
app.include_router(calls.router)
app.include_router(campaigns.router)
app.include_router(dialer.router)
app.include_router(quotations.router)
app.include_router(admin_panel.router)
app.include_router(integrations.router)
app.include_router(messaging.router)
app.include_router(developer.router)
app.include_router(telephony.router)
app.include_router(knowledge.router)

# Real-time Pipecat voice stream router (optional)
try:
    from routers import voice
    app.include_router(voice.router)
except ImportError:
    logger.info("Using classic /ws/web-call voice engine.")


def _resolve_bind_target(preferred_host: str, preferred_port: int) -> tuple[str, int]:
    """Ensures the requested host/port is available on Windows, avoiding WinError 10013/10048."""
    candidates = [
        (preferred_host, preferred_port),
        ("127.0.0.1", preferred_port),
        ("127.0.0.1", preferred_port + 1),
        ("127.0.0.1", 8080),
    ]
    for bind_host, bind_port in candidates:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((bind_host, bind_port))
                return bind_host, bind_port
            except OSError:
                continue
    return preferred_host, preferred_port


if __name__ == "__main__":
    bind_host, bind_port = _resolve_bind_target(HOST, PORT)
    if (bind_host, bind_port) != (HOST, PORT):
        logger.info(f"Port {HOST}:{PORT} was busy; starting server on http://{bind_host}:{bind_port}")
    else:
        logger.info(f"Starting server on http://127.0.0.1:{bind_port}")
    uvicorn.run("main:app", host=bind_host, port=bind_port, reload=True)
