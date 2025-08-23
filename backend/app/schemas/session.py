"""
Pydantic schemas for ChatSession entity.
Aligned with models.chat_session.ChatSession and repositories.session.ChatSessionRepository.
"""

from typing import Optional
from datetime import datetime
from pydantic import Field

from .base import BaseSchema, BaseResponseSchema


class SessionCreate(BaseSchema):
    user_id: int = Field(..., description="Owner user id")
    title: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = True  # default active


class SessionUpdate(BaseSchema):
    title: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    summary_text: Optional[str] = None

    # denormalized counters/recency
    message_count: Optional[int] = None
    assistant_message_count: Optional[int] = None
    last_message_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


class SessionResponse(BaseResponseSchema):
    user_id: int
    title: Optional[str] = None
    description: Optional[str] = None
    is_active: bool
    summary_text: Optional[str] = None
    message_count: int
    assistant_message_count: int
    last_message_at: datetime
    ended_at: Optional[datetime] = None
