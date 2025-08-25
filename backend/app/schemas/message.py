"""
Pydantic schemas for Message entity.
Aligned with models.message.Message and repositories.message.MessageRepository.
"""

from typing import Optional, List, Dict, Any, Literal
from pydantic import Field
from datetime import datetime

from .base import BaseSchema, BaseResponseSchema
from .common import (
    SourceRef,
    Citation,
    PromptContextPolicy,
    RetrievalParams,
    RetrievalStats,
)

class MessageCreate(BaseSchema):
    """
    Schema for creating new messages.
    """
    role: Literal["user", "assistant"] = Field(..., description="Message author")
    content: str = Field(..., description="Message text content")
    chat_session_id: int = Field(..., description="Parent chat session id")

class MessageUpdate(BaseSchema):
    """
    Schema for updating message metadata after creation.
    """
    # RAG artifacts / evidence
    sources: Optional[List[SourceRef]] = None
    retrieval_params: Optional[RetrievalParams] = None
    retrieval_stats: Optional[RetrievalStats] = None
    context_policy: Optional[PromptContextPolicy] = None

    # Response state and quality
    answer_type: Optional[Literal["grounded", "abstained", "fallback"]] = None
    error_type: Optional[str] = None

    # Legacy citation support (for backward compatibility)
    citations: Optional[List[Citation]] = None

    # Model usage and performance metrics
    model_provider: Optional[str] = None
    model_used: Optional[str] = None
    tokens_in: Optional[int] = Field(None, ge=0)
    tokens_out: Optional[int] = Field(None, ge=0)
    tokens_used: Optional[int] = Field(None, ge=0)  # total; repo may compute in+out
    latency_ms: Optional[float] = Field(None, ge=0.0)

    # Retrieval quality metrics
    retrieval_score: Optional[float] = Field(None, ge=0.0, le=1.0)

    # User feedback and content moderation
    user_feedback: Optional[int] = Field(None, ge=-1, le=1)  # -1=downvote, 0=clear, 1=upvote
    flagged: Optional[bool] = None


class MessageResponse(BaseResponseSchema):
    """
    Complete message response including all metadata.
    
    This is what gets returned to the frontend, containing both the core
    message content and the metadata for analytics and debugging.
    """
    # Core message fields
    role: Literal["user", "assistant"]
    content: str
    chat_session_id: int

    # RAG-specific fields (typically only present on assistant messages)
    sources: Optional[List[SourceRef]] = None
    retrieval_params: Optional[RetrievalParams] = None
    retrieval_stats: Optional[RetrievalStats] = None
    context_policy: Optional[PromptContextPolicy] = None
    answer_type: Optional[Literal["grounded", "abstained", "fallback"]] = None
    error_type: Optional[str] = None
    citations: Optional[List[Citation]] = None

    # Model usage and performance data
    model_provider: Optional[str] = None
    model_used: Optional[str] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    tokens_used: Optional[int] = None
    latency_ms: Optional[float] = None
    retrieval_score: Optional[float] = None

    # User feedback and moderation status
    user_feedback: Optional[int] = None
    flagged: bool
