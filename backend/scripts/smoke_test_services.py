#!/usr/bin/env python3
"""
Smoke test for the service layer:
- Intent classification
- RAG retrieval + generation
- Chat orchestration
- Persistence (users, sessions, messages)

Set USE_FAKES=1 to run without hitting Pinecone/OpenAI.
"""

import os
import sys
from pathlib import Path

# Make "backend" importable
backend_dir = Path(__file__).resolve().parents[1]  # adjust if needed
sys.path.insert(0, str(backend_dir))

from sqlalchemy import func

from app.database import get_db_context
from app.repositories.user import UserRepository
from app.repositories.session import ChatSessionRepository
from app.repositories.message import MessageRepository
from app.services.intent_service import IntentService
from app.services.rag_service import RAGService
from app.services.chat_service import ChatService


USE_FAKES = os.getenv("USE_FAKES", "1") == "1"

# ---------- Optional fakes to keep tests local & deterministic ----------
class _FakePineconeClient:
    def __init__(self):
        self.corpus = [
            {"id": "faq_012", "text": "Why do I need to verify my identity to use your services? ...", "category": "Regulations & Compliance", "score": 0.35},
            {"id": "faq_002", "text": "What information do I need to provide to register an account? ...", "category": "Account & Registration", "score": 0.29},
            {"id": "faq_010", "text": "What should I do if I suspect fraudulent activity on my account? ...", "category": "Security & Fraud Prevention", "score": 0.21},
        ]
    def search(self, text: str, top_k: int = 5):
        hits = []
        low = (text or "").lower()
        for row in self.corpus[:top_k]:
            score = row["score"]
            if "verify" in low and "verify" in row["text"].lower():
                score += 0.1
            hits.append({
                "id": row["id"],
                "score": float(round(score, 3)),
                "fields": {"text": row["text"], "category": row["category"]},
            })
        best = max(h["score"] for h in hits) if hits else None
        return hits, best

class _FakeLLMClient:
    def __init__(self, reply="Grounded answer with citations [1].", model="fake-llm"):
        self._reply = reply
        self.model = model
    def chat(self, system: str, user: str):
        return {"text": self._reply, "tokens_in": 42, "tokens_out": 84, "latency_ms": 12.3}

# ---------- Wiring helpers ----------
def make_rag_service():
    if USE_FAKES:
        return RAGService(
            pinecone_client=_FakePineconeClient(),   # type: ignore[arg-type]
            llm_client=_FakeLLMClient("Answer about verification [1]."),  # type: ignore[arg-type]
            msg_repo=MessageRepository(),
            sess_repo=ChatSessionRepository(),
        )
    # Real clients: RAGService will read from env-configured clients internally
    return RAGService(
        msg_repo=MessageRepository(),
        sess_repo=ChatSessionRepository(),
    )

def make_chat_service():
    return ChatService(
        intent_service=IntentService(enable_llm_fallback=not USE_FAKES),
        rag_service=make_rag_service(),
    )

# ---------- Tests ----------
def test_intent_service():
    print("🧠 Intent Service")
    svc = IntentService(enable_llm_fallback=not USE_FAKES)
    queries = [
        "How do I verify my account?",
        "Hello there!",
        "What are the transfer limits?",
        "Thanks for helping!",
        "Tell me a joke about cats"
    ]
    for q in queries:
        r = svc.classify(q)
        print(f"  {q!r} → {r.intent} (conf={r.confidence:.2f}) | processed={r.processed_query!r}")
    print("✅ Intent OK\n")

def test_rag_service():
    print("🔍 RAG Service")
    with get_db_context() as db:
        user = UserRepository().get_or_create_user(db, "smoke_rag_sess")
        session = ChatSessionRepository().create_session_for_user(db, user.id, "RAG Smoke")

        msg_repo = MessageRepository()
        before_count = db.query(func.count()).select_from(msg_repo.model).scalar()

        rag = make_rag_service()
        q = "How do I verify my identity?"
        out = rag.answer(db, session.id, q)

        after_count = db.query(func.count()).select_from(msg_repo.model).scalar()

        print(f"  Query: {q!r}")
        print(f"  Type : {out['answer_type']}")
        print(f"  Text : {out['answer'][:120]}...")
        print(f"  Srcs : {len(out['sources'])}, best={out.get('metrics',{}).get('best_score')}")
        print(f"  Messages persisted: +{after_count - before_count}")
        assert after_count - before_count == 2, "Should persist user + assistant messages"
    print("✅ RAG OK\n")

def test_chat_service():
    print("💬 Chat Service")
    with get_db_context() as db:
        user = UserRepository().get_or_create_user(db, "smoke_chat_sess")
        session = ChatSessionRepository().create_session_for_user(db, user.id, "Chat Smoke")

        chat = make_chat_service()
        msg_repo = MessageRepository()

        def session_message_count():
            return db.query(func.count()).select_from(msg_repo.model).filter(msg_repo.model.chat_session_id == session.id).scalar()

        before = session_message_count()

        turns = [
            "Hello there!",
            "How do I verify my account?",
            "What are the transfer limits?",
            "Thanks!"
        ]
        for t in turns:
            out = chat.handle_user_message(db, session.id, t)
            print(f"  U: {t!r}\n  A: {out['answer'][:90]}... ({out['answer_type']})\n")

        after = session_message_count()
        print(f"  Messages persisted in this session: +{after - before}")
        assert after - before == len(turns) * 2 - 2, "greeting/smalltalk path should only add assistant once each"
    print("✅ Chat OK\n")

def main():
    print("🚀 Smoke testing services (USE_FAKES=%s)" % ("1" if USE_FAKES else "0"))
    print("=" * 52)
    test_intent_service()
    test_rag_service()
    test_chat_service()
    print("🎉 All service-layer smoke tests passed!")

if __name__ == "__main__":
    main()
