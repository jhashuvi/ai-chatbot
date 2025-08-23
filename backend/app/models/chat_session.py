"""
ChatSession model for representing individual chat conversations.
Each session contains a series of messages between a user and the AI assistant.
"""

from sqlalchemy import Column, String, Text, Integer, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import BaseModel

class ChatSession(BaseModel):
    """
    Chat session entity that represents a conversation between a user and the AI.

    Minimal upgrades:
    - last_message_at: quick sort/filter in UI
    - ended_at: mark a session closed without deleting
    - assistant_message_count: handy metric
    - summary_text: cached short summary for sidebar (optional, cheap)
    """

    __tablename__ = "chat_sessions"

    # Title of the chat session (auto-generated from first message or user-provided)
    title = Column(String(255), nullable=True)

    # Cached short summary for sidebar/list views (keep brief)
    summary_text = Column(Text, nullable=True)

    # Whether this session is currently active (ongoing conversation)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Number of messages in this session (for quick analytics)
    message_count = Column(Integer, default=0, nullable=False)

    # Assistant-only message count (useful for metrics, confidence visuals)
    assistant_message_count = Column(Integer, default=0, nullable=False)

    # Recency fields for sorting/grouping in UI
    last_message_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    ended_at = Column(DateTime, nullable=True)

    # Foreign key to the user who owns this session
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Relationship to the user - many chat sessions belong to one user
    user = relationship("User", back_populates="chat_sessions")

    # Relationship to messages - one chat session has many messages
    # cascade="all, delete-orphan" means if we delete a session, all its messages are deleted too
    messages = relationship("Message", back_populates="chat_session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ChatSession(id={self.id}, title='{self.title}', user_id={self.user_id}, is_active={self.is_active})>"
