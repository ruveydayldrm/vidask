import pytest

from app.models.schemas import ChunkSource, ContextChunk
from app.services.citations import (
    CitationStreamFilter,
    CitationValidator,
    format_ts,
    parse_ts,
    validate_answer,
)

CTX = [
    ContextChunk(start=60, end=105, text="Decorators wrap functions.", source=ChunkSource.TRANSCRIPT),
    ContextChunk(start=300, end=340, text="def foo(): pass", source=ChunkSource.VISUAL),
    ContextChunk(start=3700, end=3740, text="Late in the video.", source=ChunkSource.TRANSCRIPT),
]


@pytest.mark.parametrize(
    ("label", "secs"), [("00:00", 0), ("1:05", 65), ("12:34", 754), ("1:02:03", 3723)]
)
def test_parse_ts(label: str, secs: float) -> None:
    assert parse_ts(label) == secs


@pytest.mark.parametrize(("secs", "label"), [(0, "00:00"), (65.7, "01:05"), (3723, "1:02:03")])
def test_format_ts(secs: float, label: str) -> None:
    assert format_ts(secs) == label


def test_keeps_valid_and_removes_fabricated() -> None:
    text, cites, removed = validate_answer(
        "A decorator wraps a function [01:00]. It was invented in 1990 [45:00].", CTX
    )
    assert "[01:00]" in text
    assert "[45:00]" not in text
    assert text.endswith("1990.")
    assert removed == ["45:00"]
    assert [c.label for c in cites] == ["01:00"]
    assert cites[0].preview.startswith("Decorators")


def test_inside_chunk_and_tolerance() -> None:
    _, cites, removed = validate_answer("x [01:30] y [01:49] z [01:52]", CTX, tolerance=5)
    assert [c.label for c in cites] == ["01:30", "01:49"]
    assert removed == ["01:52"]


def test_multi_timestamp_brackets_and_hours() -> None:
    text, cites, _ = validate_answer("See [01:00, 05:10] and [1:01:45].", CTX)
    assert "[01:00] [05:10]" in text
    assert {c.label for c in cites} == {"01:00", "05:10", "1:01:45"}
    assert next(c for c in cites if c.label == "05:10").source == ChunkSource.VISUAL


def test_non_timestamp_brackets_untouched() -> None:
    text, cites, _ = validate_answer("Use [this link](http://x) and list[0].", CTX)
    assert text == "Use [this link](http://x) and list[0]."
    assert cites == []


def test_dedupes_citations() -> None:
    _, cites, _ = validate_answer("a [01:00] b [01:00]", CTX)
    assert len(cites) == 1


def _stream(text: str, size: int) -> str:
    f = CitationStreamFilter(CitationValidator(CTX))
    out = "".join(f.feed(text[i : i + size]) for i in range(0, len(text), size))
    return out + f.flush()


@pytest.mark.parametrize("size", [1, 2, 3, 5, 8, 100])
def test_stream_filter_matches_batch(size: int) -> None:
    text = "Wraps [01:00]. Fake [59:59]. Code [05:00, 99:00]. Array [0] ok [link](u)."
    expected = CitationValidator(CTX).process(text)
    assert _stream(text, size) == expected
    assert "59:59" not in expected


def test_stream_filter_releases_long_brackets() -> None:
    text = "[" + "a" * 60 + "] tail"
    assert _stream(text, 4) == text


def test_stream_never_emits_invalid_prefix() -> None:
    f = CitationStreamFilter(CitationValidator(CTX))
    emitted = f.feed("Answer [59")
    assert "[" not in emitted
    emitted += f.feed(":59] done")
    assert "59:59" not in emitted
