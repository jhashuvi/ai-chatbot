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
        - For non-RAG paths, persist both user + assistant here.
        """
        # small recent history for context bias
        history_msgs = self.msg_repo.get_conversation_history(db, chat_session_id, limit=history_size)
        history_for_intent = [{"role": m.role, "content": m.content} for m in history_msgs]

        result: IntentResult = self.intent.classify(user_text, history_for_intent)

        if result.intent == "fintech_question":
            # Let RAG handle persistence and generation, but pass processed query
            return self.rag.answer(db, chat_session_id, result.processed_query, stream=stream)

        # Non-RAG routes: persist user first
        user_msg = self.msg_repo.create_user_message(db, chat_session_id, user_text)

        if result.intent == "greeting":
            content = self._reply_greeting()
            asst = self.msg_repo.create_assistant_message(
                db, chat_session_id, content,
                sources=[],
                retrieval_params=None,
                retrieval_stats={"router_intent": "greeting", "intent_confidence": result.confidence},
                context_policy=None,
                answer_type="non_rag",
                model_provider=None,
                model_used=None,
                tokens_in=None, tokens_out=None,
                latency_ms=0.0,
                retrieval_score=None
            )
            return {"answer": content, "message_id": asst.id, "answer_type": "non_rag"}

        if result.intent == "smalltalk":
            content = self._reply_smalltalk()
            asst = self.msg_repo.create_assistant_message(
                db, chat_session_id, content,
                sources=[],
                retrieval_params=None,
                retrieval_stats={"router_intent": "smalltalk", "intent_confidence": result.confidence},
                context_policy=None,
                answer_type="non_rag",
                model_provider=None,
                model_used=None,
                tokens_in=None, tokens_out=None,
                latency_ms=0.0,
                retrieval_score=None
            )
            return {"answer": content, "message_id": asst.id, "answer_type": "non_rag"}

        if result.intent == "off_topic":
            content = self._reply_off_topic()
            asst = self.msg_repo.create_assistant_message(
                db, chat_session_id, content,
                sources=[],
                retrieval_params=None,
                retrieval_stats={"router_intent": "off_topic", "intent_confidence": result.confidence},
                context_policy=None,
                answer_type="non_rag",
                model_provider=None,
                model_used=None,
                tokens_in=None, tokens_out=None,
                latency_ms=0.0,
                retrieval_score=None
            )
            return {"answer": content, "message_id": asst.id, "answer_type": "non_rag"}

        # default: nonsense
        content = self._reply_nonsense()
        asst = self.msg_repo.create_assistant_message(
            db, chat_session_id, content,
            sources=[],
            retrieval_params=None,
            retrieval_stats={"router_intent": "nonsense", "intent_confidence": result.confidence},
            context_policy=None,
            answer_type="non_rag",
            model_provider=None,
            model_used=None,
            tokens_in=None, tokens_out=None,
            latency_ms=0.0,
            retrieval_score=None
        )
        return {"answer": content, "message_id": asst.id, "answer_type": "non_rag"}
