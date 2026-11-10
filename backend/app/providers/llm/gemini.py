"""Google Gemini via the public REST API (free tier available)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from app.core.errors import ProviderError
from app.providers.llm.base import LLMProvider, Message


class GeminiProvider(LLMProvider):
    name = "gemini"
    base = "https://generativelanguage.googleapis.com/v1beta/models"

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
            raise ProviderError("GEMINI_API_KEY is not set.")
        self.api_key = api_key
        self.timeout = timeout
        self.transport = transport

    @staticmethod
    def to_payload(messages: list[Message]) -> dict[str, object]:
        system = "\n\n".join(m.content for m in messages if m.role == "system")
        contents = [
            {"role": "model" if m.role == "assistant" else "user", "parts": [{"text": m.content}]}
            for m in messages
            if m.role != "system"
        ]
        payload: dict[str, object] = {"contents": contents}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        return payload

    async def stream(
        self, messages: list[Message], *, json_mode: bool = False, max_tokens: int | None = None
    ) -> AsyncIterator[str]:
        payload = self.to_payload(messages)
        gen: dict[str, object] = {"temperature": self.temperature}
        if max_tokens:
            gen["maxOutputTokens"] = max_tokens
        if json_mode:
            gen["responseMimeType"] = "application/json"
        payload["generationConfig"] = gen
        url = f"{self.base}/{self.model}:streamGenerateContent"
        try:
            async with (
                httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client,
                client.stream(
                    "POST",
                    url,
                    params={"alt": "sse"},
                    headers={"x-goog-api-key": self.api_key},
                    json=payload,
                ) as resp,
            ):
                if resp.status_code != 200:
                    body = (await resp.aread()).decode(errors="ignore")
                    raise ProviderError(f"Gemini {resp.status_code}: {body[:300]}")
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    chunk = json.loads(line[5:].strip())
                    for cand in chunk.get("candidates", []):
                        for part in cand.get("content", {}).get("parts", []):
                            if part.get("text"):
                                yield part["text"]
        except httpx.HTTPError as exc:
            raise ProviderError(f"Gemini request failed: {exc}") from exc
