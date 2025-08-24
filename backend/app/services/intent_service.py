# app/services/intent_service.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Optional
import re
import time

# Optional DI: let caller pass an LLM client; we only import the type for hints
try:
    from app.clients.llm_client import LLMClient  # noqa: F401
except Exception:
    LLMClient = None  # type: ignore


@dataclass
class IntentResult:
    intent: str                      # fintech_question | greeting | smalltalk | off_topic | nonsense | meta_help
    processed_query: str             # cleaned / rewritten text (used by RAG)
    confidence: float                # 0..1
    signals: Dict[str, object]       # debug: matched_keywords, is_question, lang, length, category_hint, etc.


class IntentService:
    """
    Hybrid intent + query processing for the fintech FAQ domain.
    - Fast heuristics first (cheap, covers ~80%).
    - Optional LLM fallback when confidence is low.
    - Small synonym rewriting and a light history nudge.
    """

    GREET = {"hi", "hello", "hey", "good morning", "good afternoon", "good evening"}
    SMALLTALK = {"thanks", "thank you", "lol", "haha", "cool", "nice", "ok", "okay", "got it"}
    OFFTOPIC_HINTS = {
        "weather", "joke", "cat", "dog", "movie", "song", "sports",
        "news", "recipe", "cooking", "music", "stock price", "btc price", "bitcoin"
    }

    # Tiny fintech keyword lexicon (category → words/phrases)
    LEXICON = {
        "account": {
            "account", "signup", "register", "verify", "identity", "kyc", "profile", "open",
            "password", "passcode", "credentials"
        },
        "payments": {
            "transfer", "send", "receive", "deposit", "withdraw", "card", "fee", "limit", "payment", "transaction",
            "cancel", "reversal", "refund", "chargeback", "dispute", "failed", "declined"
        },
        "security": {
            "fraud", "phish", "compromise", "password", "2fa", "otp", "lock", "suspend", "secure",
            "data", "privacy", "encryption", "encrypted", "protect", "protection"
        },
        "regulatory": {"kyc", "aml", "compliance", "insure", "insurance", "fdic", "limit", "hold", "regulation"},
        "support": {"bug", "crash", "not working", "support", "contact", "help", "email", "issue", "problem"},
    }

    # Colloquial → canonical
    SYNONYMS = {
        r"\badd money\b": "deposit",
        r"\btop up\b": "deposit",
        r"\bput money\b": "deposit",
        r"\bsend money\b": "transfer",
        r"\bpay someone\b": "transfer",
        r"\breceive money\b": "incoming transfer",
        r"\btake out\b": "withdraw",
        r"\bverify me\b": "identity verification",
        r"\bblocked card\b": "card locked",
        r"\bfrozen account\b": "account suspended",
        r"\bcan['’]?t login\b": "login issues",
        r"\bcharges?\b": "fee",
        r"\bcosts?\b": "fee",
        r"\bprivacy\b": "security",
        r"\bdata protection\b": "security",
        r"\bfreeze (my )?account\b": "lock account",
        r"\bcancel(ed|ling)? (a )?payment\b": "payment reversal",
        r"\bchange password\b": "password change",
        r"\breset password\b": "password reset",
    }

    def __init__(
        self,
        min_len: int = 3,
        llm_fallback_threshold: float = 0.6,
        enable_llm_fallback: bool = True,
        llm_client: Optional["LLMClient"] = None,
    ):
        self.min_len = min_len
        self.llm_fallback_threshold = llm_fallback_threshold
        self.enable_llm_fallback = enable_llm_fallback
        self._llm = llm_client  # lazy-inited if None

    # ---------- Public API ----------

    def classify(self, text: str, history: Optional[List[Dict[str, str]]] = None) -> IntentResult:
        """
        Returns an IntentResult with processed query and routing decision.
        history: optional recent messages: [{"role": "...", "content": "..."}]
        """
        heuristic_result = self._classify_heuristic(text, history)

        # Short/obvious paths: never invoke LLM for these.
        if heuristic_result.intent in {"greeting", "smalltalk", "off_topic", "nonsense"}:
            return heuristic_result

        # Otherwise fintech or borderline; only fallback if confidence is low.
        if (
            self.enable_llm_fallback
            and heuristic_result.confidence < self.llm_fallback_threshold
            and len(heuristic_result.processed_query) >= self.min_len
        ):
            return self._classify_with_llm(text, history, heuristic_result)

        return heuristic_result

    # ---------- Heuristic path ----------

    def _classify_heuristic(self, text: str, history: Optional[List[Dict[str, str]]] = None) -> IntentResult:
        raw = (text or "").strip()
        normalized = self._normalize(raw)
        low = normalized.lower()

        signals = {
            "classification_method": "heuristic",
            "is_question": self._looks_like_question(low),
            "length": len(low),
            "lang": "en",
        }

        if not low or len(low) < self.min_len:
            return IntentResult("nonsense", "", 0.1, {**signals, "reason": "too_short"})

        if self._contains_any(low, self.GREET):
            return IntentResult("greeting", normalized, 0.95, {**signals, "match": "greeting"})

        if self._contains_any(low, self.SMALLTALK):
            return IntentResult("smalltalk", normalized, 0.9, {**signals, "match": "smalltalk"})

        if any(hint in low for hint in self.OFFTOPIC_HINTS):
            return IntentResult("off_topic", normalized, 0.85, {**signals, "match": "off_topic_hint"})

        # fintech keyword scoring (plural/inflection aware)
        cat_hits: Dict[str, List[str]] = {cat: [] for cat in self.LEXICON}
        for cat, words in self.LEXICON.items():
            for w in words:
                if self._word_hit(w, low):
                    cat_hits[cat].append(w)

        cat_scores = {cat: len(hits) for cat, hits in cat_hits.items()}
        best_cat, best_score = max(cat_scores.items(), key=lambda kv: kv[1])
        signals["category_scores"] = cat_scores
        signals["matched_keywords"] = cat_hits
        category_hint = best_cat if best_score > 0 else None
        signals["category_hint"] = category_hint

        # quick rewrite + history nudge
        rewritten = self._rewrite_synonyms(normalized)
        rewritten = self._bias_with_history(rewritten, history, category_hint)
        rewritten = self._normalize(rewritten)

        # confidence policy (favor RAG when question has any fintech hit)
        if best_score >= 2:
            return IntentResult("fintech_question", rewritten, 0.9, signals)
        if best_score >= 1 and signals["is_question"]:
            return IntentResult("fintech_question", rewritten, 0.7, signals)
        if best_score >= 1:
            return IntentResult("fintech_question", rewritten, 0.6, signals)
        if signals["is_question"]:
            return IntentResult("off_topic", normalized, 0.4, {**signals, "reason": "question_but_no_fintech_terms"})
        return IntentResult("nonsense", normalized, 0.3, {**signals, "reason": "no_keywords_no_question"})

    # ---------- LLM fallback (optional) ----------

    def _classify_with_llm(
        self,
        text: str,
        history: Optional[List[Dict[str, str]]],
        heuristic_result: IntentResult,
    ) -> IntentResult:
        # Lazy init to avoid hard dependency for tests
        if self._llm is None:
            from app.clients.llm_client import LLMClient  # local import to avoid cyclic issues
            self._llm = LLMClient(model="gpt-4o-mini", temperature=0.1)

        system_prompt = (
            "You are an intent classifier for a fintech FAQ chatbot.\n"
            "Return exactly one of: fintech_question | greeting | smalltalk | off_topic | nonsense\n"
        )

        context = ""
        if history:
            recent = " ".join([m.get("content", "")[:60] for m in history[-2:]])
            context = f"Recent conversation context: {recent}\n\n"

        user_prompt = f"""{context}User input: {text}
Category:"""

        try:
            t0 = time.time()
            result = self._llm.chat(system_prompt, user_prompt, stream=False)
            llm_latency = (time.time() - t0) * 1000.0

            llm_intent = (result.get("text") or "").strip().lower()
            intent = {
                "fintech_question": "fintech_question",
                "greeting": "greeting",
                "smalltalk": "smalltalk",
                "off_topic": "off_topic",
                "nonsense": "nonsense",
            }.get(llm_intent, "off_topic")

            processed_query = self._normalize(text)
            if intent == "fintech_question":
                processed_query = self._rewrite_synonyms(processed_query)
                processed_query = self._bias_with_history(processed_query, history, None)
                processed_query = self._normalize(processed_query)

            return IntentResult(
                intent=intent,
                processed_query=processed_query,
                confidence=0.88,
                signals={
                    **heuristic_result.signals,
                    "classification_method": "llm_fallback",
                    "heuristic_confidence": heuristic_result.confidence,
                    "heuristic_intent": heuristic_result.intent,
                    "llm_raw_response": llm_intent,
                    "llm_latency_ms": llm_latency,
                    "llm_tokens_in": result.get("tokens_in"),
                    "llm_tokens_out": result.get("tokens_out"),
                },
            )

        except Exception as e:
            # LLM failed → fall back to heuristic result
            heuristic_result.signals.update({
                "llm_error": str(e),
                "classification_method": "heuristic_fallback",
            })
            return heuristic_result

    # ---------- helpers ----------

    @staticmethod
    def _normalize(s: str) -> str:
        s = s.strip()
        s = re.sub(r"\s+", " ", s)
        return s

    @staticmethod
    def _looks_like_question(s: str) -> bool:
        if "?" in s:
            return True
        return bool(re.match(r"^(how|what|when|where|who|why|can|do|does|is|are|should|will|would|could)\b", s.lower()))

    @staticmethod
    def _contains_any(text: str, bag: set) -> bool:
        """
        Keyword match with light pluralization/inflection:
        - fee/fees, limit/limits, transaction/transactions, charge/charges, etc.
        """
        for w in bag:
            # allow simple plural/suffix variants (s, es, ed, ing)
            pat = rf"\b{re.escape(w)}(?:s|es|ed|ing)?\b"
            if re.search(pat, text):
                return True
        return False

    @staticmethod
    def _word_hit(word: str, text_low: str) -> bool:
        """
        Match single words with simple inflections; keep phrases as-is.
        """
        if " " in word.strip():
            # phrase — match as a whole (case-insensitive)
            return re.search(rf"\b{re.escape(word)}\b", text_low) is not None
        # single token — allow simple suffixes
        pat = rf"\b{re.escape(word)}(?:s|es|ed|ing)?\b"
        return re.search(pat, text_low) is not None

    @staticmethod
    def _category_score(text: str, bag: set) -> int:
        return sum(1 for w in bag if w in text)

    def _rewrite_synonyms(self, s: str) -> str:
        out = s
        for pat, repl in self.SYNONYMS.items():
            out = re.sub(pat, repl, out, flags=re.IGNORECASE)
        return out

    def _bias_with_history(self, s: str, history: Optional[List[Dict[str, str]]], cat_hint: Optional[str]) -> str:
        """
        If last turns mention 'transfer', nudge 'limits' -> 'transfer limits', etc.
        """
        if not history:
            return s
        # history passed in most-recent-first; look at a small window
        last_texts = " ".join([m.get("content", "").lower() for m in history[:4]])

        if "transfer" in last_texts and re.search(r"\blimits?\b", s.lower()) and "transfer" not in s.lower():
            return f"transfer {s}"
        if "verify" in last_texts and "verify" not in s.lower() and re.search(r"\b(account|me|identity)\b", s.lower()):
            return f"identity verification {s}"
        if "card" in last_texts and re.search(r"\b(blocked|frozen|locked)\b", s.lower()) and "card" not in s.lower():
            return f"card {s}"
        if "deposit" in last_texts and re.search(r"\b(how long|when|time)\b", s.lower()) and "deposit" not in s.lower():
            return f"deposit {s}"

        return s
