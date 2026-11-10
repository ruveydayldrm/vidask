"""Single source of truth for configuration.

Every model choice (LLM, embedding, reranker, Whisper size) is read from the
environment / `.env` file. A small subset (provider, model, vision on/off) can be
overridden at runtime from the UI; those overrides are persisted to
``DATA_DIR/runtime_settings.json`` so the API process and the worker agree.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderName = Literal["ollama", "groq", "gemini", "fake"]

_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(_REPO_ROOT / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- general -----------------------------------------------------------
    env: Literal["dev", "prod", "test"] = "dev"
    log_level: str = "INFO"
    log_json: bool = False
    data_dir: Path = _REPO_ROOT / "data"
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # --- hardware ----------------------------------------------------------
    device: Literal["auto", "cpu", "cuda"] = "auto"
    min_gpu_vram_gb: float = 4.0
    # Hugging Face cache dir. Useful on Windows when the user profile path has
    # non-ASCII characters, which some download backends choke on.
    hf_home: str = ""

    # --- LLM ---------------------------------------------------------------
    llm_provider: ProviderName = "ollama"
    llm_model: str = "qwen2.5:3b"
    llm_context_window: int = 8192
    llm_temperature: float = 0.1
    llm_timeout_s: float = 300.0
    ollama_base_url: str = "http://localhost:11434"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # --- transcription -----------------------------------------------------
    whisper_model: str = "small"
    whisper_compute_type: str = "auto"  # auto -> int8 on CPU, float16 on CUDA
    transcript_languages: list[str] = ["tr", "en"]

    # --- retrieval ---------------------------------------------------------
    embedding_model: str = "BAAI/bge-m3"
    embedding_batch_size: int = 16
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_enabled: bool = True
    chunk_seconds: float = 45.0
    chunk_overlap_seconds: float = 10.0
    retrieval_candidates: int = 20
    retrieval_top_k: int = 6
    # Full transcript is sent (RAG skipped) when it fits in this share of the window.
    full_context_ratio: float = 0.55
    context_strategy: Literal["auto", "full", "rag"] = "auto"
    citation_tolerance_s: float = 5.0

    # --- vector DB / queue -------------------------------------------------
    qdrant_url: str = ""  # empty -> embedded local Qdrant under DATA_DIR/qdrant
    qdrant_collection: str = "vidask_chunks"
    redis_url: str = ""  # empty -> in-process thread queue
    queue_backend: Literal["auto", "rq", "thread"] = "auto"

    # --- vision ------------------------------------------------------------
    vision_enabled: bool = False
    vision_max_frames: int = 40
    vision_scene_threshold: float = 27.0
    vision_ocr_languages: list[str] = ["en", "tr"]
    vision_vlm_model: str = ""  # e.g. "qwen2.5vl:3b" on Ollama; empty disables captions

    # --- insights ----------------------------------------------------------
    insights_enabled: bool = True

    max_video_seconds: int = Field(default=3 * 60 * 60, description="Refuse longer videos")

    @property
    def runtime_settings_path(self) -> Path:
        return self.data_dir / "runtime_settings.json"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "vidask.sqlite3"


RUNTIME_KEYS = {"llm_provider", "llm_model", "vision_enabled", "reranker_enabled"}


@lru_cache
def _base_settings() -> Settings:
    s = Settings()
    if s.hf_home:
        os.environ.setdefault("HF_HOME", s.hf_home)
    return s


def get_settings() -> Settings:
    """Base settings merged with runtime overrides saved from the UI."""
    base = _base_settings()
    path = base.runtime_settings_path
    if not path.exists():
        return base
    try:
        overrides = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return base
    clean = {k: v for k, v in overrides.items() if k in RUNTIME_KEYS}
    return base.model_copy(update=clean) if clean else base


def save_runtime_overrides(updates: dict[str, object]) -> Settings:
    base = _base_settings()
    path = base.runtime_settings_path
    path.parent.mkdir(parents=True, exist_ok=True)
    current: dict[str, object] = {}
    if path.exists():
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            current = {}
    current.update({k: v for k, v in updates.items() if k in RUNTIME_KEYS and v is not None})
    path.write_text(json.dumps(current, indent=2), encoding="utf-8")
    return get_settings()


def reset_settings_cache() -> None:
    _base_settings.cache_clear()
