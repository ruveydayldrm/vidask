"""Groq (OpenAI-compatible chat completions API; free tier available)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from app.core.errors import ProviderError
from app.providers.llm.base import LLMProvider, Message


class GroqProvider(LLMProvider):
    name = "groq"
    endpoint = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(
        self,
        model: str,
        context_window: int,
        api_key: str,
        temperature: float = 0.1,
        timeout: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(model, context_window, temperature)
        if not api_key:
            raise ProviderError("GROQ_API_KEY is not set.")
        self.api_key = api_key
        self.timeout = timeout
        self.transport = transport

    async def stream(
        self, messages: list[Message], *, json_mode: bool = False, max_tokens: int | None = None
    ) -> AsyncIterator[str]:
        payload: dict[str, object] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": self.temperature,
            "stream": True,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            async with (
                httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client,
                client.stream("POST", self.endpoint, json=payload, headers=headers) as resp,
            ):
                if resp.status_code != 200:
                    body = (await resp.aread()).decode(errors="ignore")
                    raise ProviderError(f"Groq {resp.status_code}: {body[:300]}")
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    choices = chunk.get("choices") or [{}]
                    delta = choices[0].get("delta", {}).get("content")
                    if delta:
                        yield delta
        except httpx.HTTPError as exc:
            raise ProviderError(f"Groq request failed: {exc}") from exc
