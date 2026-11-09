"""Timestamp citations: parsing, validation and a streaming-safe filter.

The model is told to cite ``[mm:ss]``. We never trust it: each timestamp must fall
inside (± tolerance) a passage that was actually placed in the prompt. Invalid
citations are removed before the user sees them — also while streaming, by
holding back any text after an unclosed ``[`` until the bracket resolves.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.models.schemas import Citation, ContextChunk

_TS = r"(?:\d{1,2}:)?\d{1,2}:\d{2}"
# A bracket whose content is one or more timestamps separated by , ; – - or "ve/and".
BRACKET_RE = re.compile(rf"\[\s*({_TS}(?:\s*(?:,|;|-|–|—|ve|and)\s*{_TS})*)\s*\]")
SINGLE_TS_RE = re.compile(_TS)
MAX_PENDING = 40  # an unclosed "[" longer than this cannot be a timestamp


def parse_ts(label: str) -> float:
    parts = [int(p) for p in label.strip().split(":")]
    if len(parts) == 2:
        m, s = parts
        return float(m * 60 + s)
    h, m, s = parts
    return float(h * 3600 + m * 60 + s)


def format_ts(seconds: float) -> str:
    total = max(0, int(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def find_chunk(seconds: float, chunks: Sequence[ContextChunk], tol: float) -> ContextChunk | None:
    best: ContextChunk | None = None
    best_dist = float("inf")
    for ch in chunks:
        if ch.start - tol <= seconds <= ch.end + tol:
            # prefer the chunk whose start is closest (models usually cite the header time)
            dist = abs(seconds - ch.start)
            if dist < best_dist:
                best, best_dist = ch, dist
    return best


def _preview(text: str, limit: int = 220) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


@dataclass
class CitationValidator:
    chunks: Sequence[ContextChunk]
    tolerance: float = 5.0
    citations: list[Citation] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)

    def rewrite_bracket(self, match: re.Match[str]) -> str:
        labels = SINGLE_TS_RE.findall(match.group(1))
        kept: list[str] = []
        for label in labels:
            secs = parse_ts(label)
            chunk = find_chunk(secs, self.chunks, self.tolerance)
            if chunk is None:
                self.removed.append(label)
                continue
            norm = format_ts(secs)
            kept.append(f"[{norm}]")
            if not any(c.label == norm for c in self.citations):
                self.citations.append(
                    Citation(
                        label=norm,
                        seconds=secs,
                        chunk_start=chunk.start,
                        chunk_end=chunk.end,
                        source=chunk.source,
                        preview=_preview(chunk.text),
                    )
                )
        return " ".join(kept)

    def process(self, text: str) -> str:
        return BRACKET_RE.sub(self.rewrite_bracket, text)


def tidy(text: str) -> str:
    """Clean up whitespace left behind by removed citations."""
    text = re.sub(r"[ \t]+([.,;:!?])", r"\1", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


class CitationStreamFilter:
    """Feed model deltas in, get validated text out — never emits a bad citation."""

    def __init__(self, validator: CitationValidator) -> None:
        self.v = validator
        self.buf = ""

    def feed(self, delta: str) -> str:
        self.buf += delta
        out: list[str] = []
        while True:
            open_idx = self.buf.find("[")
            if open_idx == -1:
                out.append(self.buf)
                self.buf = ""
                break
            out.append(self.buf[:open_idx])
            self.buf = self.buf[open_idx:]
            close_idx = self.buf.find("]")
            if close_idx == -1:
                if len(self.buf) > MAX_PENDING:
                    out.append(self.buf[0])
                    self.buf = self.buf[1:]
                    continue
                break
            candidate = self.buf[: close_idx + 1]
            self.buf = self.buf[close_idx + 1 :]
            m = BRACKET_RE.fullmatch(candidate)
            out.append(self.v.rewrite_bracket(m) if m else candidate)
        return "".join(out)

    def flush(self) -> str:
        rest, self.buf = self.buf, ""
        return self.v.process(rest)


def validate_answer(
    text: str, chunks: Sequence[ContextChunk], tolerance: float = 5.0
) -> tuple[str, list[Citation], list[str]]:
    v = CitationValidator(chunks, tolerance)
    return tidy(v.process(text)), v.citations, v.removed
