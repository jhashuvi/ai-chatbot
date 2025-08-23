"""
Message repository for managing chat messages.
Handles message storage, retrieval, and RAG context management.
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func
import logging

from .base import BaseRepository
from ..models.message import Message
from ..schemas.message import MessageCreate, MessageUpdate

logger = logging.getLogger(__name__)

class MessageRepository(BaseRepository[Message, MessageCreate, MessageUpdate]):
    """
    Repository for message management operations.
    Extends BaseRepository with message-specific functionality.
    """
    
    def __init__(self):
        super().__init__(Message)
    
    def get_by_session_id(
        self, 
        db: Session, 
        chat_session_id: int, 
        skip: int = 0, 
        limit: int = 100,
        role: Optional[str] = None
    ) -> List[Message]:
        """
        Get messages for a specific chat session with pagination.
        
        Args:
            db: Database session
            chat_session_id: Chat session ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            role: Filter by role ('user' or 'assistant')
            
        Returns:
            List of messages
        """
        try:
            query = db.query(Message).filter(Message.chat_session_id == chat_session_id)
            
            if role:
                query = query.filter(Message.role == role)
            
            return query.order_by(Message.created_at).offset(skip).limit(limit).all()
        except Exception as e:
            logger.error(f"Error getting messages for session {chat_session_id}: {e}")
            raise
    
    def get_conversation_history(
        self, 
        db: Session, 
        chat_session_id: int, 
        limit: int = 10
    ) -> List[Message]:
        """
        Get recent conversation history for context.
        
        Args:
            db: Database session
            chat_session_id: Chat session ID
            limit: Maximum number of recent messages
            
        Returns:
            List of recent messages
        """
        try:
            return db.query(Message).filter(
                Message.chat_session_id == chat_session_id
            ).order_by(desc(Message.created_at)).limit(limit).all()
        except Exception as e:
            logger.error(f"Error getting conversation history for session {chat_session_id}: {e}")
            raise
    
    def create_user_message(
        self, 
        db: Session, 
        chat_session_id: int, 
        content: str
    ) -> Message:
        """
        Create a new user message.
        
        Args:
            db: Database session
            chat_session_id: Chat session ID
            content: Message content
            
        Returns:
            Created message
        """
        try:
            message_data = MessageCreate(
                content=content,
                chat_session_id=chat_session_id,
                role="user"
            )
            return self.create(db, message_data)
        except Exception as e:
            logger.error(f"Error creating user message for session {chat_session_id}: {e}")
            raise
    
    def create_assistant_message(
        self, 
        db: Session, 
        chat_session_id: int, 
        content: str,
        context_chunks: Optional[List[Dict[str, Any]]] = None,
        citations: Optional[List[Dict[str, Any]]] = None,
        model_used: Optional[str] = None,
        tokens_used: Optional[int] = None,
        latency_ms: Optional[float] = None,
        retrieval_score: Optional[float] = None
    ) -> Message:
        """
        Create a new assistant message with RAG context.
        
        Args:
            db: Database session
            chat_session_id: Chat session ID
            content: Message content
            context_chunks: RAG context chunks used
            citations: Source citations
            model_used: AI model used for generation
            tokens_used: Number of tokens used
            latency_ms: Response time in milliseconds
            retrieval_score: Quality score of retrieved context
            
        Returns:
            Created message
        """
        try:
            message_data = MessageCreate(
                content=content,
                chat_session_id=chat_session_id,
                role="assistant"
            )
            
            message = self.create(db, message_data)
            
            # Update RAG context and metrics
            update_data = MessageUpdate(
                context_chunks=context_chunks,
                citations=citations,
                model_used=model_used,
                tokens_used=tokens_used,
                latency_ms=latency_ms,
                retrieval_score=retrieval_score
            )
            
            return self.update(db, message, update_data)
        except Exception as e:
            logger.error(f"Error creating assistant message for session {chat_session_id}: {e}")
            raise
    
    def update_user_feedback(
        self, 
        db: Session, 
        message_id: int, 
        feedback: int
    ) -> Message:
        """
        Update user feedback for a message.
        
        Args:
            db: Database session
            message_id: Message ID
            feedback: User feedback (1, -1, or 0)
            
        Returns:
            Updated message
        """
        try:
            message = self.get(db, message_id)
            if not message:
                raise ValueError(f"Message {message_id} not found")
            
            if not message.is_assistant_message:
                raise ValueError("Can only provide feedback on assistant messages")
            
            update_data = MessageUpdate(user_feedback=feedback)
            return self.update(db, message, update_data)
        except Exception as e:
            logger.error(f"Error updating feedback for message {message_id}: {e}")
            raise
    
    def get_messages_by_user(
        self, 
        db: Session, 
        user_id: int, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Message]:
        """
        Get all messages for a user across all sessions.
        
        Args:
            db: Database session
            user_id: User ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of messages
        """
        try:
            return db.query(Message).join(
                Message.chat_session
            ).filter(
                Message.chat_session.has(user_id=user_id)
            ).order_by(desc(Message.created_at)).offset(skip).limit(limit).all()
        except Exception as e:
            logger.error(f"Error getting messages for user {user_id}: {e}")
            raise
    
    def get_message_analytics(
        self, 
        db: Session, 
        chat_session_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get analytics for messages.
        
        Args:
            db: Database session
            chat_session_id: Optional session ID for session-specific analytics
            user_id: Optional user ID for user-specific analytics
            
        Returns:
            Dictionary with analytics data
        """
        try:
            query = db.query(Message)
            
            if chat_session_id:
                query = query.filter(Message.chat_session_id == chat_session_id)
            elif user_id:
                query = query.join(Message.chat_session).filter(
                    Message.chat_session.has(user_id=user_id)
                )
            
            total_messages = query.count()
            user_messages = query.filter(Message.role == "user").count()
            assistant_messages = query.filter(Message.role == "assistant").count()
            
            # Average response time for assistant messages
            avg_latency = query.filter(
                and_(
                    Message.role == "assistant",
                    Message.latency_ms.isnot(None)
                )
            ).with_entities(func.avg(Message.latency_ms)).scalar() or 0
            
            # Total tokens used
            total_tokens = query.filter(
                and_(
                    Message.role == "assistant",
                    Message.tokens_used.isnot(None)
                )
            ).with_entities(func.sum(Message.tokens_used)).scalar() or 0
            
            # Feedback statistics
            positive_feedback = query.filter(
                and_(
                    Message.role == "assistant",
                    Message.user_feedback == 1
                )
            ).count()
            
            negative_feedback = query.filter(
                and_(
                    Message.role == "assistant",
                    Message.user_feedback == -1
                )
            ).count()
            
            return {
                "total_messages": total_messages,
                "user_messages": user_messages,
                "assistant_messages": assistant_messages,
                "average_latency_ms": avg_latency,
                "total_tokens_used": total_tokens,
                "positive_feedback": positive_feedback,
                "negative_feedback": negative_feedback,
                "feedback_ratio": positive_feedback / (positive_feedback + negative_feedback) if (positive_feedback + negative_feedback) > 0 else 0
            }
        except Exception as e:
            logger.error(f"Error getting message analytics: {e}")
            raise
    
    def search_messages(
        self, 
        db: Session, 
        user_id: int, 
        search_term: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Message]:
        """
        Search messages by content.
        
        Args:
            db: Database session
            user_id: User ID
            search_term: Search term
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of matching messages
        """
        try:
            search_pattern = f"%{search_term}%"
            return db.query(Message).join(
                Message.chat_session
            ).filter(
                and_(
                    Message.chat_session.has(user_id=user_id),
                    Message.content.ilike(search_pattern)
                )
            ).order_by(desc(Message.created_at)).offset(skip).limit(limit).all()
        except Exception as e:
            logger.error(f"Error searching messages for user {user_id}: {e}")
            raise
    
    def get_flagged_messages(
        self, 
        db: Session, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Message]:
        """
        Get messages that have been flagged for review.
        
        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of flagged messages
        """
        try:
            return db.query(Message).filter(
                Message.flagged == True
            ).order_by(desc(Message.created_at)).offset(skip).limit(limit).all()
        except Exception as e:
            logger.error(f"Error getting flagged messages: {e}")
            raise
