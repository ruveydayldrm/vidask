from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Query, Request
from sse_starlette.sse import EventSourceResponse

from app.core.config import get_settings
from app.core.errors import NotFoundError, VidAskError
from app.core.logging import get_logger
from app.models.schemas import (
    ChatRequest,
    ChunkSource,
    Job,
    ProcessRequest,
    ProcessResponse,
    VideoMeta,
    VideoRecord,
    VideoStatus,
)
from app.pipeline.metadata import fetch_metadata
from app.pipeline.url import extract_video_id
from app.services.container import get_llm, get_retriever, get_store
from app.services.jobs import get_queue
from app.services.llm_gate import gate as llm_gate
from app.services.qa import QAService

log = get_logger(__name__)
router = APIRouter(prefix="/api")

_preview_cache: dict[str, VideoMeta] = {}


@router.get("/videos/preview", response_model=VideoMeta)
async def preview(url: str) -> VideoMeta:
    video_id = extract_video_id(url)
    rec = get_store().get_video(video_id)
    if rec:
        return rec.meta
    if video_id not in _preview_cache:
        _preview_cache[video_id] = await asyncio.to_thread(fetch_metadata, video_id)
    return _preview_cache[video_id]


@router.post("/videos", response_model=ProcessResponse)
async def process(req: ProcessRequest) -> ProcessResponse:
    settings = get_settings()
    store = get_store()
    video_id = extract_video_id(req.url)
    vision = settings.vision_enabled if req.vision is None else req.vision

    rec = store.get_video(video_id)
    if (
        rec
        and rec.status == VideoStatus.READY
        and not req.force
        and (rec.vision_used or not vision)
    ):
        log.info("process.cache_hit", video_id=video_id)
        return ProcessResponse(video_id=video_id, job_id=None, cached=True, status=rec.status)

    active = store.active_job_for(video_id)
    if active:
        return ProcessResponse(
            video_id=video_id, job_id=active.id, cached=False, status=VideoStatus.PROCESSING
        )

    job = store.create_job(video_id, skip=set() if vision else {"vision"})
    if rec is None:
        cached = _preview_cache.get(video_id)
        rec = VideoRecord(meta=cached or VideoMeta(video_id=video_id, url=req.url))
    rec.status, rec.latest_job_id = VideoStatus.PROCESSING, job.id
    store.upsert_video(rec)
    get_queue().enqueue(job.id, video_id, vision, req.force)
    log.info("process.enqueued", video_id=video_id, job_id=job.id, vision=vision)
    return ProcessResponse(
        video_id=video_id, job_id=job.id, cached=False, status=VideoStatus.PROCESSING
    )


@router.get("/videos", response_model=list[VideoRecord])
async def list_videos(limit: int = Query(12, ge=1, le=100)) -> list[VideoRecord]:
    return get_store().list_videos(limit)


@router.get("/videos/{video_id}", response_model=VideoRecord)
async def get_video(video_id: str) -> VideoRecord:
    return get_store().require_video(video_id)


@router.get("/videos/{video_id}/transcript")
async def get_transcript(video_id: str) -> dict[str, Any]:
    store = get_store()
    t = store.get_transcript(video_id)
    if t is None:
        raise NotFoundError("Transcript not available yet.")
    visual = [c for c in store.get_chunks(video_id) if c.source == ChunkSource.VISUAL]
    return {
        "video_id": video_id,
        "language": t.language,
        "source": t.source,
        "segments": [s.model_dump() for s in t.segments],
        "visual": [v.model_dump(mode="json") for v in visual],
    }


@router.get("/jobs/{job_id}", response_model=Job)
async def get_job(job_id: str) -> Job:
    job = get_store().get_job(job_id)
    if job is None:
        raise NotFoundError("Job not found.")
    return job


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request) -> EventSourceResponse:
    store = get_store()
    if store.get_job(job_id) is None:
        raise NotFoundError("Job not found.")

    async def gen() -> AsyncIterator[dict[str, str]]:
        last = ""
        while True:
            if await request.is_disconnected():
                return
            job = store.get_job(job_id)
            if job is None:
                return
            payload = job.model_dump_json()
            if payload != last:
                last = payload
                yield {"event": "progress", "data": payload}
            if job.status in (VideoStatus.READY, VideoStatus.FAILED):
                yield {"event": "end", "data": job.status.value}
                return
            await asyncio.sleep(0.4)

    return EventSourceResponse(gen(), ping=15)


@router.post("/videos/{video_id}/chat")
async def chat(video_id: str, req: ChatRequest) -> EventSourceResponse:
    store = get_store()
    rec = store.require_video(video_id)
    if rec.status != VideoStatus.READY:
        raise VidAskError("Video is still processing.", code="not_ready")
    transcript = store.get_transcript(video_id)
    if transcript is None:
        raise NotFoundError("Transcript missing; please re-process the video.")
    chunks = store.get_chunks(video_id)
    settings = get_settings()
    llm = get_llm()
    try:
        retriever = get_retriever()
    except Exception as exc:  # embedding model unavailable -> full-context only
        log.warning("chat.retriever_unavailable", error=str(exc))
        retriever = None
    qa = QAService(settings, llm, retriever)

    async def gen() -> AsyncIterator[dict[str, str]]:
        try:
            # Background summary work pauses while a question is being answered.
            with llm_gate.interactive():
                async for ev in qa.stream_answer(transcript, chunks, rec.meta.title, req):
                    yield {
                        "event": ev["event"],
                        "data": json.dumps(ev["data"], ensure_ascii=False),
                    }
        except VidAskError as exc:
            yield {"event": "error", "data": json.dumps({"code": exc.code, "message": exc.message})}
        except Exception as exc:
            log.exception("chat.failed", video_id=video_id)
            yield {
                "event": "error",
                "data": json.dumps({"code": "internal_error", "message": str(exc)}),
            }

    return EventSourceResponse(gen(), ping=15)
