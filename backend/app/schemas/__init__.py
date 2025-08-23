# Schemas package for API request/response validation

# Base schemas
from .base import BaseSchema, TimestampSchema, IDSchema, BaseResponseSchema

# Common data structures
from .common import Citation, ContextChunk, ChatMetrics, ErrorResponse

# User schemas
from .user import (
    UserCreate, UserLogin, UserUpdate, UserResponse, 
    UserSession, AuthResponse
)

# Session schemas
from .session import (
    SessionCreate, SessionUpdate, SessionResponse, 
    SessionListResponse, SessionSummary
)

# Message schemas
from .message import (
    MessageCreate, MessageUpdate, MessageResponse,
    ChatRequest, ChatResponse, MessageListResponse, MessageFeedback
)

# Export all schemas for easy importing
__all__ = [
    # Base
    "BaseSchema", "TimestampSchema", "IDSchema", "BaseResponseSchema",
    
    # Common
    "Citation", "ContextChunk", "ChatMetrics", "ErrorResponse",
    
    # User
    "UserCreate", "UserLogin", "UserUpdate", "UserResponse", 
    "UserSession", "AuthResponse",
    
    # Session
    "SessionCreate", "SessionUpdate", "SessionResponse", 
    "SessionListResponse", "SessionSummary",
    
    # Message
    "MessageCreate", "MessageUpdate", "MessageResponse",
    "ChatRequest", "ChatResponse", "MessageListResponse", "MessageFeedback"
]
