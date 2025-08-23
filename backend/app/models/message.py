"""
Message model for storing individual messages in chat sessions.
Includes metadata for RAG context, citations, and user feedback tracking.
"""

from sqlalchemy import Column, String, Text, Integer, ForeignKey, Boolean, JSON, Float
from sqlalchemy.orm import relationship
from .base import BaseModel

class Message(BaseModel):
    """
    Message entity that represents a single message in a chat session.
    
    Each message:
    - Belongs to a specific chat session
    - Has a role (user or assistant)
    - Contains the message content
    - Stores metadata for RAG context and analytics
    - Tracks user feedback for model improvement
    """
    
    __tablename__ = "messages"
    
    # Role of the message sender: 'user' or 'assistant'
    role = Column(String(20), nullable=False)
    
    # The actual message content
    content = Column(Text, nullable=False)
    
    # Foreign key to the chat session this message belongs to
    chat_session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    
    # Relationship to the chat session - many messages belong to one session
    chat_session = relationship("ChatSession", back_populates="messages")
    
    # For assistant messages: context chunks used for RAG response
    # Stored as JSON array of chunk metadata
    context_chunks = Column(JSON, nullable=True)
    
    # For assistant messages: citations and sources used
    # Stored as JSON array of citation objects
    citations = Column(JSON, nullable=True)
    
    # For assistant messages: model used for generation
    model_used = Column(String(50), nullable=True)
    
    # For assistant messages: token usage statistics
    tokens_used = Column(Integer, nullable=True)
    
    # For assistant messages: response latency in milliseconds
    latency_ms = Column(Float, nullable=True)
    
    # For assistant messages: retrieval quality metrics
    retrieval_score = Column(Float, nullable=True)
    
    # User feedback: thumbs up/down (1, -1, or None)
    user_feedback = Column(Integer, nullable=True)
    
    # Whether this message was flagged for review
    flagged = Column(Boolean, default=False, nullable=False)
    
    def __repr__(self):
        """String representation for debugging."""
        return f"<Message(id={self.id}, role='{self.role}', chat_session_id={self.chat_session_id})>"
    
    @property
    def is_user_message(self) -> bool:
        """Check if this is a user message."""
        return self.role == "user"
    
    @property
    def is_assistant_message(self) -> bool:
        """Check if this is an assistant message."""
        return self.role == "assistant"
