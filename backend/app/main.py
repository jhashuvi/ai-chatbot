# app/main.py
from __future__ import annotations

import logging
import os
import subprocess
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import health, chat, sessions, feedback, auth
from app.database import log_where_am_i
from app.config import settings

# Basic logging; tweak via LOG_LEVEL env if you want
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Chatbot API", version="0.1.0")

# ---- CORS (adjust origins for your frontend) ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],  # must include Authorization and X-Session-Id
)

# ---- Run Alembic before serving requests & log DB target ----
def run_migrations() -> None:
    # Ensure Alembic sees DATABASE_URL
    os.environ.setdefault("DATABASE_URL", settings.DATABASE_URL)
    logger.warning("Running Alembic migrations...")
    subprocess.check_call(["alembic", "upgrade", "head"])
    logger.warning("Migrations complete.")

@app.on_event("startup")
def _bootstrap() -> None:
    run_migrations()
    log_where_am_i()  # prints db name + server addr/port

# ---- Routers ----
app.include_router(health.router)
app.include_router(chat.router)
app.include_router(sessions.router)
app.include_router(feedback.router)
app.include_router(auth.router)

# ---- Root redirect ----
@app.get("/")
def root():
    return {"status": "ok", "message": "AI Chatbot backend is running"}
