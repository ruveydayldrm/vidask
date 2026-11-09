"""Deterministic provider for tests and offline demos."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable

from app.providers.llm.base import LLMProvider, Message


class FakeProvider(LLMProvider):
    name = "fake"

    def __init__(
        self,
        responder: Callable[[list[Message]], str] | str = "OK",
        context_window: int = 8192,
        chunk_size: int = 7,
    ) -> None:
        super().__init__("fake-model", context_window, 0.0)
        self.responder = responder
        self.chunk_size = chunk_size
        self.calls: list[list[Message]] = []

    async def stream(
        self, messages: list[Message], *, json_mode: bool = False, max_tokens: int | None = None
    ) -> AsyncIterator[str]:
        self.calls.append(messages)
        text = self.responder(messages) if callable(self.responder) else self.responder
        for i in range(0, len(text), self.chunk_size):
            yield text[i : i + self.chunk_size]
