# app/services/rag_service.py
from __future__ import annotations
from typing import Dict, List, Optional, Tuple, Any
from hashlib import sha256
import time

from sqlalchemy.orm import Session

from app.clients.pinecone_client import PineconeIntegratedClient
from app.clients.llm_client import LLMClient
from app.config import settings

from app.repositories.message import MessageRepository
from app.repositories.session import ChatSessionRepository
from app.schemas.common import SourceRef, RetrievalParams, RetrievalStats, PromptContextPolicy


def _derive_title(text: str) -> str:
    s = (text or "").strip()
    if not s:
        return "Untitled FAQ"
    qpos = s.find("?")
    if 5 <= qpos <= 140:
        return s[: qpos + 1]
    for sep in [".", "!", "\n"]:
        p = s.find(sep)
        if 10 <= p <= 140:
            return s[: p + 1]
    return s[:80].rstrip() + ("…" if len(s) > 80 else "")

def _preview(text: str, words: int = 12) -> str:
    parts = (text or "").split()
    return " ".join(parts[:words]) + ("…" if len(parts) > words else "")

def _split_qa(text: str):
    if not text:
        return "", ""
    qpos = text.find("?")
    if qpos != -1 and qpos < 300:
        return text[: qpos + 1].strip(), text[qpos + 1 :].strip()
    return "", text.strip()

def _normalize_sources(hits: List[Dict[str, Any]]) -> List[SourceRef]:
    out: List[SourceRef] = []
    if not hits:
        return out
    scores = [h.get("score") for h in hits if isinstance(h.get("score"), (int, float))]
    smin, smax = (min(scores), max(scores)) if scores else (0.0, 0.0)

    for i, h in enumerate(hits, 1):
        cid = (h.get("id") or h.get("chunk_id") or "")
        fields = h.get("metadata") or h.get("fields") or {}
        text = fields.get("text") or h.get("content") or ""
        category = fields.get("category") or (h.get("metadata") or {}).get("category")
        score = h.get("score")

        try:
            content_hash = sha256(text.encode("utf-8")).hexdigest() if text else None
        except Exception:
            content_hash = None

        if smax > smin:
            score_norm = (float(score) - smin) / (smax - smin) if isinstance(score, (int, float)) else None
        else:
            score_norm = None

        bucket = None
        if score_norm is not None:
            bucket = "high" if score_norm >= 0.66 else ("medium" if score_norm >= 0.33 else "low")

        out.append(SourceRef(
            id=str(cid),
            category=category,
            score=score if isinstance(score, (int, float)) else None,
            title=_derive_title(text),
            preview=_preview(text),
            content_hash=content_hash,
            rank=i,
            score_norm=score_norm,
            confidence_bucket=bucket,
            index_name=settings.PINECONE_INDEX,
            namespace="__default__",
            model_name="llama-text-embed-v2",
        ))
    return out

def _pack_context_for_prompt(sources: List[SourceRef], hits: List[Dict[str, Any]], max_chars: int = 6000) -> str:
    by_id = {}
    for h in hits:
        cid = (h.get("id") or h.get("chunk_id") or "")
        fields = h.get("metadata") or h.get("fields") or {}
        by_id[str(cid)] = fields.get("text") or h.get("content") or ""

    parts: List[str] = []
    used = 0
    for s in sources:
        full = by_id.get(s.id, "")
        q, a = _split_qa(full)
        snippet = f"### {s.title}\n"
        if q:
            snippet += f"Q: {q}\nA: {a}\n"
        else:
            snippet += full + "\n"
        snippet += "\n"
        if used + len(snippet) <= max_chars:
            parts.append(snippet)
            used += len(snippet)
        else:
            break

    return "".join(parts)


class RAGService:
    """
    Orchestrates one chat turn:
    - stores user message
    - retrieves context
    - abstains on low-signal
    - builds prompt
    - calls LLM
    - stores assistant message with sources & metrics
    """

    SYSTEM_PROMPT = (
        "You are a helpful, accurate assistant for a fintech FAQ.\n"
        "Answer ONLY using the provided context. If the answer is not in the context, say you don't know.\n"
        "Keep answers concise, structured, and safe. Do not invent details.\n"
    )

    def __init__(
        self,
        *,
        pinecone_client: Optional[PineconeIntegratedClient] = None,
        llm_client: Optional[LLMClient] = None,
        msg_repo: Optional[MessageRepository] = None,
        sess_repo: Optional[ChatSessionRepository] = None,
    ):
        self.pc = pinecone_client or PineconeIntegratedClient(namespace="__default__")
        self.llm = llm_client or LLMClient(model=settings.OPENAI_MODEL, temperature=0.2)
        self.msg_repo = msg_repo or MessageRepository()
        self.sess_repo = sess_repo or ChatSessionRepository()

        self.top_k = getattr(settings, "RETRIEVAL_TOP_K", 5)
        self.min_score = getattr(settings, "RETRIEVAL_MIN_SCORE", 0.18)
        self.max_context_chars = getattr(settings, "CONTEXT_MAX_CHARS", 6000)

    def answer(
        self,
        db: Session,
        chat_session_id: int,
        user_text: str,
        *,
        stream: bool = False,
    ):
        # 1) persist user message
        user_msg = self.msg_repo.create_user_message(db, chat_session_id, user_text)

        # 2) retrieve
        t0 = time.time()
        hits, best = self.pc.search(user_text, top_k=self.top_k)
        retrieval_ms = (time.time() - t0) * 1000.0

        # 3) normalize sources
        sources = _normalize_sources(hits)

        # 4) abstain
        if best is None or (isinstance(best, (int, float)) and best < self.min_score):
            content = (
                "I’m not fully confident I can answer that from the available FAQs. "
                "Could you rephrase or ask a question about account setup, payments, security, or regulations?"
            )
            asst = self.msg_repo.create_assistant_message(
                db, chat_session_id, content,
                sources=[s.model_dump(exclude_none=True) for s in sources],
                retrieval_params=RetrievalParams(
                    top_k=self.top_k, min_score=self.min_score,
                    namespace="__default__", index_name=settings.PINECONE_INDEX,
                    embed_model="llama-text-embed-v2"
                ).model_dump(exclude_none=True),
                retrieval_stats=RetrievalStats(
                    best_score=best, kept_hits=len(sources), n_hits=len(hits),
                    retrieval_ms=retrieval_ms
                ).model_dump(exclude_none=True),
                context_policy=PromptContextPolicy(
                    max_chars=self.max_context_chars, dedupe="by_root", order="score_then_category"
                ).model_dump(exclude_none=True),
                answer_type="abstained",
                model_provider="openai",
                model_used=self.llm.model,
                tokens_in=0, tokens_out=0,
                latency_ms=retrieval_ms,
                retrieval_score=best if isinstance(best, (int, float)) else None,
            )
            return {
                "answer": content,
                "message_id": asst.id,
                "answer_type": "abstained",
                "sources": [s.model_dump(exclude_none=True) for s in sources],
            }

        # 5) pack & prompt
        context_text = _pack_context_for_prompt(sources, hits, max_chars=self.max_context_chars)
        user_prompt = (
            "Use the context below to answer the user. Cite inline as [1], [2] in order of relevance.\n\n"
            f"---CONTEXT START---\n{context_text}---CONTEXT END---\n\n"
            f"User: {user_text}\n"
            "Answer:"
        )

        # 6) LLM
        try:
            result = self.llm.chat(self.SYSTEM_PROMPT, user_prompt, stream=stream)
        except Exception as e:
            # graceful fallback: persist an abstain with error tag
            content = (
                "I couldn’t reach the model just now. Please try again later, "
                "or ask about account setup, payments, security, or regulations."
            )
            asst = self.msg_repo.create_assistant_message(
                db, chat_session_id, content,
                sources=[s.model_dump(exclude_none=True) for s in sources],
                retrieval_params=RetrievalParams(
                    top_k=self.top_k, min_score=self.min_score,
                    namespace="__default__", index_name=settings.PINECONE_INDEX,
                    embed_model="llama-text-embed-v2"
                ).model_dump(exclude_none=True),
                retrieval_stats=RetrievalStats(
                    best_score=best, kept_hits=len(sources), n_hits=len(hits),
                    retrieval_ms=retrieval_ms
                ).model_dump(exclude_none=True),
                context_policy=PromptContextPolicy(
                    max_chars=self.max_context_chars, dedupe="by_root", order="score_then_category"
                ).model_dump(exclude_none=True),
                answer_type="abstained",
                error_type="llm_error",
                model_provider="openai",
                model_used=getattr(self.llm, "model", None),
                tokens_in=0, tokens_out=0, latency_ms=0.0,
                retrieval_score=best if isinstance(best, (int, float)) else None,
            )
            return {
                "answer": content,
                "message_id": asst.id,
                "answer_type": "abstained",
                "sources": [s.model_dump(exclude_none=True) for s in sources],
            }

        text = result["text"]
        tokens_in = result.get("tokens_in")
        tokens_out = result.get("tokens_out")
        latency_ms_total = retrieval_ms + (result.get("latency_ms") or 0.0)

        asst = self.msg_repo.create_assistant_message(
            db, chat_session_id, text,
            sources=[s.model_dump(exclude_none=True) for s in sources],
            retrieval_params=RetrievalParams(
                top_k=self.top_k, min_score=self.min_score,
                namespace="__default__", index_name=settings.PINECONE_INDEX,
                embed_model="llama-text-embed-v2"
            ).model_dump(exclude_none=True),
            retrieval_stats=RetrievalStats(
                best_score=best, kept_hits=len(sources), n_hits=len(hits),
                retrieval_ms=retrieval_ms, tokens_in=tokens_in, tokens_out=tokens_out
            ).model_dump(exclude_none=True),
            context_policy=PromptContextPolicy(
                max_chars=self.max_context_chars, dedupe="by_root", order="score_then_category"
            ).model_dump(exclude_none=True),
            answer_type="grounded",
            model_provider="openai",
            model_used=self.llm.model,
            tokens_in=tokens_in, tokens_out=tokens_out,
            latency_ms=latency_ms_total,
            retrieval_score=best,
        )

        return {
            "answer": text,
            "message_id": asst.id,
            "answer_type": "grounded",
            "sources": [s.model_dump(exclude_none=True) for s in sources],
            "metrics": {
                "best_score": best,
                "kept_hits": len(sources),
                "n_hits": len(hits),
                "retrieval_ms": retrieval_ms,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "latency_ms": latency_ms_total,
                "context_chunks_used": len(sources),
            },
        }
