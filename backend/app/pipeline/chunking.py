"""Time-based chunking that respects sentence boundaries.

Captions arrive as short, timed segments (2-6 s). We greedily pack segments into
~``target`` second windows. Once the window is past ``min_ratio * target`` we
close it at the first segment that ends a sentence; ``max_ratio * target`` is a
hard cap so auto-captions without punctuation still chunk sensibly. Consecutive
chunks overlap by roughly ``overlap`` seconds (whole segments are re-used).
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.models.schemas import Chunk, ChunkSource, Segment

_SENTENCE_END = re.compile(r"[.!?…。]['\")\]]*\s*$")


def ends_sentence(text: str) -> bool:
    return bool(_SENTENCE_END.search(text.strip()))


def normalize_segments(segments: Sequence[Segment]) -> list[Segment]:
    """Clean whitespace, drop empty/music-only lines, fix overlapping end times."""
    cleaned: list[Segment] = []
    for seg in sorted(segments, key=lambda s: s.start):
        text = re.sub(r"\s+", " ", seg.text.replace("\n", " ")).strip()
        if not text or re.fullmatch(r"[\[(]?(music|müzik|applause|alkış)[\])]?", text, re.I):
            continue
        cleaned.append(Segment(start=seg.start, end=max(seg.end, seg.start), text=text))
    for i in range(len(cleaned) - 1):
        nxt = cleaned[i + 1].start
        if cleaned[i].end > nxt:
            cleaned[i] = cleaned[i].model_copy(update={"end": max(cleaned[i].start, nxt)})
    return cleaned


def chunk_segments(
    segments: Sequence[Segment],
    video_id: str,
    *,
    target: float = 45.0,
    overlap: float = 10.0,
    min_ratio: float = 0.75,
    max_ratio: float = 1.35,
) -> list[Chunk]:
    segs = normalize_segments(segments)
    if not segs:
        return []
    if overlap >= target:
        raise ValueError("overlap must be smaller than target")

    chunks: list[Chunk] = []
    i = 0
    n = len(segs)
    while i < n:
        start = segs[i].start
        j = i
        while j < n:
            span = segs[j].end - start
            if span >= target * max_ratio and j > i:
                j -= 1
                break
            if span >= target * min_ratio and ends_sentence(segs[j].text):
                break
            if span >= target and j + 1 < n and segs[j + 1].end - start > target * max_ratio:
                break
            j += 1
        j = min(j, n - 1)
        window = segs[i : j + 1]
        chunks.append(
            Chunk(
                video_id=video_id,
                idx=len(chunks),
                start=round(window[0].start, 2),
                end=round(window[-1].end, 2),
                text=" ".join(s.text for s in window),
                source=ChunkSource.TRANSCRIPT,
            )
        )
        if j >= n - 1:
            break
        # Step back so the next chunk starts ~overlap seconds before this one ended.
        next_i = j + 1
        boundary = segs[j].end - overlap
        while next_i - 1 > i and segs[next_i - 1].start >= boundary:
            next_i -= 1
        i = max(next_i, i + 1)
    return chunks
