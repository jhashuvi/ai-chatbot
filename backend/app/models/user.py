"""
User model for handling both anonymous and authenticated users.
"""
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from .base import BaseModel

class User(BaseModel):
    """
    User entity that supports both anonymous and authenticated users.
    
    For anonymous users:
    - session_id is used to track them across visits
    - is_authenticated is False
    - email is None
    
    For authenticated users:
    - session_id is still used for session management
    - is_authenticated is True
    - email is required for authentication
    """
    
    __tablename__ = "users"
    
    # Session identifier - used for both anonymous and authenticated users
    session_id = Column(String(255), unique=True, index=True, nullable=False)
    
    # Email for authenticated users (nullable for anonymous users)
    email = Column(String(255), unique=True, index=True, nullable=True)
    
    # Password hash for authenticated users
    password_hash = Column(String(255), nullable=True)
    
    # Whether this user has authenticated (False for anonymous users)
    is_authenticated = Column(Boolean, default=False, nullable=False)
    
    # Last login timestamp 
    last_login_at = Column(DateTime, nullable=True)
    
    # Relationship to chat sessions - one user can have many chats
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        """String representation for debugging."""
        return f"<User(id={self.id}, session_id='{self.session_id}', is_authenticated={self.is_authenticated})>"
