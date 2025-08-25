# app/routers/chat.py
from __future__ import annotations
from typing import List, Optional, Literal, Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.chat_service import ChatService
from app.repositories.session import ChatSessionRepository
from app.repositories.message import MessageRepository

# Reuse your shared schema pieces for sources/metrics/history
from app.schemas.common import SourceRef, ChatMetrics  # type: ignore

router = APIRouter(prefix="/chat", tags=["chat"])

# ------- DI providers -------
def get_chat_service() -> ChatService:
    return ChatService()

def get_session_repo() -> ChatSessionRepository:
    return ChatSessionRepository()

def get_message_repo() -> MessageRepository:
    return MessageRepository()

# ------- Local request/response shapes (thin wrappers around your shared parts) -------
class ChatRequest(BaseModel):
    session_id: int = Field(..., ge=1, description="Existing chat_session.id")
    message: str = Field(..., min_length=1, description="User message text")
    history_size: int = Field(6, ge=0, le=50, description="Recent history messages to bias intent")

class ChatResponse(BaseModel):
    # Minimal common surface your ChatService returns on both canned and RAG paths
    answer: str = Field(..., description="Assistant answer text")
    answer_type: Literal["grounded", "abstained", "fallback"] = "fallback"
    message_id: Optional[int] = Field(None, description="Assistant message id persisted by repo")
    # Optional evidence + metrics (present on RAG path; allowed to be empty for canned)
    session_id: Optional[int] = Field(None, description="Echo back the session id for the client")
    sources: List[SourceRef] = Field(default_factory=list, description="Normalized evidence items")
    metrics: Optional[ChatMetrics] = Field(None, description="Performance/usage metrics for this turn")

class HistoryItem(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    content: str
    created_at: str

class HistoryResponse(BaseModel):
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
    # Ensure session exists (avoids hidden 500s inside services)
    session = sess_repo.get(db, payload.session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    try:
        result = chat_service.handle_user_message(
            db,
            payload.session_id,
            payload.message,
            history_size=payload.history_size,
        )
    except HTTPException:
        # bubble up any explicit API errors thrown from inside
        raise
    except Exception as e:
        # Normalize unexpected failures
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"chat_service failed: {e}",
        )

    # Your ChatService returns a dict on both paths. We normalize to ChatResponse.
    # On RAG path we expect keys like: answer, answer_type, message_id, sources, metrics (optional).
    # On canned path (_send_canned) we get: answer, message_id, answer_type='fallback'.
    return ChatResponse(
        session_id=payload.session_id,
        answer=result.get("answer", ""),
        answer_type=result.get("answer_type", "fallback"),
        message_id=result.get("message_id"),
        sources=[SourceRef(**s) for s in result.get("sources", [])] if result.get("sources") else [],
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
    s = sess_repo.get(db, session_id)
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # Uses your repository method that returns oldest→newest after internal reverse
    msgs = msg_repo.get_conversation_history(db, chat_session_id=session_id, limit=limit)

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
