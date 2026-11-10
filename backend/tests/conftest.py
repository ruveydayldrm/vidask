from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from app.core import config
from app.models.schemas import Segment, Transcript, TranscriptSource
from app.services import container


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Every test gets its own data dir and lightweight fake models."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("EMBEDDING_MODEL", "hash")
    monkeypatch.setenv("RERANKER_MODEL", "overlap")
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("REDIS_URL", "")
    monkeypatch.setenv("QDRANT_URL", "")
    monkeypatch.setenv("QUEUE_BACKEND", "thread")
    monkeypatch.setenv("INSIGHTS_ENABLED", "false")
    config.reset_settings_cache()
    container.clear_overrides()
    yield
    container.clear_overrides()
    config.reset_settings_cache()


def make_transcript(video_id: str = "abcdefghijk", lang: str = "en") -> Transcript:
    lines = [
        "Welcome to this tutorial about Python decorators.",
        "A decorator is a function that wraps another function.",
        "You apply it with the at sign above the definition.",
        "Next we look at functools wraps to keep metadata.",
        "Without wraps the function name is lost.",
        "Now let's talk about class decorators.",
        "Class decorators receive the class object.",
        "They are useful for registering plugins.",
        "Finally, decorators can take arguments.",
        "That requires an extra level of nesting.",
        "Thanks for watching and see you next time.",
    ]
    segs = [Segment(start=i * 12.0, end=i * 12.0 + 11.5, text=t) for i, t in enumerate(lines)]
    return Transcript(
        video_id=video_id, language=lang, source=TranscriptSource.MANUAL, segments=segs
    )


@pytest.fixture
def transcript() -> Transcript:
    return make_transcript()
