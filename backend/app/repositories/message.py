"""
Message repository for managing chat messages.
Handles message storage, retrieval, and RAG context management.
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func
from datetime import datetime
import logging

from .base import BaseRepository
from ..models.message import Message
from ..models.chat_session import ChatSession
from ..schemas.message import MessageCreate, MessageUpdate

logger = logging.getLogger(__name__)


class MessageRepository(BaseRepository[Message, MessageCreate, MessageUpdate]):
    """
    Repository for message management operations.
    Extends BaseRepository with message-specific functionality.
    """

    def __init__(self):
        super().__init__(Message)

    # ---------- Helpers (internal) ----------

    def _touch_session_on_new_message(self, db: Session, session_id: int, is_assistant: bool) -> None:
        """Increment counters and bump recency on the parent session."""
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not session:
            return
        session.message_count = (session.message_count or 0) + 1
        if is_assistant:
            session.assistant_message_count = (session.assistant_message_count or 0) + 1
        session.last_message_at = datetime.utcnow()
        # Keep is_active unless explicitly archived elsewhere
        db.add(session)

    # ---------- Queries ----------

    def get_by_session_id(
        self,
        db: Session,
        chat_session_id: int,
        skip: int = 0,
        limit: int = 100,
        role: Optional[str] = None,
        ascending: bool = True,
    ) -> List[Message]:
        """Get messages for a session with pagination; default chronological order."""
        try:
            q = db.query(Message).filter(Message.chat_session_id == chat_session_id)
            if role:
                q = q.filter(Message.role == role)
            q = q.order_by(Message.created_at if ascending else desc(Message.created_at))
            return q.offset(skip).limit(limit).all()
        except Exception as e:
            logger.error(f"get_by_session_id failed (session={chat_session_id}): {e}")
            raise

    def get_conversation_history(
        self,
        db: Session,
        chat_session_id: int,
        limit: int = 10
    ) -> List[Message]:
        """
        Get the most recent 'limit' messages, returned oldest→newest for prompt assembly.
        """
        try:
            recent = (
                db.query(Message)
                .filter(Message.chat_session_id == chat_session_id)
                .order_by(desc(Message.created_at))
                .limit(limit)
                .all()
            )
            return list(reversed(recent))
        except Exception as e:
            logger.error(f"get_conversation_history failed (session={chat_session_id}): {e}")
            raise

    # ---------- Mutations ----------

    def create_user_message(
        self,
        db: Session,
        chat_session_id: int,
        content: str
    ) -> Message:
        """Create a user message and bump session recency/counters."""
        try:
            msg = self.create(db, MessageCreate(
                content=content,
                chat_session_id=chat_session_id,
                role="user"
            ))
            self._touch_session_on_new_message(db, chat_session_id, is_assistant=False)
            db.flush()
            return msg
        except Exception as e:
            logger.error(f"create_user_message failed (session={chat_session_id}): {e}")
            db.rollback()
            raise

    def create_assistant_message(
        self,
        db: Session,
        chat_session_id: int,
        content: str,
        *,
        # RAG artifacts (normalized)
        sources: Optional[List[Dict[str, Any]]] = None,              # [{id, category, score, title?, preview, content_hash, rank, score_norm?, confidence_bucket?}]
        retrieval_params: Optional[Dict[str, Any]] = None,           # {"top_k":5,"min_score":0.2,"namespace":"__default__","embed_model":"llama-text-embed-v2",...}
        retrieval_stats: Optional[Dict[str, Any]] = None,            # {"best_score":0.349,"kept_hits":3,"n_hits":5,"retrieval_ms":42,"tokens_in":812,"tokens_out":216}
        context_policy: Optional[Dict[str, Any]] = None,             # {"max_chars":6000,"dedupe":"by_root","order":"score_then_category"}
        answer_type: Optional[str] = None,                           # "grounded" | "abstained" | "fallback"
        error_type: Optional[str] = None,

        # Model usage
        model_provider: Optional[str] = None,                        # e.g., "openai"
        model_used: Optional[str] = None,                            # e.g., "gpt-4.1-mini"
        tokens_in: Optional[int] = None,
        tokens_out: Optional[int] = None,
        latency_ms: Optional[float] = None,

        # Back-compat / optional
        citations: Optional[List[Dict[str, Any]]] = None,
        retrieval_score: Optional[float] = None,
        flagged: Optional[bool] = None,
    ) -> Message:
        """
        Create an assistant message with evidence and metrics in one call.
        """
        try:
            msg = self.create(db, MessageCreate(
                content=content,
                chat_session_id=chat_session_id,
                role="assistant"
            ))

            # Build minimal update payload; only set fields that are provided
            update_payload: Dict[str, Any] = {}
            if sources is not None:           update_payload["sources"] = sources
            if retrieval_params is not None:  update_payload["retrieval_params"] = retrieval_params
            if retrieval_stats is not None:   update_payload["retrieval_stats"] = retrieval_stats
            if context_policy is not None:    update_payload["context_policy"] = context_policy
            if answer_type is not None:       update_payload["answer_type"] = answer_type
            if error_type is not None:        update_payload["error_type"] = error_type

            if citations is not None:         update_payload["citations"] = citations
            if model_used is not None:        update_payload["model_used"] = model_used
            if model_provider is not None:    update_payload["model_provider"] = model_provider

            # Prefer separate in/out, keep tokens_used for back-compat/analytics
            if tokens_in is not None:         update_payload["tokens_in"] = tokens_in
            if tokens_out is not None:        update_payload["tokens_out"] = tokens_out
            if tokens_in is not None or tokens_out is not None:
                total = (tokens_in or 0) + (tokens_out or 0)
                update_payload["tokens_used"] = total

            if latency_ms is not None:        update_payload["latency_ms"] = latency_ms
            if retrieval_score is not None:   update_payload["retrieval_score"] = retrieval_score
            if flagged is not None:           update_payload["flagged"] = flagged

            msg = self.update(db, msg, MessageUpdate(**update_payload))

            # bump session counters/recency
            self._touch_session_on_new_message(db, chat_session_id, is_assistant=True)
            db.flush()
            return msg
        except Exception as e:
            logger.error(f"create_assistant_message failed (session={chat_session_id}): {e}")
            db.rollback()
            raise

    def update_user_feedback(
        self,
        db: Session,
        message_id: int,
        feedback: int
    ) -> Message:
        """Update thumbs (1 / -1 / 0) on an assistant message."""
        try:
            msg = self.get(db, message_id)
            if not msg:
                raise ValueError(f"Message {message_id} not found")
            if not msg.is_assistant_message:
                raise ValueError("Can only provide feedback on assistant messages")

            updated = self.update(db, msg, MessageUpdate(user_feedback=feedback))
            return updated
        except Exception as e:
            logger.error(f"update_user_feedback failed (message_id={message_id}): {e}")
            db.rollback()
            raise

    # ---------- Analytics ----------

    def get_message_analytics(
        self,
        db: Session,
        chat_session_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Basic analytics with latency and token summaries on assistant messages."""
        try:
            base_q = db.query(Message)
            if chat_session_id:
                base_q = base_q.filter(Message.chat_session_id == chat_session_id)
            elif user_id:
                base_q = base_q.join(Message.chat_session).filter(
                    Message.chat_session.has(user_id=user_id)
                )

            total_messages = base_q.count()
            user_messages = base_q.filter(Message.role == "user").count()
            assistant_messages = base_q.filter(Message.role == "assistant").count()

            # Assistant-only aggregates
            asst_q = base_q.filter(Message.role == "assistant")

            avg_latency = asst_q.with_entities(func.avg(Message.latency_ms)).scalar() or 0
            total_tokens_in = asst_q.with_entities(func.sum(Message.tokens_in)).scalar() or 0
            total_tokens_out = asst_q.with_entities(func.sum(Message.tokens_out)).scalar() or 0

            # Feedback stats
            positive = asst_q.filter(Message.user_feedback == 1).count()
            negative = asst_q.filter(Message.user_feedback == -1).count()

            # Retrieval quality (best_score mirrored to retrieval_score for quick scans)
            avg_retrieval_score = asst_q.with_entities(func.avg(Message.retrieval_score)).scalar() or 0

            return {
                "total_messages": total_messages,
                "user_messages": user_messages,
                "assistant_messages": assistant_messages,
                "average_latency_ms": float(avg_latency),
                "total_tokens_in": int(total_tokens_in),
                "total_tokens_out": int(total_tokens_out),
                "positive_feedback": positive,
                "negative_feedback": negative,
                "feedback_ratio": (positive / (positive + negative)) if (positive + negative) > 0 else 0.0,
                "avg_retrieval_score": float(avg_retrieval_score),
            }
        except Exception as e:
            logger.error(f"get_message_analytics failed: {e}")
            raise

    # ---------- Search ----------

    def search_messages(
        self,
        db: Session,
        user_id: int,
        search_term: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Message]:
        """Simple LIKE search over message content for a given user."""
        try:
            pattern = f"%{search_term}%"
            return (
                db.query(Message)
                .join(Message.chat_session)
                .filter(
                    and_(
                        Message.chat_session.has(user_id=user_id),
                        Message.content.ilike(pattern),
                    )
                )
                .order_by(desc(Message.created_at))
                .offset(skip)
                .limit(limit)
                .all()
            )
        except Exception as e:
            logger.error(f"search_messages failed (user_id={user_id}): {e}")
            raise

    def get_flagged_messages(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100
    ) -> List[Message]:
        """List messages flagged for review."""
        try:
            return (
                db.query(Message)
                .filter(Message.flagged.is_(True))
                .order_by(desc(Message.created_at))
                .offset(skip)
                .limit(limit)
                .all()
            )
        except Exception as e:
            logger.error(f"get_flagged_messages failed: {e}")
            raise
