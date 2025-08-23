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
    role: Literal["user", "assistant"] = Field(..., description="Message author")
    content: str = Field(..., description="Message text content")
    chat_session_id: int = Field(..., description="Parent chat session id")


class MessageUpdate(BaseSchema):
    # RAG artifacts / evidence
    sources: Optional[List[SourceRef]] = None
    retrieval_params: Optional[RetrievalParams] = None
    retrieval_stats: Optional[RetrievalStats] = None
    context_policy: Optional[PromptContextPolicy] = None

    # State
    answer_type: Optional[Literal["grounded", "abstained", "fallback"]] = None
    error_type: Optional[str] = None

    # Optional: if you also keep legacy citation objects
    citations: Optional[List[Citation]] = None

    # Model usage
    model_provider: Optional[str] = None
    model_used: Optional[str] = None
    tokens_in: Optional[int] = Field(None, ge=0)
    tokens_out: Optional[int] = Field(None, ge=0)
    tokens_used: Optional[int] = Field(None, ge=0)  # total; repo may compute in+out
    latency_ms: Optional[float] = Field(None, ge=0.0)

    # Retrieval quality mirror for quick filtering
    retrieval_score: Optional[float] = Field(None, ge=0.0, le=1.0)

    # Feedback/moderation
    user_feedback: Optional[int] = Field(None, ge=-1, le=1)
    flagged: Optional[bool] = None


class MessageResponse(BaseResponseSchema):
    role: Literal["user", "assistant"]
    content: str
    chat_session_id: int

    # Optional RAG fields (assistant only)
    sources: Optional[List[SourceRef]] = None
    retrieval_params: Optional[RetrievalParams] = None
    retrieval_stats: Optional[RetrievalStats] = None
    context_policy: Optional[PromptContextPolicy] = None
    answer_type: Optional[Literal["grounded", "abstained", "fallback"]] = None
    error_type: Optional[str] = None
    citations: Optional[List[Citation]] = None

    # Model usage
    model_provider: Optional[str] = None
    model_used: Optional[str] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    tokens_used: Optional[int] = None
    latency_ms: Optional[float] = None
    retrieval_score: Optional[float] = None

    # Feedback/mod
    user_feedback: Optional[int] = None
    flagged: bool
