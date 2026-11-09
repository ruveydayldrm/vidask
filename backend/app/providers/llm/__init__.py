"""LLM providers and factory."""

from __future__ import annotations

from app.core.config import Settings
from app.core.errors import ProviderError
from app.providers.llm.base import LLMProvider, Message, estimate_tokens

__all__ = ["LLMProvider", "Message", "build_llm", "estimate_tokens"]

# Known context windows for hosted models; local models use LLM_CONTEXT_WINDOW.
_HOSTED_CONTEXT = {"groq": 32768, "gemini": 131072}


def build_llm(settings: Settings, *, provider: str | None = None, model: str | None = None) -> LLMProvider:
    name = provider or settings.llm_provider
    if name == "ollama":
        from app.providers.llm.ollama import OllamaProvider

        return OllamaProvider(
            model=model or settings.llm_model,
            context_window=settings.llm_context_window,
            temperature=settings.llm_temperature,
            base_url=settings.ollama_base_url,
            timeout=settings.llm_timeout_s,
        )
    if name == "groq":
        from app.providers.llm.groq import GroqProvider

        return GroqProvider(
            model=model or (settings.llm_model if settings.llm_provider == "groq" else settings.groq_model),
            context_window=_HOSTED_CONTEXT["groq"],
            api_key=settings.groq_api_key,
            temperature=settings.llm_temperature,
        )
    if name == "gemini":
        from app.providers.llm.gemini import GeminiProvider

        return GeminiProvider(
            model=model
            or (settings.llm_model if settings.llm_provider == "gemini" else settings.gemini_model),
            context_window=_HOSTED_CONTEXT["gemini"],
            api_key=settings.gemini_api_key,
            temperature=settings.llm_temperature,
        )
    if name == "fake":
        from app.providers.llm.fake import FakeProvider

        return FakeProvider()
    raise ProviderError(f"Unknown LLM provider: {name}")
