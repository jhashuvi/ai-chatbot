# app/routers/feedback.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.message import MessageRepository
from app.repositories.user import UserRepository

router = APIRouter(prefix="/messages", tags=["feedback"])

# ---- DI ----
def get_message_repo() -> MessageRepository:
    return MessageRepository()

def get_user_repo() -> UserRepository:
    return UserRepository()

# ---- Schemas ----
class FeedbackRequest(BaseModel):
    value: int = Field(..., description="1 (upvote), -1 (downvote), or 0 (clear)")

    @model_validator(mode="after")
    def _check_value(self):
        if self.value not in (-1, 0, 1):
            raise ValueError("value must be one of -1, 0, 1")
        return self

# ---- Route ----
@router.post(
    "/{message_id}/feedback",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Submit thumbs feedback for an assistant message",
)
def leave_feedback(
    message_id: int,
    payload: FeedbackRequest,
    x_session_id: str | None = Header(default=None, convert_underscores=False, alias="X-Session-Id"),
    db: Session = Depends(get_db),
    repo: MessageRepository = Depends(get_message_repo),
    users: UserRepository = Depends(get_user_repo),
):
    # 1) Resolve current user
    if not x_session_id:
        raise HTTPException(status_code=400, detail="Missing X-Session-Id")
    user = users.get_or_create_user(db, session_id=x_session_id)

    # 2) Ownership & validity checks
    msg = repo.get(db, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg.role != "assistant":
        raise HTTPException(status_code=400, detail="Feedback allowed only on assistant messages")
    if msg.chat_session.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your message")

    # 3) Persist
    repo.update_user_feedback(db, message_id=message_id, feedback=payload.value)
    return
