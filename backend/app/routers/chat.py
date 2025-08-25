# app/routers/chat.py
"""
Chat router for handling user messages and retrieving conversation history.
"""
from __future__ import annotations
from typing import List, Optional, Literal, Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.chat_service import ChatService
from app.repositories.session import ChatSessionRepository
from app.repositories.message import MessageRepository

from app.schemas.common import SourceRef, ChatMetrics 

router = APIRouter(prefix="/chat", tags=["chat"])

def get_chat_service() -> ChatService:
    """Get a new ChatService for this request."""
    return ChatService()

def get_session_repo() -> ChatSessionRepository:
    """Get a new ChatSessionRepository for this request."""
    return ChatSessionRepository()

def get_message_repo() -> MessageRepository:
    """Get a new MessageRepository for this request."""
    return MessageRepository()

# ------- Local request/response shapes -------
class ChatRequest(BaseModel):
    """Request to send a message to the chatbot."""
    session_id: int = Field(..., ge=1, description="Existing chat_session.id")
    message: str = Field(..., min_length=1, description="User message text")
    history_size: int = Field(6, ge=0, le=50, description="Recent history messages to bias intent")

class ChatResponse(BaseModel):
    """
    Unified response format for both RAG and canned response paths.
    
    This normalizes the output from ChatService so frontend doesn't need to handle
    different response shapes depending on the response type.
    """
    # Core response content
    answer: str = Field(..., description="Assistant answer text")
    answer_type: Literal["grounded", "abstained", "fallback"] = "fallback"
    message_id: Optional[int] = Field(None, description="Assistant message id persisted by repo")
    
    # Session context
    session_id: Optional[int] = Field(None, description="Echo back the session id for the client")
    
    # RAG-specific fields (may be empty for canned responses)
    sources: List[SourceRef] = Field(default_factory=list, description="Normalized evidence items")
    metrics: Optional[ChatMetrics] = Field(None, description="Performance/usage metrics for this turn")

class HistoryItem(BaseModel):
    """Individual message in chat history."""
    id: int
    role: Literal["user", "assistant"]
    content: str
    created_at: str

class HistoryResponse(BaseModel):
    """Complete chat history for a session."""
    session_id: int
    messages: List[HistoryItem]

# ------- Routes -------
@router.post("", response_model=ChatResponse, summary="Send a message to the chatbot")
def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    chat_service: ChatService = Depends(get_chat_service),
    sess_repo: ChatSessionRepository = Depends(get_session_repo),
):
    """
    Main chat endpoint that handles user messages.
        1. Validates the session exists
    2. Delegates to ChatService for message processing
    3. Normalizes the response format for frontend consumption
    """
    # Ensure session exists before processing (avoids hidden 500s inside services)
    session = sess_repo.get(db, payload.session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    try:
        # Delegate to ChatService which handles the core message processing logic
        # This includes intent detection, RAG retrieval, and response generation
        result = chat_service.handle_user_message(
            db,
            payload.session_id,
            payload.message,
            history_size=payload.history_size,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"chat_service failed: {e}",
        )

    # Normalize ChatService response to consistent ChatResponse format
    return ChatResponse(
        session_id=payload.session_id,
        answer=result.get("answer", ""),
        answer_type=result.get("answer_type", "fallback"),
        message_id=result.get("message_id"),

        # Convert source dicts to SourceRef objects if present
        sources=[SourceRef(**s) for s in result.get("sources", [])] if result.get("sources") else [],
        # Convert metrics dict to ChatMetrics object if present
        metrics=ChatMetrics(**result["metrics"]) if isinstance(result.get("metrics"), dict) else None,
    )

@router.get(
    "/history",
    response_model=HistoryResponse,
    summary="Get recent chat history for a session (oldest → newest)",
)
def get_history(
    session_id: int = Query(..., ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    sess_repo: ChatSessionRepository = Depends(get_session_repo),
    msg_repo: MessageRepository = Depends(get_message_repo),
):
    """
    Retrieve chat history for a specific session.
    Returns messages in chronological order (oldest first)
    """
    # Validate that the session exists
    s = sess_repo.get(db, session_id)
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    msgs = msg_repo.get_conversation_history(db, chat_session_id=session_id, limit=limit)
    # Convert database message objects to API response format
    return HistoryResponse(
        session_id=session_id,
        messages=[
            HistoryItem(
                id=m.id,
                role=m.role,                    # Literal["user","assistant"]
                content=m.content,
                created_at=m.created_at.isoformat() if hasattr(m.created_at, "isoformat") else str(m.created_at),
            )
            for m in msgs
        ],
    )
