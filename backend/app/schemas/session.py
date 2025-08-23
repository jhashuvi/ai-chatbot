"""
Chat session schemas for managing conversation threads.
Handles session creation, updates, and responses.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from .base import BaseResponseSchema
from .user import UserResponse

class SessionCreate(BaseModel):
    """
    Schema for creating a new chat session.
    Used when users start a new conversation.
    """
    
    title: Optional[str] = Field(None, max_length=255, description="Session title (auto-generated if not provided)")
    description: Optional[str] = Field(None, description="Session description")
    session_id: Optional[str] = Field(None, description="Browser session identifier (for anonymous users)")
    user_id: Optional[int] = Field(None, description="User ID (for authenticated users)")

class SessionUpdate(BaseModel):
    """
    Schema for updating chat session information.
    Allows users to modify session metadata.
    """
    
    title: Optional[str] = Field(None, max_length=255, description="New session title")
    description: Optional[str] = Field(None, description="New session description")
    is_active: Optional[bool] = Field(None, description="Whether the session is active")

class SessionResponse(BaseResponseSchema):
    """
    Schema for chat session data in API responses.
    Includes session metadata and user information.
    """
    
    title: Optional[str] = Field(None, description="Session title")
    description: Optional[str] = Field(None, description="Session description")
    is_active: bool = Field(..., description="Whether the session is currently active")
    message_count: int = Field(..., ge=0, description="Number of messages in this session")
    user_id: int = Field(..., description="ID of the user who owns this session")
    
    # Optional user information (for authenticated users)
    user: Optional[UserResponse] = Field(None, description="User information")

class SessionListResponse(BaseModel):
    """
    Schema for listing multiple chat sessions.
    Used when fetching user's conversation history.
    """
    
    sessions: List[SessionResponse] = Field(..., description="List of chat sessions")
    total_count: int = Field(..., ge=0, description="Total number of sessions")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, description="Number of sessions per page")
    has_next: bool = Field(..., description="Whether there are more pages")

class SessionSummary(BaseModel):
    """
    Schema for session summary information.
    Used for quick overview of conversation history.
    """
    
    id: int = Field(..., description="Session ID")
    title: Optional[str] = Field(None, description="Session title")
    message_count: int = Field(..., ge=0, description="Number of messages")
    is_active: bool = Field(..., description="Whether session is active")
    last_message_at: Optional[datetime] = Field(None, description="When the last message was sent")
    created_at: datetime = Field(..., description="When the session was created")
