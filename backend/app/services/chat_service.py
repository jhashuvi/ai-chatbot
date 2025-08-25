# app/services/chat_service.py
"""
Chat service for handling user messages and routing to appropriate response systems.
"""
from __future__ import annotations
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

from app.services.intent_service import IntentService, IntentResult
from app.services.rag_service import RAGService
from app.repositories.message import MessageRepository
from app.repositories.session import ChatSessionRepository


class ChatService:
    """
    Entry point for  /chat endpoint.
    
    This service orchestrates the complete chat flow:
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

    def _autotitle_if_empty(self, db: Session, chat_session_id: int, user_text: str) -> None:
        """
        Set a human title from the first user message.
        """
        try:
            raw = (user_text or "").strip()
            if not raw:
                candidate = "New chat"
            else:
                # Collapse whitespace for cleaner titles
                candidate = " ".join(raw.split())
                
                # Trim to ~60 chars on a word boundary (but don't cut too short)
                if len(candidate) > 60:
                    head = candidate[:60]
                    cut_at = head.rfind(" ")
                    if cut_at >= 30:
                        candidate = head[:cut_at]
                    else:
                        candidate = head
                
                # Light sentence casing for readability
                candidate = candidate[0].upper() + candidate[1:] if candidate else "New chat"

            self.sess_repo.set_title_if_empty(db, chat_session_id, candidate)
        except Exception:
            pass

    # --- Canned Response System ---
    @staticmethod
    def _reply_greeting() -> str:
        """Friendly greeting with service overview."""
        return "Hey! I can help with account setup, payments & transfers, security, and regulations. What would you like to do?"

    @staticmethod
    def _reply_smalltalk() -> str:
        """Redirect smalltalk to business topics."""
        return "Got it! If you have a question about your account, payments, or security, I'm here to help."

    @staticmethod
    def _reply_off_topic() -> str:
        """Guide users back to supported topics."""
        return "I specialize in our fintech FAQs. Try asking about account setup, payments and transfers, security, or regulations."

    @staticmethod
    def _reply_nonsense() -> str:
        """Handle unclear or nonsensical input."""
        return "I didn't quite catch that. Could you ask a question about our financial services?"

    def _canned_reply_for_intent(self, intent: str, user_text: str) -> str:
        """Route to appropriate canned response based on intent classification."""
        if intent == "greeting":
            return self._reply_greeting()
        if intent == "smalltalk":
            return self._reply_smalltalk()
        if intent == "off_topic":
            return self._reply_off_topic()
        # Default fallback for unexpected intents
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
        Persist the assistant message for non-RAG paths.
        """
        # Create assistant message with intent metadata
        asst = self.msg_repo.create_assistant_message(
            db, chat_session_id, content,
            sources=[],  # No RAG sources for canned responses
            retrieval_params=None,
            retrieval_stats={"router_intent": intent, "intent_confidence": confidence},
            context_policy=None,
            answer_type="fallback",   # Mark as non-RAG path
            model_provider=None,
            model_used=None,
            tokens_in=None, tokens_out=None,
            latency_ms=0.0,  # Canned responses are instant
            retrieval_score=None,
        )
        
        return {"answer": content, "message_id": asst.id, "answer_type": "fallback"}

    def handle_user_message(
        self,
        db: Session,
        chat_session_id: int,
        user_text: str,
        *,
        history_size: int = 6,
    ):
        """
        Main entry point for handling user messages.
        For RAG path, RAGService handles user message persistence.
        For non-RAG paths, we persist both user and assistant messages here.
        """
        self._autotitle_if_empty(db, chat_session_id, user_text)

        # Get small recent history for context bias in intent classification
        # This helps understand user intent based on conversation flow
        history_msgs = self.msg_repo.get_conversation_history(db, chat_session_id, limit=history_size)
        history_for_intent = [{"role": m.role, "content": m.content} for m in history_msgs]

        # Classify user intent using the intent service
        result: IntentResult = self.intent.classify(user_text, history_for_intent)
        print("intent_debug:", result.intent, result.confidence, result.signals.get("matched_keywords"))

        # Route to RAG if this is a fintech question
        if result.intent == "fintech_question":
            # Let RAGService handle persistence & generation
            return self.rag.answer(
                db,
                chat_session_id,
                result.processed_query,
                category_hint=result.signals.get("category_hint"),
                intent_confidence=result.confidence,
            )

        # Non-RAG path: persist the user message first (so history is complete)
        # This ensures we have a complete conversation record
        self.msg_repo.create_user_message(db, chat_session_id, user_text)

        # Generate and persist canned response
        content = self._canned_reply_for_intent(result.intent, user_text)
        return self._send_canned(
            db=db,
            chat_session_id=chat_session_id,
            intent=(result.intent or "unknown"),
            confidence=(result.confidence or 0.0),
            content=content,
        )
