# app/clients/llm_client.py
from __future__ import annotations
from typing import Dict, List, Optional, Generator, Iterable
import time

from openai import OpenAI  # pip install openai>=1.40
from app.config import settings


class LLMClient:
    """
    Thin OpenAI chat wrapper with optional streaming.
    """

    def __init__(self, model: Optional[str] = None, temperature: float = 0.2):
        self.model = model or settings.OPENAI_MODEL  # e.g., "gpt-4o-mini" or "gpt-4.1-mini"
        self.temperature = temperature
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        messages_history: Optional[List[Dict[str, str]]] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> Dict[str, any] | Generator[str, None, Dict[str, any]]:
        """
        Returns either a dict (non-stream) or a generator of token strings (stream).
        The final return (for stream) is the same dict with usage.
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
            txt = resp.choices[0].message.content or ""
            usage = getattr(resp, "usage", None)
            latency_ms = (time.time() - started) * 1000.0
            tokens_in = usage.prompt_tokens if usage else None
            tokens_out = usage.completion_tokens if usage else None
            return {
                "text": txt,
                "model": self.model,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "latency_ms": latency_ms,
            }

        # streaming
        def _gen() -> Generator[str, None, Dict[str, any]]:
            started = time.time()
            acc = []
            tokens_in = None
            tokens_out = 0
            with self.client.chat.completions.stream(
                model=self.model,
                temperature=self.temperature,
                max_tokens=max_tokens,
                messages=msgs,
            ) as stream_resp:
                for event in stream_resp:
                    if event.type == "response.refusal.delta":
                        continue
                    if event.type == "response.output_text.delta":
                        acc.append(event.delta)
                        tokens_out += 1
                        yield event.delta
                    elif event.type == "response.completed":
                        tokens_in = event.response.usage.input_tokens
                        tokens_out = event.response.usage.output_tokens
                        break

            latency_ms = (time.time() - started) * 1000.0
            return {
                "text": "".join(acc),
                "model": self.model,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "latency_ms": latency_ms,
            }

        return _gen()