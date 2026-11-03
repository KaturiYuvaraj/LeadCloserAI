"""
Main Application Entrypoint for Telugu AI Caller & Lead Closing CRM.
FastAPI Web Server with modular routers for pages, leads, calls, employees,
integrations, developer APIs, messaging, campaigns, and telephony.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import uvicorn

from config import CORS_ORIGINS, HOST, PORT
from database import init_db
from providers import sync_providers_with_db

from core.web import templates, BASE_DIR
from routers import (
    pages,
    leads,
    employees,
    calls,
    campaigns,
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
    Initializes database and synchronizes third-party providers on startup.
    """
    init_db()
    sync_providers_with_db()
    logger.info("Database & Multi-Provider Architecture initialized. Telugu AI Caller ready.")
    try:  # outbound call queue (needs the real-time voice engine)
        from voice_agent.dialer import call_queue
        call_queue.start()
    except ImportError:
        call_queue = None
    yield
    if call_queue:
        await call_queue.stop()


app = FastAPI(
    title="Telugu AI Caller & Lead Closer",
    description="Natural language Telugu AI calling agent to qualify and close software leads.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure directories exist
(BASE_DIR / "static").mkdir(parents=True, exist_ok=True)
(BASE_DIR / "templates").mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Include modular routers
app.include_router(pages.router)
app.include_router(leads.router)
app.include_router(employees.router)
app.include_router(calls.router)
app.include_router(campaigns.router)
app.include_router(integrations.router)
app.include_router(messaging.router)
app.include_router(developer.router)
app.include_router(telephony.router)
app.include_router(knowledge.router)

# Real-time voice engine (Pipecat). Optional: without it the dashboard uses the classic engine.
try:
    from routers import voice, dialer
    app.include_router(voice.router)
    app.include_router(dialer.router)
except ImportError as e:
    logger.warning(f"Real-time voice engine unavailable ({e}); using the classic /ws/web-call engine.")


if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
