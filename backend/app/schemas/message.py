"""
Message schemas for individual chat messages.
Includes RAG context, citations, and user feedback.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from .base import BaseResponseSchema
from .common import Citation, ContextChunk, ChatMetrics

class MessageCreate(BaseModel):
    """
    Schema for creating a new message.
    Used when users send messages to the chatbot.
    """
    
    content: str = Field(..., min_length=1, max_length=2000, description="Message content")
    chat_session_id: int = Field(..., description="ID of the chat session this message belongs to")
    role: str = Field(default="user", description="Message role (user or assistant)")
    
    @field_validator('role')
    @classmethod
    def validate_role(cls, v):
        if v not in ['user', 'assistant']:
            raise ValueError('Role must be either "user" or "assistant"')
        return v

class MessageUpdate(BaseModel):
    """
    Schema for updating message information.
    Primarily used for user feedback on assistant messages.
    """
    
    user_feedback: Optional[int] = Field(None, ge=-1, le=1, description="User feedback: 1 (thumbs up), -1 (thumbs down), 0 (neutral)")
    flagged: Optional[bool] = Field(None, description="Whether the message should be flagged for review")

    context_chunks: Optional[List[Dict[str, Any]]] = None
    citations: Optional[List[Dict[str, Any]]] = None
    model_used: Optional[str] = None
    tokens_used: Optional[int] = Field(None, ge=0)
    latency_ms: Optional[float] = Field(None, ge=0.0)
    retrieval_score: Optional[float] = Field(None, ge=0.0, le=1.0)

class MessageResponse(BaseResponseSchema):
    """
    Schema for message data in API responses.
    Includes message content and metadata.
    """
    
    content: str = Field(..., description="Message content")
    role: str = Field(..., description="Message role (user or assistant)")
    chat_session_id: int = Field(..., description="ID of the chat session")
    
    # RAG context (for assistant messages)
    context_chunks: Optional[List[ContextChunk]] = Field(None, description="Context chunks used for RAG response")
    citations: Optional[List[Citation]] = Field(None, description="Source citations")
    model_used: Optional[str] = Field(None, description="AI model used for generation")
    
    # Performance metrics (for assistant messages)
    tokens_used: Optional[int] = Field(None, ge=0, description="Number of tokens used")
    latency_ms: Optional[float] = Field(None, ge=0.0, description="Response time in milliseconds")
    retrieval_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Quality score of retrieved context")
    
    # User feedback
    user_feedback: Optional[int] = Field(None, ge=-1, le=1, description="User feedback")
    flagged: bool = Field(default=False, description="Whether message is flagged for review")

class ChatRequest(BaseModel):
    """
    Schema for chat requests from the frontend.
    Handles both anonymous and authenticated users.
    """
    
    message: str = Field(..., min_length=1, max_length=2000, description="User's message")
    session_id: Optional[str] = Field(None, description="Browser session identifier (for anonymous users)")
    user_id: Optional[int] = Field(None, description="User ID (for authenticated users)")
    chat_session_id: Optional[int] = Field(None, description="Existing chat session ID (for continuing conversations)")
    
    @field_validator('message')
    @classmethod
    def validate_message_content(cls, v):
        v = ' '.join(v.split())
        if not v.strip():
            raise ValueError('Message cannot be empty after sanitization')
        return v

class ChatResponse(BaseModel):
    """
    Schema for chat responses from the AI assistant.
    Includes the response, citations, and metadata.
    """
    
    response: str = Field(..., description="AI assistant's response")
    message_id: int = Field(..., description="ID of the generated message")
    chat_session_id: int = Field(..., description="ID of the chat session")
    session_id: str = Field(..., description="Browser session identifier")
    
    # RAG context and citations
    citations: List[Citation] = Field(default_factory=list, description="Source citations")
    context_chunks_used: int = Field(..., ge=0, description="Number of context chunks used")
    
    # Performance metrics
    metrics: ChatMetrics = Field(..., description="Performance and analytics metrics")
    
    # Session information
    session_title: Optional[str] = Field(None, description="Title of the chat session")

class MessageListResponse(BaseModel):
    """
    Schema for listing multiple messages in a chat session.
    Used for fetching conversation history.
    """
    
    messages: List[MessageResponse] = Field(..., description="List of messages")
    total_count: int = Field(..., ge=0, description="Total number of messages")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, description="Number of messages per page")
    has_next: bool = Field(..., description="Whether there are more pages")

class MessageFeedback(BaseModel):
    """
    Schema for user feedback on messages.
    Used for thumbs up/down functionality.
    """
    
    message_id: int = Field(..., description="ID of the message to provide feedback on")
    feedback: int = Field(..., ge=-1, le=1, description="Feedback: 1 (thumbs up), -1 (thumbs down), 0 (neutral)")
    comment: Optional[str] = Field(None, max_length=500, description="Optional comment about the feedback")
