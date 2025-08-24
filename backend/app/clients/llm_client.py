# app/clients/llm_client.py
from __future__ import annotations
from typing import Dict, List, Optional, Generator, Union, Any
import time

from openai import OpenAI
from app.config import settings


class LLMClient:
    """
    Thin OpenAI chat wrapper with optional streaming.
    """

    def __init__(self, model: Optional[str] = None, temperature: float = 0.2):
        self.model = model or settings.OPENAI_MODEL  # e.g. "gpt-4o-mini"
        self.temperature = temperature
        if not settings.OPENAI_API_KEY:
            # Fail loudly so you know why calls error
            raise RuntimeError("OPENAI_API_KEY is not set")
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        messages_history: Optional[List[Dict[str, str]]] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> Union[Dict[str, Any], Generator[str, None, Dict[str, Any]]]:
        """
        Returns:
          - dict when stream=False: {"text","model","tokens_in","tokens_out","latency_ms"}
          - generator when stream=True: yields text deltas; final generator return
            is the same dict (tokens_in/out often unavailable for streamed chat.completions).
        """
        msgs: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        if messages_history:
            msgs.extend(messages_history)
        msgs.append({"role": "user", "content": user_prompt})

        if not stream:
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

        # ---- streaming (chunk-based for chat.completions) ----
        def _gen() -> Generator[str, None, Dict[str, Any]]:
            started = time.time()
            acc: List[str] = []
            tokens_in = None
            tokens_out = None

            # stream=True returns an iterator of ChatCompletionChunk objects
            stream_resp = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=max_tokens,
                messages=msgs,
                stream=True,
            )

            for chunk in stream_resp:
                # Each chunk has choices[0].delta.content with partial text
                try:
                    delta = chunk.choices[0].delta.content or ""
                except Exception:
                    delta = ""
                if delta:
                    acc.append(delta)
                    yield delta

            latency_ms = (time.time() - started) * 1000.0
            # NOTE: chat.completions streaming does not return usage reliably
            return {
                "text": "".join(acc),
                "model": self.model,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "latency_ms": latency_ms,
            }

        return _gen()
