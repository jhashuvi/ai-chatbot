# app/services/rag_service.py
"""
Retrieval-Augmented Generation (RAG) service for fintech FAQ chatbot.
Prioritizes accuracy over completeness, preferring to abstain
rather than provide ungrounded information for fintech queries.
"""
from __future__ import annotations
from typing import Dict, List, Optional, Tuple, Any
from hashlib import sha256
import time
import re

from sqlalchemy.orm import Session

from app.clients.pinecone_client import PineconeIntegratedClient
from app.clients.llm_client import LLMClient
from app.config import settings

from app.repositories.message import MessageRepository
from app.repositories.session import ChatSessionRepository
from app.schemas.common import (
    SourceRef,
    RetrievalParams,
    RetrievalStats,
    PromptContextPolicy,
)

# -------------------------- Utility Functions --------------------------

def _derive_title(text: str) -> str:
    """
    Extract a meaningful title from FAQ text.
    - Look for question mark within reasonable length (5-140 chars)
    - Fall back to first sentence/paragraph break
    - Truncate long text with ellipsis
    """
    s = (text or "").strip()
    if not s:
        return "Untitled FAQ"
    
    # Prefer question-based titles for Q&A format
    qpos = s.find("?")
    if 5 <= qpos <= 140:
        return s[: qpos + 1]
    
    # Look for sentence boundaries
    for sep in [".", "!", "\n"]:
        p = s.find(sep)
        if 10 <= p <= 140:
            return s[: p + 1]
    
    # Fallback: truncate at 80 chars
    return s[:80].rstrip() + ("…" if len(s) > 80 else "")


def _preview(text: str, words: int = 12) -> str:
    """
    Create a short preview of text for UI display.
    Returns first N words with ellipsis if truncated.
    """
    parts = (text or "").split()
    return " ".join(parts[:words]) + ("…" if len(parts) > words else "")


def _split_qa(text: str) -> Tuple[str, str]:
    """
    Split FAQ text into question and answer parts.
    Looks for question mark within first 300 chars to identify Q&A format.
    Returns (question, answer) tuple - question may be empty for non-Q&A text.
    """
    if not text:
        return "", ""
    
    qpos = text.find("?")
    if qpos != -1 and qpos < 300:
        return text[: qpos + 1].strip(), text[qpos + 1 :].strip()
    
    return "", text.strip()


def _normalize_sources(hits: List[Dict[str, Any]]) -> List[SourceRef]:
    """
    Convert raw Pinecone search hits into normalized SourceRef objects.
    """
    out: List[SourceRef] = []
    if not hits:
        return out

    # Calculate score distribution for normalization
    raw_scores = [h.get("score") for h in hits if isinstance(h.get("score"), (int, float))]
    smin, smax = (min(raw_scores), max(raw_scores)) if raw_scores else (0.0, 0.0)

    for i, h in enumerate(hits, 1):
        # Extract core fields from Pinecone response
        cid = (h.get("id") or h.get("chunk_id") or "")
        fields = h.get("metadata") or h.get("fields") or {}
        text = fields.get("text") or h.get("content") or ""
        category = fields.get("category") or (h.get("metadata") or {}).get("category")

        # Handle score normalization and clamping
        raw_score = h.get("score")
        if isinstance(raw_score, (int, float)):
            try:
                score_val = float(raw_score)
                score = score_val if score_val >= 0 else 0.0  # Clamp negatives
            except Exception:
                score = None
        else:
            score = None

        # Generate content hash for deduplication
        try:
            content_hash = sha256(text.encode("utf-8")).hexdigest() if text else None
        except Exception:
            content_hash = None

        # Compute normalized score for relative ranking
        if smax > smin and isinstance(raw_score, (int, float)):
            score_norm = (float(raw_score) - smin) / (smax - smin)
        else:
            score_norm = None

        # Assign confidence bucket for UI 
        bucket = None
        if score_norm is not None:
            bucket = "high" if score_norm >= 0.66 else ("medium" if score_norm >= 0.33 else "low")

        out.append(
            SourceRef(
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
            )
        )
    return out


def _pack_context_for_prompt(sources: List[SourceRef], hits: List[Dict[str, Any]], max_chars: int = 6000) -> str:
    """
    Pack retrieved sources into formatted context for LLM prompt.
    - Maps source IDs to full text content
    - Formats Q&A pairs when possible
    - Respects character limits for context window
    - Creates numbered sections for citation reference (next step: make these clickable)
    """
    # Build lookup from source ID to full text
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
        
        # Format as Q&A if possible, otherwise use full text
        snippet = f"### {s.title}\n"
        if q:
            snippet += f"Q: {q}\nA: {a}\n"
        else:
            snippet += full + "\n"
        snippet += "\n"
        
        # Respect character limit
        if used + len(snippet) <= max_chars:
            parts.append(snippet)
            used += len(snippet)
        else:
            break

    return "".join(parts)


# -------------------------- Main RAG  --------------------------
class RAGService:
    """
    Retrieval-Augmented Generation service for fintech FAQ chatbot.
    
    Complete RAG pipeline for one chat turn:
    1. Store user message in database
    2. Retrieve relevant documents using vector search
    3. Re-rank results using multi-factor scoring
    4. Diversify context to avoid duplicates
    5. Build prompt with retrieved context
    6. Generate answer using LLM 
    7. Verify answer quality and potentially abstain
    8. Store assistant response with full metadata
    
    The service prioritizes accuracy through:
    - Citation requirements for all factual claims (next step: make these clickable)
    - Answer verification to catch hallucination
    - Abstention when confidence is low
    - Comprehensive logging for debugging
    """

    # System prompt enforces citation and accuracy requirements
    SYSTEM_PROMPT = (
        "You are a helpful, accurate assistant for a fintech FAQ.\n"
        "Use ONLY the provided context. If a fact is not in the context, say you don't know.\n"
        "Every factual sentence MUST include an inline citation like [1] or [2].\n"
        "Do NOT state numbers (fees, limits, timing) unless the exact number appears in the cited passage.\n"
        "Prefer concise bullets for policies/fees, steps for procedures, and short definitions for terms.\n"
    )

    def __init__(
        self,
        *,
        pinecone_client: Optional[PineconeIntegratedClient] = None,
        llm_client: Optional[LLMClient] = None,
        msg_repo: Optional[MessageRepository] = None,
        sess_repo: Optional[ChatSessionRepository] = None,
    ):
        """
        Initialize RAG service with configurable components.
        
        Args:
            pinecone_client: Vector search client (defaults to integrated client)
            llm_client: Language model client for generation
            msg_repo: Message persistence repository
            sess_repo: Session management repository
        """
        self.pc = pinecone_client or PineconeIntegratedClient(namespace="__default__")
        self.llm = llm_client or LLMClient(model=settings.OPENAI_MODEL, temperature=0.2)
        self.msg_repo = msg_repo or MessageRepository()
        self.sess_repo = sess_repo or ChatSessionRepository()

        # Configuration for retrieval and context management
        # Small FAQ corpus, so strategy is to retrieve broadly and filter later
        self.top_k = getattr(settings, "RETRIEVAL_TOP_K", 17) # Taken from spec
        self.min_score = getattr(settings, "RETRIEVAL_MIN_SCORE", 0.0)  # No early filtering
        self.max_context_chars = getattr(settings, "CONTEXT_MAX_CHARS", 6000)


    def answer(
        self,
        db: Session,
        chat_session_id: int,
        user_text: str,
        *,
        category_hint: Optional[str] = None,
        intent_confidence: Optional[float] = None,
    ):
        """
        Main entry point for RAG-based question answering.        
        Args:
            db: Database session
            chat_session_id: Chat session identifier
            user_text: User's question
            category_hint: Optional category from intent classification
            intent_confidence: Confidence score from intent service
        Returns:
            Dictionary with answer, message ID, answer type, sources, and metrics
        """
        # Step 1: Persist user message to maintain conversation history
        user_msg = self.msg_repo.create_user_message(db, chat_session_id, user_text)

        # Step 2: Vector search 
        t0 = time.time()
        hits, best = self.pc.search(user_text, top_k=self.top_k)
        retrieval_ms = (time.time() - t0) * 1000.0

        # Step 3: Normalize raw search hits into SourceRef objects
        raw_sources = _normalize_sources(hits)

        # Step 3.1: Multi-stage ranking and diversification
        reranked = self._rerank(
            query=user_text,
            hits=hits,
            raw_sources=raw_sources,
            category_hint=category_hint,
            intent_confidence=(intent_confidence or 0.0),
        )
        sources = self._diversify_by_hash(reranked, top_n=min(10, len(reranked)))

        # Step 4: Handle case where no usable sources found
        if not sources:
            content, followups = self._abstain_message(user_text)
            asst = self.msg_repo.create_assistant_message(
                db,
                chat_session_id,
                content,
                sources=[s.model_dump(exclude_none=True) for s in raw_sources[:3]],
                retrieval_params=RetrievalParams(
                    top_k=self.top_k,
                    min_score=self.min_score,
                    namespace="__default__",
                    index_name=settings.PINECONE_INDEX,
                    embed_model="llama-text-embed-v2",
                ).model_dump(exclude_none=True),
                retrieval_stats=RetrievalStats(
                    best_score=best,
                    kept_hits=len(raw_sources),
                    n_hits=len(hits),
                    retrieval_ms=retrieval_ms,
                ).model_dump(exclude_none=True),
                context_policy=PromptContextPolicy(
                    max_chars=self.max_context_chars, dedupe="by_root", order="score_then_category"
                ).model_dump(exclude_none=True),
                answer_type="abstained",
                model_provider="openai",
                model_used=self.llm.model,
                tokens_in=0,
                tokens_out=0,
                latency_ms=retrieval_ms,
                retrieval_score=(max(best, 0.0) if isinstance(best, (int, float)) else None),
            )
            return {
                "answer": content,
                "message_id": asst.id,
                "answer_type": "abstained",
                "sources": [s.model_dump(exclude_none=True) for s in raw_sources[:3]],
                "metrics": {"abstain_reason": "no_diverse_sources", "suggested_followups": followups},
            }

        # Step 5: Build context and prompt for LLM generation
        context_text = _pack_context_for_prompt(sources, hits, max_chars=self.max_context_chars)
        user_prompt = (
            "Use the context below to answer the user.\n"
            "• Every factual sentence MUST include a citation like [1] or [2].\n"
            "• Do NOT invent numbers; only include fees/limits/timing if present in cited text.\n\n"
            f"---CONTEXT START---\n{context_text}---CONTEXT END---\n\n"
            f"User: {user_text}\n"
            "Answer:"
        )

        # Step 6: Generate answer using LLM
        try:
            result = self.llm.chat(self.SYSTEM_PROMPT, user_prompt)
        except Exception:
            content = (
                "I couldn't reach the model just now. Please try again later, "
                "or ask about account setup, payments, security, or regulations."
            )
            asst = self.msg_repo.create_assistant_message(
                db,
                chat_session_id,
                content,
                sources=[s.model_dump(exclude_none=True) for s in sources],
                retrieval_params=RetrievalParams(
                    top_k=self.top_k,
                    min_score=self.min_score,
                    namespace="__default__",
                    index_name=settings.PINECONE_INDEX,
                    embed_model="llama-text-embed-v2",
                ).model_dump(exclude_none=True),
                retrieval_stats=RetrievalStats(
                    best_score=best, kept_hits=len(sources), n_hits=len(hits), retrieval_ms=retrieval_ms
                ).model_dump(exclude_none=True),
                context_policy=PromptContextPolicy(
                    max_chars=self.max_context_chars, dedupe="by_root", order="score_then_category"
                ).model_dump(exclude_none=True),
                answer_type="abstained",
                error_type="llm_error",
                model_provider="openai",
                model_used=getattr(self.llm, "model", None),
                tokens_in=0,
                tokens_out=0,
                latency_ms=0.0,
                retrieval_score=(max(best, 0.0) if isinstance(best, (int, float)) else None),
            )
            return {
                "answer": content,
                "message_id": asst.id,
                "answer_type": "abstained",
                "sources": [s.model_dump(exclude_none=True) for s in sources],
            }

        # Extract LLM response metrics
        text = result.get("text", "")
        tokens_in = result.get("tokens_in")
        tokens_out = result.get("tokens_out")
        latency_ms_total = retrieval_ms + (result.get("latency_ms") or 0.0)

        # Step 7: Verify answer quality 
        verify = self._verify_answer(text, sources, user_text)
        as_answer_type = "grounded" if verify["confidence"] >= 0.55 else "abstained"
        final_text = text
        if as_answer_type == "abstained":
            followup_text, _ = self._abstain_message(user_text)
            final_text = followup_text

        # Step 8: Persist assistant message with full metadata
        asst = self.msg_repo.create_assistant_message(
            db,
            chat_session_id,
            final_text,
            sources=[s.model_dump(exclude_none=True) for s in sources],
            retrieval_params=RetrievalParams(
                top_k=self.top_k,
                min_score=self.min_score,
                namespace="__default__",
                index_name=settings.PINECONE_INDEX,
                embed_model="llama-text-embed-v2",
            ).model_dump(exclude_none=True),
            retrieval_stats=RetrievalStats(
                best_score=best,
                kept_hits=len(sources),
                n_hits=len(hits),
                retrieval_ms=retrieval_ms,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
            ).model_dump(exclude_none=True),
            context_policy=PromptContextPolicy(
                max_chars=self.max_context_chars, dedupe="by_root", order="score_then_category"
            ).model_dump(exclude_none=True),
            answer_type=as_answer_type,
            model_provider="openai",
            model_used=self.llm.model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms_total,
            retrieval_score=(max(best, 0.0) if isinstance(best, (int, float)) else None),
        )

        return {
            "answer": final_text,
            "message_id": asst.id,
            "answer_type": as_answer_type,
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
                "verification": verify,
            },
        }

    # ----------------------  Helper Methods ----------------------

    def _rerank(
        self,
        query: str,
        hits: List[Dict[str, Any]],
        raw_sources: List[SourceRef],
        category_hint: Optional[str],
        intent_confidence: float,
    ) -> List[SourceRef]:
        """
        Multi-factor re-ranking combining vector scores, lexical overlap, and category hints.
        
        This method improves retrieval quality by:
        - Using vector similarity as primary signal (60% weight)
        - Adding lexical overlap for keyword matching (30% weight)
        - Applying category boost when intent classification provides hints (6-12% boost)
        """
        # Build lookup tables for efficient text/metadata access
        id_to_text: Dict[str, str] = {}
        id_to_meta: Dict[str, Dict[str, Any]] = {}
        for h in hits:
            cid = str(h.get("id") or h.get("chunk_id") or "")
            fields = h.get("metadata") or h.get("fields") or {}
            id_to_text[cid] = fields.get("text") or h.get("content") or ""
            id_to_meta[cid] = fields

        def lexical_overlap(q: str, t: str) -> float:
            """
            Calculate lexical overlap between query and text.
            """
            q_tokens = set(re.findall(r"[a-zA-Z0-9]+", q.lower()))
            t_tokens = set(re.findall(r"[a-zA-Z0-9]+", t.lower()))
            if not q_tokens or not t_tokens:
                return 0.0
            inter = len(q_tokens & t_tokens)
            return min(1.0, inter / max(4, len(q_tokens)))

        # Score each source using multi-factor approach
        ranked: List[Tuple[float, SourceRef]] = []
        for s in raw_sources:
            txt = id_to_text.get(s.id, "")
            meta = id_to_meta.get(s.id, {}) or {}
            
            # Component scores
            pine = (s.score or 0.0)  # Vector similarity score
            lex = lexical_overlap(query, txt)  # Lexical overlap
            
            # Category boost when intent classification provides hints
            cat_boost = 0.0
            if category_hint and isinstance(meta.get("category"), str):
                if meta.get("category", "").lower() == category_hint:
                    # Higher boost for high-confidence intent classifications
                    cat_boost = 0.12 if intent_confidence and intent_confidence >= 0.75 else 0.06
            
            # Weighted combination
            score = (0.6 * pine) + (0.3 * lex) + cat_boost
            ranked.append((score, s))

        # Sort by combined score (descending)
        ranked.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in ranked]

    def _diversify_by_hash(self, ranked: List[SourceRef], top_n: int) -> List[SourceRef]:
        """
        Remove near-duplicate sources to ensure context diversity.
        Uses content hash or title as deduplication key to avoid
        having multiple very similar sources in the context window (due to small corpus).

        """
        seen = set()
        out: List[SourceRef] = []
        for s in ranked:
            key = (s.content_hash or s.title)
            if key in seen:
                continue
            seen.add(key)
            out.append(s)
            if len(out) >= top_n:
                break
        return out

    def _verify_answer(self, text: str, sources: List[SourceRef], query: str) -> Dict[str, Any]:
        """
        Verify answer quality using citation analysis and content checks.
        - Checking that factual claims have citations
        - Verifying cited numbers appear in source text
        - Measuring lexical overlap between claims and sources
        - Ensuring answer covers key query terms
        """
        # Split answer into sentences for analysis
        sentences = [p.strip() for p in re.split(r"(?<=[\.\!\?])\s+", text) if p.strip()]
        if not sentences:
            return {"supported": 0.0, "evidence_density": 0.0, "coverage": 0.0, "confidence": 0.0}

        # Map citation indices to source references
        by_rank = {s.rank: s for s in sources}

        # Check if answer covers key query terms
        q_keys = {
            "fee", "fees", "limit", "limits", "timing", "time", "when",
            "cancel", "reverse", "declined", "failed", "2fa", "password",
            "privacy", "data", "encryption", "verify", "kyc", "id",
        }
        coverage = 1.0 if any(k in text.lower() and k in (query or "").lower() for k in q_keys) else 0.6

        # Analyze citations and factual support
        cited = 0
        supported_hits = 0
        num_pat = re.compile(r"\b\d+(\.\d+)?\b")
        
        for sent in sentences:
            cites = [int(n) for n in re.findall(r"\[(\d+)\]", sent)]
            if cites:
                cited += 1
                ok = False
                
                for n in cites:
                    src = by_rank.get(n)
                    if not src:
                        continue
                    
                    # Check source text for supporting evidence
                    src_text = (src.preview or "") + " " + (src.title or "")
                    
                    # Verify numbers mentioned in sentence appear in source
                    nums = num_pat.findall(sent)
                    if nums and any(num in src_text for num in nums):
                        ok = True
                        break
                    
                    # Check lexical overlap between sentence and source
                    s_tokens = set(w for w in re.findall(r"[a-zA-Z0-9]+", sent.lower()) if len(w) > 2)
                    t_tokens = set(w for w in re.findall(r"[a-zA-Z0-9]+", src_text.lower()) if len(w) > 2)
                    if s_tokens and len(s_tokens & t_tokens) / max(4, len(s_tokens)) >= 0.2:
                        ok = True
                        break
                
                if ok:
                    supported_hits += 1

        # Calculate verification metrics
        evidence_density = cited / max(1, len(sentences))
        supported = supported_hits / max(1, cited)
        confidence = 0.5 * supported + 0.3 * evidence_density + 0.2 * coverage
        
        return {
            "supported": round(supported, 3),
            "evidence_density": round(evidence_density, 3),
            "coverage": round(coverage, 3),
            "confidence": round(confidence, 3),
        }

    def _abstain_message(self, user_text: str) -> Tuple[str, List[str]]:
        """
        When the system cannot provide a grounded answer, it abstains 
        with helpful follow-up questions to guide the user toward more specific queries.
        """
        low = (user_text or "").lower()
        
        # Domain-specific follow-up questions based on query content
        if "password" in low:
            q = "Do you want to change your password while logged in, or reset it if you've forgotten it?"
        elif "freeze" in low or "lock" in low:
            q = "Do you mean temporarily lock your account in the app, or request a full account suspension?"
        elif "fee" in low or "fees" in low or "charge" in low:
            q = "Which service are you asking about—instant transfers, international transfers, or card withdrawals?"
        elif "cancel" in low or "reverse" in low or "declined" in low or "failed" in low:
            q = "Is this about canceling a payment you sent, or a transfer that was declined/failed?"
        else:
            q = "Could you share a bit more detail so I can find the exact policy (e.g., transfer type or feature)?"
        
        msg = f"I don't have enough grounded detail in the FAQs to answer precisely. {q}"
        return msg, [q]
