"""Provider-agnostic LLM interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class Message:
    role: Role
    content: str


class LLMProvider(ABC):
    """Every backend (Ollama, Groq, Gemini, fakes) implements this contract."""

    name: str = "base"

    def __init__(self, model: str, context_window: int, temperature: float = 0.1) -> None:
        self.model = model
        self.context_window = context_window
        self.temperature = temperature

    @abstractmethod
    def stream(
        self, messages: list[Message], *, json_mode: bool = False, max_tokens: int | None = None
    ) -> AsyncIterator[str]:
        """Yield text deltas as they arrive."""

    async def complete(
        self, messages: list[Message], *, json_mode: bool = False, max_tokens: int | None = None
    ) -> str:
        parts = [d async for d in self.stream(messages, json_mode=json_mode, max_tokens=max_tokens)]
        return "".join(parts)

    async def health(self) -> tuple[bool, str]:
        return True, "ok"

    def describe(self) -> dict[str, object]:
        return {"provider": self.name, "model": self.model, "context_window": self.context_window}


def estimate_tokens(text: str) -> int:
    """Cheap, tokenizer-free estimate. ~3.5 chars/token is conservative for TR+EN."""
    return int(len(text) / 3.5) + 1
