import pytest

from app.models.schemas import ChunkSource, ContextChunk
from app.services.prompts import LEAKED_MARKUP, detect_lang, format_context


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        ("Does the video explain functools.wraps?", "en"),  # regression: two plain i's
        ("What is a decorator in Python?", "en"),
        ("Is it fine?", "en"),
        ("Bir fonksiyona birden fazla decorator uygulanabilir mi?", "tr"),
        ("Yapay zeka nedir?", "tr"),
        ("SHA-256 çıktısı kaç karakter?", "tr"),
        ("İstanbul", "tr"),
    ],
)
def test_detect_lang(text: str, lang: str) -> None:
    assert detect_lang(text) == lang


def test_detect_lang_falls_back_when_ambiguous() -> None:
    assert detect_lang("API?", fallback="tr") == "tr"


def test_format_context_marks_visual_without_copyable_tags() -> None:
    ctx = format_context(
        [
            ContextChunk(start=65, end=90, text="x = 1", source=ChunkSource.VISUAL),
            ContextChunk(start=0, end=30, text="Hello", source=ChunkSource.TRANSCRIPT),
        ]
    )
    assert ctx.splitlines()[0] == "[00:00] Hello"
    assert "[01:05] 🖼 On screen: x = 1" in ctx
    assert "(spoken)" not in ctx


def test_leaked_markup_is_stripped() -> None:
    assert LEAKED_MARKUP.sub("", "[00:30] (spoken) It wraps it.") == "[00:30] It wraps it."
