# app/routers/sessions.py
from __future__ import annotations
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.user import UserRepository
from app.repositories.session import ChatSessionRepository
from app.schemas.session import SessionResponse  # response shape aligned to your model

router = APIRouter(prefix="/sessions", tags=["sessions"])

# ----- DI providers -----
def get_user_repo() -> UserRepository:
    return UserRepository()

def get_session_repo() -> ChatSessionRepository:
    return ChatSessionRepository()

# ----- Request/Response payloads -----
class CreateSessionRequest(BaseModel):
    title: Optional[str] = Field(None, description="Optional session title")

class ListSessionsResponse(BaseModel):
    items: List[SessionResponse]
    next_cursor: Optional[str] = None  # Placeholder if you add cursor pagination later

class SummaryResponse(BaseModel):
    total_sessions: int
    active_sessions: int
    total_messages: int
    average_messages_per_session: float

# ----- Helpers -----
def _require_session_header(x_session_id: Optional[str]) -> str:
    if not x_session_id:
        # Keep this explicit; frontend should pass a browser/session id for anonymous flow
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing X-Session-Id header",
        )
    return x_session_id

def _ensure_ownership(session_obj, user_id: int):
    if not session_obj or session_obj.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

# ----- Routes -----
@router.post(
    "",
    response_model=SessionResponse,
    summary="Create a new chat session (anonymous or authenticated via X-Session-Id)",
)
def create_session(
    payload: CreateSessionRequest,
    x_session_id: Optional[str] = Header(default=None, convert_underscores=False, alias="X-Session-Id"),
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repo),
    sess_repo: ChatSessionRepository = Depends(get_session_repo),
):
    session_id_hdr = _require_session_header(x_session_id)

    # Get or create the user tied to this browser session
    user = user_repo.get_or_create_user(db, session_id=session_id_hdr)

    # Create the chat session
    s = sess_repo.create_session_for_user(db, user_id=user.id, title=payload.title)

    # Refresh to ensure timestamps/counters are present
    db.refresh(s)
    return SessionResponse(
        id=s.id,
        created_at=s.created_at,
        updated_at=s.updated_at,
        user_id=s.user_id,
        title=s.title,
        description=getattr(s, "description", None),
        is_active=s.is_active,
        summary_text=getattr(s, "summary_text", None),
        message_count=s.message_count or 0,
        assistant_message_count=s.assistant_message_count or 0,
        last_message_at=s.last_message_at,
        ended_at=s.ended_at,
    )

@router.get(
    "",
    response_model=ListSessionsResponse,
    summary="List sessions for the current user",
)
def list_sessions(
    active_only: bool = Query(False, description="Only active sessions"),
    search: Optional[str] = Query(None, description="Search by title/description"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    x_session_id: Optional[str] = Header(default=None, convert_underscores=False, alias="X-Session-Id"),
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repo),
    sess_repo: ChatSessionRepository = Depends(get_session_repo),
):
    session_id_hdr = _require_session_header(x_session_id)
    user = user_repo.get_or_create_user(db, session_id=session_id_hdr)

    if search:
        sessions = sess_repo.search_sessions(db, user_id=user.id, search_term=search, skip=skip, limit=limit)
    else:
        sessions = sess_repo.get_by_user_id(db, user_id=user.id, skip=skip, limit=limit, active_only=active_only)

    items = [
        SessionResponse(
            id=s.id,
            created_at=s.created_at,
            updated_at=s.updated_at,
            user_id=s.user_id,
            title=s.title,
            description=getattr(s, "description", None),
            is_active=s.is_active,
            summary_text=getattr(s, "summary_text", None),
            message_count=s.message_count or 0,
            assistant_message_count=s.assistant_message_count or 0,
            last_message_at=s.last_message_at,
            ended_at=s.ended_at,
        )
        for s in sessions
    ]

    # Simple offset pagination for now; add real cursor later if needed
    return ListSessionsResponse(items=items, next_cursor=None)

@router.post(
    "/{session_id}/deactivate",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate (archive) a session",
)
def deactivate_session(
    session_id: int,
    x_session_id: Optional[str] = Header(default=None, convert_underscores=False, alias="X-Session-Id"),
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repo),
    sess_repo: ChatSessionRepository = Depends(get_session_repo),
):
    session_id_hdr = _require_session_header(x_session_id)
    user = user_repo.get_or_create_user(db, session_id=session_id_hdr)

    # Ownership check
    s = sess_repo.get(db, session_id)
    _ensure_ownership(s, user.id)

    # Deactivate
    try:
        sess_repo.deactivate_session(db, session_id=session_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return

@router.get(
    "/summary",
    response_model=SummaryResponse,
    summary="Get per-user session summary stats",
)
def get_summary(
    x_session_id: Optional[str] = Header(default=None, convert_underscores=False, alias="X-Session-Id"),
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repo),
    sess_repo: ChatSessionRepository = Depends(get_session_repo),
):
    session_id_hdr = _require_session_header(x_session_id)
    user = user_repo.get_or_create_user(db, session_id=session_id_hdr)

    stats = sess_repo.get_session_summary(db, user_id=user.id)
    return SummaryResponse(**stats)
