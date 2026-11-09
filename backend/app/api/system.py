from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings, save_runtime_overrides
from app.core.device import detect_device
from app.providers.llm import build_llm
from app.providers.llm.ollama import OllamaProvider
from app.services.jobs import get_queue

router = APIRouter(prefix="/api")


class SettingsUpdate(BaseModel):
    llm_provider: Literal["ollama", "groq", "gemini"] | None = None
    llm_model: str | None = None
    vision_enabled: bool | None = None
    reranker_enabled: bool | None = None


def _public_settings() -> dict[str, Any]:
    s = get_settings()
    return {
        "llm_provider": s.llm_provider,
        "llm_model": s.llm_model,
        "vision_enabled": s.vision_enabled,
        "reranker_enabled": s.reranker_enabled,
        "embedding_model": s.embedding_model,
        "reranker_model": s.reranker_model,
        "whisper_model": s.whisper_model,
        "context_window": s.llm_context_window,
    }


@router.get("/settings")
async def read_settings() -> dict[str, Any]:
    s = get_settings()
    ollama = OllamaProvider(s.llm_model, s.llm_context_window, base_url=s.ollama_base_url)
    return {
        "current": _public_settings(),
        "providers": {
            "ollama": {"available": True, "models": await ollama.list_models()},
            "groq": {"available": bool(s.groq_api_key), "models": [s.groq_model]},
            "gemini": {"available": bool(s.gemini_api_key), "models": [s.gemini_model]},
        },
    }


@router.put("/settings")
async def update_settings(update: SettingsUpdate) -> dict[str, Any]:
    data = update.model_dump(exclude_none=True)
    if "llm_provider" in data and "llm_model" not in data:
        s = get_settings()
        data["llm_model"] = {
            "groq": s.groq_model,
            "gemini": s.gemini_model,
            "ollama": s.llm_model,
        }[data["llm_provider"]]
    save_runtime_overrides(data)
    return await read_settings()


@router.get("/health")
async def health() -> dict[str, Any]:
    s = get_settings()
    dev = detect_device(s.device, s.min_gpu_vram_gb)
    try:
        llm = build_llm(s)
        ok, msg = await llm.health()
    except Exception as exc:
        ok, msg = False, str(exc)
    return {
        "status": "ok",
        "device": {"device": dev.device, "reason": dev.reason, "gpu": dev.gpu_name},
        "llm": {"provider": s.llm_provider, "model": s.llm_model, "ok": ok, "message": msg},
        "queue": get_queue().backend,
        "qdrant": s.qdrant_url or "embedded",
    }
