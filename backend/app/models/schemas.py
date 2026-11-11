"""Pydantic models shared across layers."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(UTC)


class TranscriptSource(StrEnum):
    MANUAL = "manual_captions"
    AUTO = "auto_captions"
    WHISPER = "whisper"


class ChunkSource(StrEnum):
    TRANSCRIPT = "transcript"
    VISUAL = "visual"


class VideoStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class Stage(StrEnum):
    METADATA = "metadata"
    TRANSCRIPT = "transcript"
    VISION = "vision"
    INDEXING = "indexing"
    INSIGHTS = "insights"


STAGE_ORDER: list[Stage] = [
    Stage.METADATA,
    Stage.TRANSCRIPT,
    Stage.VISION,
    Stage.INDEXING,
    Stage.INSIGHTS,
]


class VideoMeta(BaseModel):
    video_id: str
    url: str
    title: str = ""
    channel: str = ""
    duration: float = 0.0
    thumbnail: str = ""
    language: str | None = None


class Segment(BaseModel):
    start: float
    end: float
    text: str


class Transcript(BaseModel):
    video_id: str
    language: str | None
    source: TranscriptSource
    segments: list[Segment]

    @property
    def full_text(self) -> str:
        return " ".join(s.text for s in self.segments)


class Chunk(BaseModel):
    video_id: str
    idx: int
    start: float
    end: float
    text: str
    source: ChunkSource = ChunkSource.TRANSCRIPT


class Chapter(BaseModel):
    start: float
    title: str


class Insights(BaseModel):
    summary: str = ""
    chapters: list[Chapter] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)
    error: str | None = None


class StageState(BaseModel):
    stage: Stage
    status: Literal["pending", "running", "done", "skipped", "failed"] = "pending"
    progress: float = 0.0
    message: str = ""


class Job(BaseModel):
    id: str
    video_id: str
    status: VideoStatus = VideoStatus.PENDING
    progress: float = 0.0
    stage: Stage | None = None
    message: str = ""
    error: str | None = None
    error_code: str | None = None
    stages: list[StageState] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class VideoRecord(BaseModel):
    meta: VideoMeta
    status: VideoStatus = VideoStatus.PENDING
    transcript_source: TranscriptSource | None = None
    vision_used: bool = False
    insights: Insights | None = None
    # Ready for chat while summary/chapters are still being generated.
    insights_pending: bool = False
    error: str | None = None
    latest_job_id: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


# --- API payloads -----------------------------------------------------------


class ProcessRequest(BaseModel):
    url: str
    force: bool = False
    vision: bool | None = None


class ProcessResponse(BaseModel):
    video_id: str
    job_id: str | None
    cached: bool
    status: VideoStatus


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)
    lang: Literal["tr", "en"] | None = None


class Citation(BaseModel):
    label: str
    seconds: float
    chunk_start: float
    chunk_end: float
    source: ChunkSource
    preview: str


class ContextChunk(BaseModel):
    start: float
    end: float
    text: str
    source: ChunkSource
    score: float | None = None


class AnswerResult(BaseModel):
    answer: str
    citations: list[Citation]
    abstained: bool
    strategy: Literal["full", "rag"]
    context: list[ContextChunk]
    removed_citations: list[str] = Field(default_factory=list)
    latency_ms: int = 0
