from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from app.core.errors import ProviderError
from app.providers.llm.base import LLMProvider, Message


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(
        self,
        model: str,
        context_window: int,
        temperature: float = 0.1,
        base_url: str = "http://localhost:11434",
        timeout: float = 300.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(model, context_window, temperature)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport

    async def stream(
        self, messages: list[Message], *, json_mode: bool = False, max_tokens: int | None = None
    ) -> AsyncIterator[str]:
        payload: dict[str, object] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "options": {
                "temperature": self.temperature,
                "num_ctx": self.context_window,
                **({"num_predict": max_tokens} if max_tokens else {}),
            },
        }
        if json_mode:
            payload["format"] = "json"
        try:
            async with (
                httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client,
                client.stream("POST", f"{self.base_url}/api/chat", json=payload) as resp,
            ):
                if resp.status_code != 200:
                    body = (await resp.aread()).decode(errors="ignore")
                    raise ProviderError(f"Ollama {resp.status_code}: {body[:300]}")
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    if "error" in data:
                        raise ProviderError(f"Ollama: {data['error']}")
                    delta = data.get("message", {}).get("content", "")
                    if delta:
                        yield delta
                    if data.get("done"):
                        break
        except httpx.ConnectError as exc:
            raise ProviderError(
                f"Cannot reach Ollama at {self.base_url}. Is it running? (`ollama serve`)"
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"Ollama request failed: {exc}") from exc

    async def list_models(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                resp.raise_for_status()
                return sorted(m["name"] for m in resp.json().get("models", []))
        except httpx.HTTPError:
            return []

    async def health(self) -> tuple[bool, str]:
        models = await self.list_models()
        if not models:
            return False, f"Ollama unreachable or has no models at {self.base_url}"
        if not any(m == self.model or m.split(":")[0] == self.model for m in models):
            return False, f"Model '{self.model}' not pulled. Run: ollama pull {self.model}"
        return True, "ok"
