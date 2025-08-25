# app/clients/llm_client.py
"""
OpenAI API client wrapper with performance monitoring.
Handles chat completions, token tracking, and latency measurement for LLM responses.
Good for debugging and observability layer (next step).
"""
from __future__ import annotations
from typing import Dict, List, Optional, Any
import time
from openai import OpenAI
from app.config import settings

class LLMClient:
    def __init__(self, model: Optional[str] = None, temperature: float = 0.2):
        self.model = model or settings.OPENAI_MODEL  
        self.temperature = temperature
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not set")
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        messages_history: Optional[List[Dict[str, str]]] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Returns a dict with: {"text", "model", "tokens_in", "tokens_out", "latency_ms"}
        """
        msgs: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        if messages_history:
            msgs.extend(messages_history)
        msgs.append({"role": "user", "content": user_prompt})

        started = time.time()
        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            max_tokens=max_tokens,
            messages=msgs,
        )
        
        txt = (resp.choices[0].message.content or "").strip()
        usage = getattr(resp, "usage", None)
        latency_ms = (time.time() - started) * 1000.0
        tokens_in = getattr(usage, "prompt_tokens", None)
        tokens_out = getattr(usage, "completion_tokens", None)

        return {
            "text": txt,
            "model": self.model,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "latency_ms": latency_ms,
        }
