"""
Chat session repository for managing conversation threads.
Handles session creation, updates, and user session relationships.
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func
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
    
    def get_by_user_id(
        self, 
        db: Session, 
        user_id: int, 
        skip: int = 0, 
        limit: int = 100,
        active_only: bool = False
    ) -> List[ChatSession]:
        """
        Get chat sessions for a specific user with pagination.
        
        Args:
            db: Database session
            user_id: User ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            active_only: If True, return only active sessions
            
        Returns:
            List of chat sessions
        """
        try:
            query = db.query(ChatSession).filter(ChatSession.user_id == user_id)
            
            if active_only:
                query = query.filter(ChatSession.is_active == True)
            
            return query.order_by(desc(ChatSession.created_at)).offset(skip).limit(limit).all()
        except Exception as e:
            logger.error(f"Error getting sessions for user {user_id}: {e}")
            raise
    
    def get_active_session(self, db: Session, user_id: int) -> Optional[ChatSession]:
        """
        Get the most recent active session for a user.
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            Active chat session or None
        """
        try:
            return db.query(ChatSession).filter(
                and_(
                    ChatSession.user_id == user_id,
                    ChatSession.is_active == True
                )
            ).order_by(desc(ChatSession.created_at)).first()
        except Exception as e:
            logger.error(f"Error getting active session for user {user_id}: {e}")
            raise
    
    def create_session_for_user(
        self, 
        db: Session, 
        user_id: int, 
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> ChatSession:
        """
        Create a new chat session for a user.
        
        Args:
            db: Database session
            user_id: User ID
            title: Optional session title
            description: Optional session description
            
        Returns:
            Created chat session
        """
        try:
            session_data = SessionCreate(
                user_id=user_id,
                title=title,
                description=description
            )
            return self.create(db, session_data)
        except Exception as e:
            logger.error(f"Error creating session for user {user_id}: {e}")
            raise
    
    def deactivate_session(self, db: Session, session_id: int) -> ChatSession:
        """
        Mark a session as inactive (completed).
        
        Args:
            db: Database session
            session_id: Session ID
            
        Returns:
            Updated chat session
        """
        try:
            session = self.get(db, session_id)
            if not session:
                raise ValueError(f"Session {session_id} not found")
            
            update_data = SessionUpdate(is_active=False)
            return self.update(db, session, update_data)
        except Exception as e:
            logger.error(f"Error deactivating session {session_id}: {e}")
            raise
    
    def update_message_count(self, db: Session, session_id: int, increment: int = 1) -> ChatSession:
        """
        Update the message count for a session.
        
        Args:
            db: Database session
            session_id: Session ID
            increment: Number to increment by (default 1)
            
        Returns:
            Updated chat session
        """
        try:
            session = self.get(db, session_id)
            if not session:
                raise ValueError(f"Session {session_id} not found")
            
            session.message_count += increment
            db.add(session)
            db.flush()
            db.refresh(session)
            
            logger.info(f"Updated message count for session {session_id} to {session.message_count}")
            return session
        except Exception as e:
            logger.error(f"Error updating message count for session {session_id}: {e}")
            db.rollback()
            raise
    
    def get_session_summary(self, db: Session, user_id: int) -> dict:
        """
        Get summary statistics for a user's sessions.
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            Dictionary with session statistics
        """
        try:
            total_sessions = self.count(db, {"user_id": user_id})
            active_sessions = self.count(db, {"user_id": user_id, "is_active": True})
            total_messages = db.query(func.sum(ChatSession.message_count)).filter(
                ChatSession.user_id == user_id
            ).scalar() or 0
            
            return {
                "total_sessions": total_sessions,
                "active_sessions": active_sessions,
                "total_messages": total_messages,
                "average_messages_per_session": total_messages / total_sessions if total_sessions > 0 else 0
            }
        except Exception as e:
            logger.error(f"Error getting session summary for user {user_id}: {e}")
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
        
        Args:
            db: Database session
            user_id: User ID
            search_term: Search term
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of matching chat sessions
        """
        try:
            search_pattern = f"%{search_term}%"
            return db.query(ChatSession).filter(
                and_(
                    ChatSession.user_id == user_id,
                    or_(
                        ChatSession.title.ilike(search_pattern),
                        ChatSession.description.ilike(search_pattern)
                    )
                )
            ).order_by(desc(ChatSession.created_at)).offset(skip).limit(limit).all()
        except Exception as e:
            logger.error(f"Error searching sessions for user {user_id}: {e}")
            raise
    
    def get_recent_sessions(
        self, 
        db: Session, 
        user_id: int, 
        days: int = 7,
        limit: int = 50
    ) -> List[ChatSession]:
        """
        Get recent sessions within a specified number of days.
        
        Args:
            db: Database session
            user_id: User ID
            days: Number of days to look back
            limit: Maximum number of records to return
            
        Returns:
            List of recent chat sessions
        """
        try:
            from datetime import datetime, timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            return db.query(ChatSession).filter(
                and_(
                    ChatSession.user_id == user_id,
                    ChatSession.created_at >= cutoff_date
                )
            ).order_by(desc(ChatSession.created_at)).limit(limit).all()
        except Exception as e:
            logger.error(f"Error getting recent sessions for user {user_id}: {e}")
            raise
