from app.models.schemas import Segment
from app.pipeline.chunking import chunk_segments, ends_sentence, normalize_segments


def segs(n: int, dur: float = 5.0, punct_every: int = 3) -> list[Segment]:
    return [
        Segment(
            start=i * dur,
            end=(i + 1) * dur,
            text=f"word{i} text" + ("." if (i + 1) % punct_every == 0 else ""),
        )
        for i in range(n)
    ]


def test_empty() -> None:
    assert chunk_segments([], "v") == []


def test_covers_whole_transcript_with_overlap() -> None:
    chunks = chunk_segments(segs(120), "vid", target=45, overlap=10)
    assert chunks[0].start == 0
    assert chunks[-1].end == 600
    for a, b in zip(chunks, chunks[1:], strict=False):
        assert b.start < a.end, "consecutive chunks must overlap"
        assert a.end - b.start <= 15
        assert b.start > a.start, "chunks must advance"


def test_chunk_length_bounds() -> None:
    chunks = chunk_segments(segs(200), "vid", target=45, overlap=10)
    for c in chunks[:-1]:
        assert 30 <= c.end - c.start <= 45 * 1.35 + 0.01


def test_prefers_sentence_boundaries() -> None:
    chunks = chunk_segments(segs(120, punct_every=3), "vid", target=45, overlap=10)
    ends = [c.text.endswith(".") for c in chunks[:-1]]
    assert sum(ends) / len(ends) > 0.8


def test_no_punctuation_still_chunks() -> None:
    chunks = chunk_segments(segs(100, punct_every=10_000), "vid", target=45, overlap=10)
    assert len(chunks) > 5
    assert all(c.end - c.start <= 45 * 1.35 + 0.01 for c in chunks)


def test_zero_overlap_partitions() -> None:
    chunks = chunk_segments(segs(60), "vid", target=30, overlap=0)
    for a, b in zip(chunks, chunks[1:], strict=False):
        assert b.start >= a.end
    assert " ".join(c.text for c in chunks).count("word") == 60


def test_metadata_fields() -> None:
    chunks = chunk_segments(segs(30), "myvideo", target=45, overlap=10)
    assert all(c.video_id == "myvideo" for c in chunks)
    assert [c.idx for c in chunks] == list(range(len(chunks)))


def test_normalize_drops_music_and_fixes_overlap() -> None:
    out = normalize_segments(
        [
            Segment(start=0, end=10, text="hello\nworld"),
            Segment(start=5, end=8, text="[Music]"),
            Segment(start=8, end=12, text="  next  "),
        ]
    )
    assert [s.text for s in out] == ["hello world", "next"]
    assert out[0].end == 8


def test_ends_sentence() -> None:
    assert ends_sentence("Bu bir cümle.")
    assert ends_sentence('He said "hi!"')
    assert not ends_sentence("and then")
