"""Question answering: pick a context strategy, stream the answer, validate citations."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal

from app.core.config import Settings
from app.core.logging import get_logger
from app.models.schemas import (
    AnswerResult,
    ChatRequest,
    Chunk,
    ChunkSource,
    ContextChunk,
    Transcript,
)
from app.pipeline.chunking import chunk_segments
from app.providers.llm import LLMProvider, Message, estimate_tokens
from app.services.citations import CitationStreamFilter, CitationValidator, tidy
from app.services.prompts import (
    ABSTAIN_MESSAGES,
    NO_ANSWER,
    detect_lang,
    format_context,
    qa_system_prompt,
    qa_user_prompt,
)
from app.services.retrieval import HybridRetriever

log = get_logger(__name__)

Strategy = Literal["full", "rag"]
FULL_BLOCK_SECONDS = 30.0
HISTORY_TURNS = 6


def full_context_blocks(transcript: Transcript, visual: list[Chunk]) -> list[ContextChunk]:
    """Non-overlapping ~30 s blocks covering the whole video (+ on-screen text)."""
    blocks = chunk_segments(
        transcript.segments, transcript.video_id, target=FULL_BLOCK_SECONDS, overlap=0
    )
    items = [ContextChunk(start=b.start, end=b.end, text=b.text, source=b.source) for b in blocks]
    items += [
        ContextChunk(start=v.start, end=v.end, text=v.text, source=ChunkSource.VISUAL) for v in visual
    ]
    return sorted(items, key=lambda c: c.start)


def choose_strategy(
    full_tokens: int, context_window: int, settings: Settings
) -> tuple[Strategy, str]:
    if settings.context_strategy != "auto":
        return settings.context_strategy, f"forced by CONTEXT_STRATEGY={settings.context_strategy}"
    budget = int(context_window * settings.full_context_ratio)
    if full_tokens <= budget:
        return "full", f"transcript ≈{full_tokens} tokens fits budget {budget}"
    return "rag", f"transcript ≈{full_tokens} tokens exceeds budget {budget}"


def retrieval_query(req: ChatRequest) -> str:
    """Follow-ups like "why?" need the previous question to retrieve anything useful."""
    prev = [t.content for t in req.history if t.role == "user"][-1:]
    return " ".join([*prev, req.question]) if prev else req.question


@dataclass
class QAService:
    settings: Settings
    llm: LLMProvider
    retriever: HybridRetriever | None

    def build_context(
        self, transcript: Transcript, chunks: list[Chunk], req: ChatRequest
    ) -> tuple[Strategy, str, list[ContextChunk]]:
        visual = [c for c in chunks if c.source == ChunkSource.VISUAL]
        blocks = full_context_blocks(transcript, visual)
        full_tokens = estimate_tokens(format_context(blocks))
        strategy, reason = choose_strategy(full_tokens, self.llm.context_window, self.settings)
        if strategy == "rag" and self.retriever is None:
            strategy, reason = "full", "retriever unavailable"
        if strategy == "full":
            return strategy, reason, blocks
        assert self.retriever is not None
        res = self.retriever.retrieve(
            transcript.video_id, retrieval_query(req), chunks, self.settings.retrieval_top_k
        )
        return strategy, reason, res.chunks

    def messages(
        self, req: ChatRequest, title: str, context: list[ContextChunk], lang: str
    ) -> list[Message]:
        msgs = [Message("system", qa_system_prompt(lang, title))]
        for turn in req.history[-HISTORY_TURNS:]:
            msgs.append(Message(turn.role, turn.content))
        msgs.append(Message("user", qa_user_prompt(format_context(context), req.question)))
        return msgs

    async def stream_answer(
        self,
        transcript: Transcript,
        chunks: list[Chunk],
        title: str,
        req: ChatRequest,
        prepared: tuple[Strategy, str, list[ContextChunk]] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yields SSE-ready events: meta → token* → done (or error)."""
        t0 = time.perf_counter()
        lang = detect_lang(req.question, fallback=req.lang or transcript.language or "en")
        strategy, reason, context = prepared or self.build_context(transcript, chunks, req)
        log.info(
            "qa.context",
            video_id=transcript.video_id,
            strategy=strategy,
            reason=reason,
            passages=len(context),
            model=self.llm.model,
        )
        yield {
            "event": "meta",
            "data": {
                "strategy": strategy,
                "reason": reason,
                "provider": self.llm.name,
                "model": self.llm.model,
                "context": [c.model_dump(mode="json") for c in context] if strategy == "rag" else [],
            },
        }

        validator = CitationValidator(context, self.settings.citation_tolerance_s)
        filt = CitationStreamFilter(validator)
        raw: list[str] = []
        head = ""  # held back until we know the answer does not start with NO_ANSWER
        decided = False
        early_abstain = False
        first_token_ms: int | None = None

        async for delta in self.llm.stream(self.messages(req, title, context, lang)):
            raw.append(delta)
            if first_token_ms is None:
                first_token_ms = int((time.perf_counter() - t0) * 1000)
            if not decided:
                head += delta
                probe = head.lstrip().lstrip("`*_\"' ")
                if len(probe) < len(NO_ANSWER) and NO_ANSWER.startswith(probe):
                    continue
                decided = True
                early_abstain = probe.startswith(NO_ANSWER)
                delta = head
            if early_abstain:
                continue
            text = filt.feed(delta)
            if text:
                yield {"event": "token", "data": {"text": text}}

        full_raw = "".join(raw)
        abstained = full_raw.strip().strip("`*_\"' .").startswith(NO_ANSWER) or (
            NO_ANSWER in full_raw and len(full_raw.strip()) < len(NO_ANSWER) + 40
        )
        if abstained:
            answer, citations, removed = ABSTAIN_MESSAGES.get(lang, ABSTAIN_MESSAGES["en"]), [], []
        else:
            tail = (filt.feed(head) if not decided else "") + filt.flush()
            if tail:
                yield {"event": "token", "data": {"text": tail}}
            final_validator = CitationValidator(context, self.settings.citation_tolerance_s)
            answer = tidy(final_validator.process(full_raw.replace(NO_ANSWER, "")))
            citations, removed = final_validator.citations, final_validator.removed

        latency = int((time.perf_counter() - t0) * 1000)
        if removed:
            log.warning("qa.citations_removed", removed=removed, video_id=transcript.video_id)
        result = AnswerResult(
            answer=answer,
            citations=citations,
            abstained=abstained,
            strategy=strategy,
            context=context if strategy == "rag" else [],
            removed_citations=removed,
            latency_ms=latency,
        )
        log.info(
            "qa.done",
            video_id=transcript.video_id,
            abstained=abstained,
            citations=len(citations),
            removed=len(removed),
            latency_ms=latency,
            first_token_ms=first_token_ms,
        )
        yield {"event": "done", "data": result.model_dump(mode="json")}

    async def answer(
        self, transcript: Transcript, chunks: list[Chunk], title: str, req: ChatRequest
    ) -> tuple[AnswerResult, list[ContextChunk]]:
        """Non-streaming helper (used by eval). Returns the result and the full context used."""
        prepared = self.build_context(transcript, chunks, req)
        context = prepared[2]
        result: AnswerResult | None = None
        async for ev in self.stream_answer(transcript, chunks, title, req, prepared):
            if ev["event"] == "done":
                result = AnswerResult.model_validate(ev["data"])
        assert result is not None
        return result, context
