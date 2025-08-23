"""
ChatSession model for representing individual chat conversations.
Each session contains a series of messages between a user and the AI assistant.
"""

from sqlalchemy import Column, String, Text, Integer, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from .base import BaseModel

class ChatSession(BaseModel):
    """
    Chat session entity that represents a conversation between a user and the AI.
    
    Each session:
    - Belongs to a specific user (anonymous or authenticated)
    - Contains multiple messages in chronological order
    - Can be active (ongoing) or completed
    - Has metadata for analytics and session management
    """
    
    __tablename__ = "chat_sessions"
    
    # Title of the chat session (auto-generated from first message or user-provided)
    title = Column(String(255), nullable=True)
    
    # Description or summary of the conversation
    description = Column(Text, nullable=True)
    
    # Whether this session is currently active (ongoing conversation)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Number of messages in this session (for quick analytics)
    message_count = Column(Integer, default=0, nullable=False)
    
    # Foreign key to the user who owns this session
    # This creates the relationship with the User model
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Relationship to the user - many chat sessions belong to one user
    user = relationship("User", back_populates="chat_sessions")
    
    # Relationship to messages - one chat session has many messages
    # cascade="all, delete-orphan" means if we delete a session, all its messages are deleted too
    messages = relationship("Message", back_populates="chat_session", cascade="all, delete-orphan")
    
    def __repr__(self):
        """String representation for debugging."""
        return f"<ChatSession(id={self.id}, title='{self.title}', user_id={self.user_id}, is_active={self.is_active})>"
