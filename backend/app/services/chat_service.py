# app/services/chat_service.py
from __future__ import annotations
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

from app.services.intent_service import IntentService, IntentResult
from app.services.rag_service import RAGService
from app.repositories.message import MessageRepository
from app.repositories.session import ChatSessionRepository


class ChatService:
    """
    Entry point for your /chat endpoint.
    - Classify intent (cheap)
    - Route to canned reply OR RAG
    - Persist messages consistently
    """

    def __init__(
        self,
        *,
        intent_service: Optional[IntentService] = None,
        rag_service: Optional[RAGService] = None,
        msg_repo: Optional[MessageRepository] = None,
        sess_repo: Optional[ChatSessionRepository] = None,
    ):
        self.intent = intent_service or IntentService()
        self.rag = rag_service or RAGService()
        self.msg_repo = msg_repo or MessageRepository()
        self.sess_repo = sess_repo or ChatSessionRepository()

    # ---------------- NEW: auto-title helper ----------------
    def _autotitle_if_empty(self, db: Session, chat_session_id: int, user_text: str) -> None:
        """
        Set a human title from the first user message if the session has no title yet.
        Safe to call every turn: set_title_if_empty only writes when empty.
        """
        try:
            raw = (user_text or "").strip()
            if not raw:
                candidate = "New chat"
            else:
                # collapse whitespace
                candidate = " ".join(raw.split())
                # trim to ~60 chars on a word boundary (but don't cut too short)
                if len(candidate) > 60:
                    head = candidate[:60]
                    cut_at = head.rfind(" ")
                    if cut_at >= 30:
                        candidate = head[:cut_at]
                    else:
                        candidate = head
                # light sentence casing
                candidate = candidate[0].upper() + candidate[1:] if candidate else "New chat"

            self.sess_repo.set_title_if_empty(db, chat_session_id, candidate)
        except Exception:
            # Never let title generation break chat flow
            pass
    # --------------------------------------------------------

    # --- canned responses (keep short & friendly) ---

    @staticmethod
    def _reply_greeting() -> str:
        return "Hey! I can help with account setup, payments & transfers, security, and regulations. What would you like to do?"

    @staticmethod
    def _reply_smalltalk() -> str:
        return "Got it! If you have a question about your account, payments, or security, I’m here to help."

    @staticmethod
    def _reply_off_topic() -> str:
        return "I specialize in our fintech FAQs. Try asking about account setup, payments and transfers, security, or regulations."

    @staticmethod
    def _reply_nonsense() -> str:
        return "I didn’t quite catch that. Could you ask a question about our financial services?"

    def _canned_reply_for_intent(self, intent: str, user_text: str) -> str:
        if intent == "greeting":
            return self._reply_greeting()
        if intent == "smalltalk":
            return self._reply_smalltalk()
        if intent == "off_topic":
            return self._reply_off_topic()
        # default
        return self._reply_nonsense()

    def _send_canned(
        self,
        db: Session,
        chat_session_id: int,
        intent: str,
        confidence: float,
        content: str,
    ):
        """
        Persist ONLY an assistant message for non-RAG paths.
        (Skip create_user_message to match your test policy.)
        """
        asst = self.msg_repo.create_assistant_message(
            db, chat_session_id, content,
            sources=[],
            retrieval_params=None,
            retrieval_stats={"router_intent": intent, "intent_confidence": confidence},
            context_policy=None,
            answer_type="fallback",   # non-RAG path
            model_provider=None,
            model_used=None,
            tokens_in=None, tokens_out=None,
            latency_ms=0.0,
            retrieval_score=None,
        )
        return {"answer": content, "message_id": asst.id, "answer_type": "fallback"}

    # --- public API ---

    def handle_user_message(
        self,
        db: Session,
        chat_session_id: int,
        user_text: str,
        *,
        stream: bool = False,
        history_size: int = 6,
    ):
        """
        Main entry: classify → route
        - For RAG path, let RAGService persist the user message (to avoid double-writes).
        - For non-RAG paths, persist ONLY an assistant message here.
        """
        # ------- NEW: try to auto-title this session (first user turn wins) -------
        self._autotitle_if_empty(db, chat_session_id, user_text)
        # ----------------------------------------------------------------------------

        # small recent history for context bias
        history_msgs = self.msg_repo.get_conversation_history(db, chat_session_id, limit=history_size)
        history_for_intent = [{"role": m.role, "content": m.content} for m in history_msgs]

        result: IntentResult = self.intent.classify(user_text, history_for_intent)
        print("intent_debug:", result.intent, result.confidence, result.signals.get("matched_keywords"))

        # RAG-worthy: let RAG handle persistence & generation
        if result.intent == "fintech_question":
                return self.rag.answer(
                    db,
                    chat_session_id,
                    result.processed_query,
                    stream=stream,
                    category_hint=result.signals.get("category_hint"),
                    intent_confidence=result.confidence,
                )

        # Non-RAG: do NOT persist user message; send a single assistant reply
        content = self._canned_reply_for_intent(result.intent, user_text)
        return self._send_canned(
            db=db,
            chat_session_id=chat_session_id,
            intent=(result.intent or "unknown"),
            confidence=(result.confidence or 0.0),
            content=content,
        )
