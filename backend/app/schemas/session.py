"""
Pydantic schemas for ChatSession entity.
"""

from typing import Optional
from datetime import datetime
from pydantic import Field

from .base import BaseSchema, BaseResponseSchema


class SessionCreate(BaseSchema):
    """
    Schema for creating new chat sessions.
    """
    user_id: int = Field(..., description="Owner user id")
    title: Optional[str] = None  
    description: Optional[str] = None  
    is_active: Optional[bool] = True  # Sessions start active by default


class SessionUpdate(BaseSchema):
    """
    Schema for updating existing chat sessions.
    """
    # Basic session properties
    title: Optional[str] = None
    description: Optional[str] = None  
    is_active: Optional[bool] = None
    summary_text: Optional[str] = None

    message_count: Optional[int] = None
    assistant_message_count: Optional[int] = None
    last_message_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


class SessionResponse(BaseResponseSchema):
    """
    Complete session data returned to the frontend.
    
    This includes all session information needed for:
    - Displaying session lists and details
    - Analytics and user insights
    - Session management operations
    """
    # Core session identity
    user_id: int
    title: Optional[str] = None
    description: Optional[str] = None  
    is_active: bool
    
    # Cached content for quick display
    summary_text: Optional[str] = None
    
    # Message statistics and engagement metrics
    message_count: int
    assistant_message_count: int
    
    # Activity timestamps 
    last_message_at: datetime
    ended_at: Optional[datetime] = None
