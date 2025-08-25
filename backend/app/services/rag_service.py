# app/services/rag_service.py
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


# ---------------------- helpers for source packing ----------------------


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
    """
    Convert raw Pinecone hits into SourceRef with clamped scores (>= 0),
    and a normalized score bucket for UI/debugging.
    """
    out: List[SourceRef] = []
    if not hits:
        return out

    raw_scores = [h.get("score") for h in hits if isinstance(h.get("score"), (int, float))]
    smin, smax = (min(raw_scores), max(raw_scores)) if raw_scores else (0.0, 0.0)

    for i, h in enumerate(hits, 1):
        cid = (h.get("id") or h.get("chunk_id") or "")
        fields = h.get("metadata") or h.get("fields") or {}
        text = fields.get("text") or h.get("content") or ""
        category = fields.get("category") or (h.get("metadata") or {}).get("category")

        # Clamp negatives for schema validation
        raw_score = h.get("score")
        if isinstance(raw_score, (int, float)):
            try:
                score_val = float(raw_score)
                score = score_val if score_val >= 0 else 0.0
            except Exception:
                score = None
        else:
            score = None

        try:
            content_hash = sha256(text.encode("utf-8")).hexdigest() if text else None
        except Exception:
            content_hash = None

        # Normalized score uses original distribution (including negatives) for relative ordering
        if smax > smin and isinstance(raw_score, (int, float)):
            score_norm = (float(raw_score) - smin) / (smax - smin)
        else:
            score_norm = None

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


# -------------------------- main service --------------------------


class RAGService:
    """
    One chat turn:
    - stores user message
    - retrieves broadly
    - re-ranks & diversifies
    - builds prompt with guardrails
    - LLM generate
    - verifies & may abstain with helpful follow-up
    - stores assistant message with sources & metrics
    """

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
        self.pc = pinecone_client or PineconeIntegratedClient(namespace="__default__")
        self.llm = llm_client or LLMClient(model=settings.OPENAI_MODEL, temperature=0.2)
        self.msg_repo = msg_repo or MessageRepository()
        self.sess_repo = sess_repo or ChatSessionRepository()

        # Tiny corpus → retrieve broadly and decide later
        self.top_k = getattr(settings, "RETRIEVAL_TOP_K", 17)
        self.min_score = getattr(settings, "RETRIEVAL_MIN_SCORE", 0.0)  # no early gate
        self.max_context_chars = getattr(settings, "CONTEXT_MAX_CHARS", 6000)

    # ---------------------- public API ----------------------

    def answer(
        self,
        db: Session,
        chat_session_id: int,
        user_text: str,
        *,
        category_hint: Optional[str] = None,
        intent_confidence: Optional[float] = None,
    ):
        # 1) persist user message
        user_msg = self.msg_repo.create_user_message(db, chat_session_id, user_text)

        # 2) retrieve (broad)
        t0 = time.time()
        hits, best = self.pc.search(user_text, top_k=self.top_k)
        retrieval_ms = (time.time() - t0) * 1000.0

        # 3) normalize raw hits
        raw_sources = _normalize_sources(hits)

        # 3.1) re-rank + diversify
        reranked = self._rerank(
            query=user_text,
            hits=hits,
            raw_sources=raw_sources,
            category_hint=category_hint,
            intent_confidence=(intent_confidence or 0.0),
        )
        sources = self._diversify_by_hash(reranked, top_n=min(10, len(reranked)))

        # 4) if nothing usable → helpful abstain (with previews)
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

        # 5) pack & prompt
        context_text = _pack_context_for_prompt(sources, hits, max_chars=self.max_context_chars)
        user_prompt = (
            "Use the context below to answer the user.\n"
            "• Every factual sentence MUST include a citation like [1] or [2].\n"
            "• Do NOT invent numbers; only include fees/limits/timing if present in cited text.\n\n"
            f"---CONTEXT START---\n{context_text}---CONTEXT END---\n\n"
            f"User: {user_text}\n"
            "Answer:"
        )

        # 6) LLM
        try:
            result = self.llm.chat(self.SYSTEM_PROMPT, user_prompt)
        except Exception:
            content = (
                "I couldn’t reach the model just now. Please try again later, "
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

        text = result.get("text", "")
        tokens_in = result.get("tokens_in")
        tokens_out = result.get("tokens_out")
        latency_ms_total = retrieval_ms + (result.get("latency_ms") or 0.0)

        # 7) Verify & calibrate; flip to abstain if weakly supported
        verify = self._verify_answer(text, sources, user_text)
        as_answer_type = "grounded" if verify["confidence"] >= 0.55 else "abstained"
        final_text = text
        if as_answer_type == "abstained":
            followup_text, _ = self._abstain_message(user_text)
            final_text = followup_text

        # 8) Persist assistant message
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

    # ---------------------- internal helpers ----------------------

    def _rerank(
        self,
        query: str,
        hits: List[Dict[str, Any]],
        raw_sources: List[SourceRef],
        category_hint: Optional[str],
        intent_confidence: float,
    ) -> List[SourceRef]:
        """Blend vector score + lexical overlap + optional category boost."""
        # index sources by id for text/meta lookup
        id_to_text: Dict[str, str] = {}
        id_to_meta: Dict[str, Dict[str, Any]] = {}
        for h in hits:
            cid = str(h.get("id") or h.get("chunk_id") or "")
            fields = h.get("metadata") or h.get("fields") or {}
            id_to_text[cid] = fields.get("text") or h.get("content") or ""
            id_to_meta[cid] = fields

        def lexical_overlap(q: str, t: str) -> float:
            q_tokens = set(re.findall(r"[a-zA-Z0-9]+", q.lower()))
            t_tokens = set(re.findall(r"[a-zA-Z0-9]+", t.lower()))
            if not q_tokens or not t_tokens:
                return 0.0
            inter = len(q_tokens & t_tokens)
            return min(1.0, inter / max(4, len(q_tokens)))

        ranked: List[Tuple[float, SourceRef]] = []
        for s in raw_sources:
            txt = id_to_text.get(s.id, "")
            meta = id_to_meta.get(s.id, {}) or {}
            pine = (s.score or 0.0)
            lex = lexical_overlap(query, txt)
            cat_boost = 0.0
            if category_hint and isinstance(meta.get("category"), str):
                if meta.get("category", "").lower() == category_hint:
                    cat_boost = 0.12 if intent_confidence and intent_confidence >= 0.75 else 0.06
            score = (0.6 * pine) + (0.3 * lex) + cat_boost
            ranked.append((score, s))

        ranked.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in ranked]

    def _diversify_by_hash(self, ranked: List[SourceRef], top_n: int) -> List[SourceRef]:
        """Drop near-duplicates by content_hash/title to keep context diverse."""
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
        """Very light verifier using citations + lexical/number checks."""
        sentences = [p.strip() for p in re.split(r"(?<=[\.\!\?])\s+", text) if p.strip()]
        if not sentences:
            return {"supported": 0.0, "evidence_density": 0.0, "coverage": 0.0, "confidence": 0.0}

        # Map citation index → source ref
        by_rank = {s.rank: s for s in sources}

        # rough coverage: does the answer touch key tokens from the query?
        q_keys = {
            "fee",
            "fees",
            "limit",
            "limits",
            "timing",
            "time",
            "when",
            "cancel",
            "reverse",
            "declined",
            "failed",
            "2fa",
            "password",
            "privacy",
            "data",
            "encryption",
            "verify",
            "kyc",
            "id",
        }
        coverage = 1.0 if any(k in text.lower() and k in (query or "").lower() for k in q_keys) else 0.6

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
                    # use preview+title (we don't have the full text here)
                    src_text = (src.preview or "") + " " + (src.title or "")
                    nums = num_pat.findall(sent)
                    if nums and any(num in src_text for num in nums):
                        ok = True
                        break
                    s_tokens = set(w for w in re.findall(r"[a-zA-Z0-9]+", sent.lower()) if len(w) > 2)
                    t_tokens = set(w for w in re.findall(r"[a-zA-Z0-9]+", src_text.lower()) if len(w) > 2)
                    if s_tokens and len(s_tokens & t_tokens) / max(4, len(s_tokens)) >= 0.2:
                        ok = True
                        break
                if ok:
                    supported_hits += 1

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
        """Domain-aware abstain copy with targeted follow-up."""
        low = (user_text or "").lower()
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
