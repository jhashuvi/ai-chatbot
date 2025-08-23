"""
Message model for storing individual messages in chat sessions.
Includes metadata for RAG context, citations, and user feedback tracking.
"""

from sqlalchemy import Column, String, Text, Integer, ForeignKey, Boolean, JSON, Float
from sqlalchemy.orm import relationship
from .base import BaseModel

class Message(BaseModel):
    """
    Message entity that represents a single message in a chat session.

    For 'assistant' messages, we persist:
    - retrieval_params: what knobs we used (top_k, min_score, namespace, model_name, etc.)
    - retrieval_stats: observed metrics (best_score, kept_hits, latency_ms, tokens, etc.)
    - sources: normalized source refs for citations (id/category/score/title/preview/content_hash)
    - context_policy: how we packed context (caps, dedupe rules)
    - answer_type: 'grounded' | 'abstained' | 'fallback'
    - error_type: set if we failed (e.g., 'PineconeUnavailable', 'EmptyContext')
    """

    __tablename__ = "messages"

    # Role of the message sender: 'user' or 'assistant'
    role = Column(String(20), nullable=False, index=True)

    # The actual message content
    content = Column(Text, nullable=False)

    # Foreign key to the chat session this message belongs to
    chat_session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False, index=True)

    # Relationship to the chat session - many messages belong to one session
    chat_session = relationship("ChatSession", back_populates="messages")

    # ------------------------------
    # RAG artifacts for assistant messages
    # ------------------------------

    # Normalized evidence used to generate this answer
    # Array[SourceRef]: {id, category, score, title?, preview, content_hash, rank, score_norm?, confidence_bucket?}
    sources = Column(JSON, nullable=True)

    # Retrieval knobs we used for this turn
    # e.g., {"top_k":5,"min_score":0.2,"namespace":"__default__","index_name":"...","embed_model":"llama-text-embed-v2"}
    retrieval_params = Column(JSON, nullable=True)

    # Stats we observed during retrieval & generation
    # e.g., {"best_score":0.349,"kept_hits":3,"n_hits":5,"retrieval_ms":42,"tokens_in":812,"tokens_out":216}
    retrieval_stats = Column(JSON, nullable=True)

    # Context packing policy used to build the prompt (for reproducibility)
    # e.g., {"max_chars":6000,"dedupe":"by_root","order":"score_then_category"}
    context_policy = Column(JSON, nullable=True)

    # If the model abstained or we fell back
    # 'grounded' | 'abstained' | 'fallback'
    answer_type = Column(String(20), nullable=True, index=True)

    # If something went wrong this turn (surface in metrics/ops)
    # e.g., "PineconeUnavailable", "EmptyContext", "LLMTimeout"
    error_type = Column(String(50), nullable=True)

    # ------------------------------
    # Citations (optional, if you keep a separate structure)
    # You can keep this or remove it since 'sources' already covers citations well.
    # ------------------------------
    citations = Column(JSON, nullable=True)

    # ------------------------------
    # Model usage & performance (assistant only)
    # ------------------------------

    model_used = Column(String(80), nullable=True)         # e.g., "gpt-4.1-mini"
    model_provider = Column(String(40), nullable=True)     # e.g., "openai"
    tokens_in = Column(Integer, nullable=True)             # prompt tokens
    tokens_out = Column(Integer, nullable=True)            # completion tokens
    tokens_used = Column(Integer, nullable=True)           # total tokens (kept for backward compat)
    latency_ms = Column(Float, nullable=True)              # end-to-end latency for this turn
    retrieval_score = Column(Float, nullable=True)         # optional: duplicate of best_score for quick filtering

    # Feedback & moderation
    user_feedback = Column(Integer, nullable=True)         # thumbs up/down: 1, -1, or None
    flagged = Column(Boolean, default=False, nullable=False)

    def __repr__(self):
        return f"<Message(id={self.id}, role='{self.role}', chat_session_id={self.chat_session_id})>"

    @property
    def is_user_message(self) -> bool:
        return self.role == "user"

    @property
    def is_assistant_message(self) -> bool:
        return self.role == "assistant"
