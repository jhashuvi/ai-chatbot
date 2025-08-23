"""
Chat session repository for managing conversation threads.
Handles session creation, updates, and user session relationships.
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func  # added or_
from datetime import datetime, timedelta
import logging

from .base import BaseRepository
from ..models.chat_session import ChatSession
from ..schemas.session import SessionCreate, SessionUpdate

logger = logging.getLogger(__name__)


class ChatSessionRepository(BaseRepository[ChatSession, SessionCreate, SessionUpdate]):
    """
    Repository for chat session management operations.
    Extends BaseRepository with session-specific functionality.
    """

    def __init__(self):
        super().__init__(ChatSession)

    # ---------- Queries ----------

    def get_by_user_id(
        self,
        db: Session,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = False
    ) -> List[ChatSession]:
        """
        Get chat sessions for a user. Sorted by recency (last_message_at desc).
        """
        try:
            q = db.query(ChatSession).filter(ChatSession.user_id == user_id)
            if active_only:
                q = q.filter(ChatSession.is_active.is_(True))
            return (
                q.order_by(desc(ChatSession.last_message_at))
                 .offset(skip)
                 .limit(limit)
                 .all()
            )
        except Exception as e:
            logger.error(f"Error getting sessions for user {user_id}: {e}")
            raise

    def get_active_session(self, db: Session, user_id: int) -> Optional[ChatSession]:
        """
        Get the most recent active session for a user.
        """
        try:
            return (
                db.query(ChatSession)
                  .filter(and_(ChatSession.user_id == user_id, ChatSession.is_active.is_(True)))
                  .order_by(desc(ChatSession.last_message_at))
                  .first()
            )
        except Exception as e:
            logger.error(f"Error getting active session for user {user_id}: {e}")
            raise

    def get_recent_sessions(
        self,
        db: Session,
        user_id: int,
        days: int = 7,
        limit: int = 50
    ) -> List[ChatSession]:
        """
        Get sessions active within the last N days (by last_message_at).
        """
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            return (
                db.query(ChatSession)
                  .filter(and_(ChatSession.user_id == user_id, ChatSession.last_message_at >= cutoff))
                  .order_by(desc(ChatSession.last_message_at))
                  .limit(limit)
                  .all()
            )
        except Exception as e:
            logger.error(f"Error getting recent sessions for user {user_id}: {e}")
            raise

    def search_sessions(
        self,
        db: Session,
        user_id: int,
        search_term: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[ChatSession]:
        """
        Search sessions by title or description.
        """
        try:
            pattern = f"%{search_term}%"
            return (
                db.query(ChatSession)
                  .filter(
                      and_(
                          ChatSession.user_id == user_id,
                          or_(
                              ChatSession.title.ilike(pattern),
                              ChatSession.description.ilike(pattern)
                          )
                      )
                  )
                  .order_by(desc(ChatSession.last_message_at))
                  .offset(skip)
                  .limit(limit)
                  .all()
            )
        except Exception as e:
            logger.error(f"Error searching sessions for user {user_id}: {e}")
            raise

    def get_session_summary(self, db: Session, user_id: int) -> dict:
        """
        Aggregate session stats for a user.
        """
        try:
            total_sessions = self.count(db, {"user_id": user_id})
            active_sessions = self.count(db, {"user_id": user_id, "is_active": True})
            total_messages = (
                db.query(func.sum(ChatSession.message_count))
                  .filter(ChatSession.user_id == user_id)
                  .scalar()
                or 0
            )
            return {
                "total_sessions": total_sessions,
                "active_sessions": active_sessions,
                "total_messages": total_messages,
                "average_messages_per_session": (total_messages / total_sessions) if total_sessions > 0 else 0,
            }
        except Exception as e:
            logger.error(f"Error getting session summary for user {user_id}: {e}")
            raise

    # ---------- Mutations ----------

    def create_session_for_user(
        self,
        db: Session,
        user_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> ChatSession:
        """
        Create a new chat session. last_message_at starts at now().
        """
        try:
            session_data = {
                "user_id": user_id,
                "title": title,               # keep
                #"description": description,   # ← REMOVE THIS
                "summary_text": None,         # optional: or a brief string
                "is_active": True,
            }
            session = self.create(db, session_data)
            # Ensure recency fields initialized
            session.last_message_at = datetime.utcnow()
            db.add(session)
            db.flush()
            db.refresh(session)
            return session
        except Exception as e:
            logger.error(f"Error creating session for user {user_id}: {e}")
            db.rollback()
            raise

    def deactivate_session(self, db: Session, session_id: int) -> ChatSession:
        """
        Mark a session as inactive and stamp ended_at.
        """
        try:
            s = self.get(db, session_id)
            if not s:
                raise ValueError(f"Session {session_id} not found")

            update = SessionUpdate(is_active=False, ended_at=datetime.utcnow())
            return self.update(db, s, update)
        except Exception as e:
            logger.error(f"Error deactivating session {session_id}: {e}")
            db.rollback()
            raise

    def update_message_count(self, db: Session, session_id: int, increment: int = 1) -> ChatSession:
        """
        (Kept for compatibility) Increment message_count; prefer automatic bumps in MessageRepository.
        """
        try:
            s = self.get(db, session_id)
            if not s:
                raise ValueError(f"Session {session_id} not found")
            s.message_count = (s.message_count or 0) + increment
            db.add(s)
            db.flush()
            db.refresh(s)
            logger.info(f"Updated message count for session {session_id} to {s.message_count}")
            return s
        except Exception as e:
            logger.error(f"Error updating message count for session {session_id}: {e}")
            db.rollback()
            raise

    # ---------- Nice-to-have helpers (minimal, optional) ----------

    def set_title_if_empty(self, db: Session, session_id: int, title: str) -> ChatSession:
        """
        Set a title only if not already set (useful to auto-title from first user msg).
        """
        s = self.get(db, session_id)
        if not s:
            raise ValueError(f"Session {session_id} not found")
        if not s.title:
            s.title = title[:255]
            db.add(s)
            db.flush()
            db.refresh(s)
        return s

    def update_summary_text(self, db: Session, session_id: int, summary_text: str) -> ChatSession:
        """
        Cache a brief session summary for sidebar/list views.
        """
        s = self.get(db, session_id)
        if not s:
            raise ValueError(f"Session {session_id} not found")
        s.summary_text = summary_text
        db.add(s)
        db.flush()
        db.refresh(s)
        return s
