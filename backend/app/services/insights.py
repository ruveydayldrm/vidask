"""Auto-generated summary, chapters and suggested questions."""

from __future__ import annotations

import json
import re
from typing import Any

from app.core.logging import get_logger
from app.models.schemas import Chapter, Insights, Transcript
from app.pipeline.chunking import chunk_segments
from app.providers.llm import LLMProvider, Message, estimate_tokens
from app.services.citations import SINGLE_TS_RE, format_ts, parse_ts
from app.services.prompts import insights_prompt, notes_prompt

log = get_logger(__name__)


def timestamped_text(transcript: Transcript, block_seconds: float = 30.0) -> list[str]:
    blocks = chunk_segments(transcript.segments, transcript.video_id, target=block_seconds, overlap=0)
    return [f"[{format_ts(b.start)}] {b.text}" for b in blocks]


def extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in model output")
    data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("model output is not a JSON object")
    return data


def clean_chapters(raw: Any, duration: float, intro_title: str) -> list[Chapter]:
    chapters: list[Chapter] = []
    if not isinstance(raw, list):
        return chapters
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        start_raw = str(item.get("start", "")).strip()
        m = SINGLE_TS_RE.search(start_raw)
        if not title or not m:
            continue
        secs = parse_ts(m.group(0))
        if duration and secs > duration:
            continue
        chapters.append(Chapter(start=secs, title=title[:80]))
    chapters.sort(key=lambda c: c.start)
    deduped: list[Chapter] = []
    for ch in chapters:
        if deduped and ch.start - deduped[-1].start < 10:
            continue
        deduped.append(ch)
    if deduped and deduped[0].start > 15:
        deduped.insert(0, Chapter(start=0, title=intro_title))
    elif deduped:
        deduped[0] = deduped[0].model_copy(update={"start": 0.0})
    return deduped[:12]


async def _condense(llm: LLMProvider, lang: str, lines: list[str], budget: int) -> list[str]:
    """Map step for long videos: turn transcript windows into timestamped notes."""
    windows: list[list[str]] = [[]]
    used = 0
    for line in lines:
        t = estimate_tokens(line)
        if used + t > budget and windows[-1]:
            windows.append([])
            used = 0
        windows[-1].append(line)
        used += t
    notes: list[str] = []
    for i, w in enumerate(windows):
        out = await llm.complete([Message("user", notes_prompt(lang, "\n".join(w)))], max_tokens=600)
        notes.extend(ln.strip() for ln in out.splitlines() if ln.strip())
        log.info("insights.condensed_window", window=i + 1, of=len(windows))
    return notes


async def generate_insights(transcript: Transcript, title: str, duration: float, llm: LLMProvider) -> Insights:
    lang = transcript.language if transcript.language in ("tr", "en") else "en"
    lines = timestamped_text(transcript)
    budget = int(llm.context_window * 0.6) - 600
    rounds = 0
    while estimate_tokens("\n".join(lines)) > budget and rounds < 3:
        lines = await _condense(llm, lang, lines, budget)
        rounds += 1

    prompt = insights_prompt(lang, title, "\n".join(lines), format_ts(duration))
    last_err: Exception | None = None
    for attempt in range(2):
        out = await llm.complete([Message("user", prompt)], json_mode=True, max_tokens=900)
        try:
            data = extract_json(out)
            questions = [str(q).strip() for q in data.get("questions", []) if str(q).strip()]
            insights = Insights(
                summary=str(data.get("summary", "")).strip(),
                chapters=clean_chapters(
                    data.get("chapters"), duration, "Giriş" if lang == "tr" else "Intro"
                ),
                suggested_questions=questions[:5],
            )
            log.info(
                "insights.done",
                video_id=transcript.video_id,
                chapters=len(insights.chapters),
                questions=len(insights.suggested_questions),
                condense_rounds=rounds,
            )
            return insights
        except (ValueError, json.JSONDecodeError) as exc:
            last_err = exc
            log.warning("insights.parse_failed", attempt=attempt + 1, error=str(exc))
    return Insights(error=f"Could not parse insights: {last_err}")
