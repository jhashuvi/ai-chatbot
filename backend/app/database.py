"""
Database connection and session management.
Handles SQLAlchemy setup, connection pooling, and session lifecycle.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from .config import settings

logger = logging.getLogger(__name__)

# SQLAlchemy engine with connection pooling and health checks
engine = create_engine(
    settings.DATABASE_URL,
    future=True,  # Use SQLAlchemy 2.x style
    poolclass=QueuePool,
    pool_size=20,  # Number of connections to maintain
    max_overflow=30,  # Additional connections when pool is full
    pool_pre_ping=True,  # Test connections before use
    pool_recycle=3600,  # Recycle connections after 1 hour
    echo=getattr(settings, "SQL_ECHO", False),  # Log SQL queries in dev
)

# Creates database sessions with consistent configuration
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,  # Keep objects accessible after commit
    future=True,
)

# Import Base from models for table creation
from .models import Base  # noqa: E402

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a DB session.
    - On normal exit: commits (no-op if repos already committed).
    - On exception: rollbacks.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager for manual session management (scripts, tasks).
    Mirrors get_db() semantics.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        logger.error(f"Database context error: {e}")
        db.rollback()
        raise
    finally:
        db.close()



def redacted_dsn(dsn: str) -> str:
    """
    Redact password in a DATABASE_URL for safe logging.
    """
    try:
        url = make_url(dsn)
        safe = url.set(password="***")
        return str(safe)
    except Exception:
        return "<unparsable DSN>"


def where_am_i(db: Session) -> Tuple[str, str, int]:
    """
    Returns (current_database, server_addr, server_port) for forensic logging.
    """
    row = db.execute(text("SELECT current_database(), inet_server_addr(), inet_server_port()")).first()
    return (row[0], str(row[1]), int(row[2])) if row else ("", "", 0)


def log_where_am_i() -> None:
    """
    Open a short-lived session and log which DB/host/port we actually hit.
    Safe to call in app startup.
    """
    ds = redacted_dsn(settings.DATABASE_URL)
    with SessionLocal() as db:
        try:
            dbname, addr, port = where_am_i(db)
            logger.warning(f"DB connected -> dsn={ds} | db={dbname} | addr={addr} | port={port}")
        except Exception as e:
            logger.error(f"DB introspection failed for dsn={ds}: {e}")
