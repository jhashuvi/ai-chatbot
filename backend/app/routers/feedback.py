# app/routers/feedback.py
"""
Feedback router for collecting user ratings on assistant responses.
Enables continuous improvement of chatbot quality through user feedback (though not fully incorporated yet, next step).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.message import MessageRepository
from app.repositories.user import UserRepository

router = APIRouter(prefix="/messages", tags=["feedback"])

def get_message_repo() -> MessageRepository:
    """Get a new MessageRepository for this request."""
    return MessageRepository()

def get_user_repo() -> UserRepository:
    """Get a new UserRepository for this request."""
    return UserRepository()

class FeedbackRequest(BaseModel):
    """User feedback on an assistant message."""
    value: int = Field(..., description="1 (upvote), -1 (downvote), or 0 (clear)")

    @model_validator(mode="after")
    def _check_value(self):
        """Validate that feedback value is one of the allowed options."""
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
    """
    Submit feedback on an assistant message.
    """
    if not x_session_id:
        raise HTTPException(status_code=400, detail="Missing X-Session-Id")
    
    # Get or create user based on browser session
    user = users.get_or_create_user(db, session_id=x_session_id)

    msg = repo.get(db, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # Only allow feedback on assistant messages (not user messages)
    if msg.role != "assistant":
        raise HTTPException(status_code=400, detail="Feedback allowed only on assistant messages")
    
    if msg.chat_session.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your message")

    # pUdate the message with the user's rating
    repo.update_user_feedback(db, message_id=message_id, feedback=payload.value)
    
    return
