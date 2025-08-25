# app/main.py
"""
FastAPI application entry point.
Sets up the web server, middleware, database migrations, and API routes.
"""

from __future__ import annotations

import logging
import os
import subprocess
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import health, chat, sessions, feedback, auth
from app.database import log_where_am_i
from app.config import settings

# Configure logging level from environment variable
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# Create FastAPI application instance
app = FastAPI(title="AI Chatbot API", version="0.1.0")

# ---- CORS Middleware ----
# Allow frontend to make requests from localhost:3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],  # Must include Authorization and X-Session-Id
)

# ---- Database Migration Function ----
def run_migrations() -> None:
    """Run Alembic database migrations on startup."""
    # Ensure Alembic sees DATABASE_URL
    os.environ.setdefault("DATABASE_URL", settings.DATABASE_URL)
    logger.warning("Running Alembic migrations...")
    subprocess.check_call(["alembic", "upgrade", "head"])
    logger.warning("Migrations complete.")

# ---- Startup Event Handler ----
@app.on_event("startup")
def _bootstrap() -> None:
    """Initialize database and log connection details on app startup."""
    run_migrations()
    log_where_am_i()  # Log database name + server address/port

# ---- API Routes ----
# Include all router modules to register their endpoints
app.include_router(health.router)
app.include_router(chat.router)
app.include_router(sessions.router)
app.include_router(feedback.router)
app.include_router(auth.router)

# ---- Root Endpoint ----
@app.get("/")
def root():
    """Health check endpoint for the root path."""
    return {"status": "ok", "message": "AI Chatbot backend is running"}
