"""Orchestrates one processing job: metadata → transcript → vision → indexing → insights.

Runs in a worker (RQ) or a background thread. All progress is written to the
store, which the SSE endpoint tails.
"""

from __future__ import annotations

import asyncio
import time

from app.core.config import get_settings
from app.core.errors import VidAskError
from app.core.logging import get_logger
from app.models.schemas import (
    Chunk,
    Job,
    Stage,
    StageState,
    VideoRecord,
    VideoStatus,
)
from app.pipeline.chunking import chunk_segments
from app.pipeline.metadata import fetch_metadata
from app.pipeline.transcript import get_transcript
from app.services.container import get_store

log = get_logger(__name__)

STAGE_WEIGHTS = {
    Stage.METADATA: 5,
    Stage.TRANSCRIPT: 30,
    Stage.VISION: 25,
    Stage.INDEXING: 25,
    Stage.INSIGHTS: 15,
}


class ProgressReporter:
    """Writes stage/overall progress to the store, throttled to ~4 writes/second."""

    def __init__(self, job: Job) -> None:
        self.job = job
        self.store = get_store()
        self._last_write = 0.0

    def _overall(self) -> float:
        active = [s for s in self.job.stages if s.status != "skipped"]
        total = sum(STAGE_WEIGHTS[s.stage] for s in active) or 1
        done = sum(
            STAGE_WEIGHTS[s.stage] * (1.0 if s.status == "done" else s.progress) for s in active
        )
        return round(done / total, 4)

    def _state(self, stage: Stage) -> StageState:
        return next(s for s in self.job.stages if s.stage == stage)

    def start(self, stage: Stage, message: str) -> None:
        st = self._state(stage)
        st.status, st.progress, st.message = "running", 0.0, message
        self.job.stage, self.job.message, self.job.status = stage, message, VideoStatus.PROCESSING
        self._flush(force=True)

    def update(self, stage: Stage, frac: float, message: str) -> None:
        st = self._state(stage)
        st.progress, st.message = max(0.0, min(frac, 1.0)), message
        self.job.message = message
        self._flush()

    def finish(self, stage: Stage, message: str = "", skipped: bool = False) -> None:
        st = self._state(stage)
        st.status = "skipped" if skipped else "done"
        st.progress = 1.0
        if message:
            st.message = message
        self._flush(force=True)

    def fail(self, stage: Stage | None, error: str, code: str) -> None:
        if stage:
            self._state(stage).status = "failed"
        self.job.status = VideoStatus.FAILED
        self.job.error, self.job.error_code = error, code
        self._flush(force=True)

    def complete(self) -> None:
        self.job.status = VideoStatus.READY
        self.job.progress = 1.0
        self.job.message = "Ready"
        self._flush(force=True)

    def _flush(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last_write < 0.25:
            return
        self._last_write = now
        if self.job.status != VideoStatus.READY:
            self.job.progress = self._overall()
        self.store.save_job(self.job)


def process_video(job_id: str, video_id: str, vision: bool, force: bool = False) -> None:
    """Entry point for the queue. Never raises: failures are recorded on the job."""
    from app.services.container import get_embedder_cached, get_llm, get_vector_store

    settings = get_settings()
    store = get_store()
    job = store.get_job(job_id)
    if job is None:
        log.error("job.missing", job_id=job_id)
        return
    rep = ProgressReporter(job)
    stage: Stage | None = None
    t_start = time.perf_counter()
    log.info("job.start", job_id=job_id, video_id=video_id, vision=vision)

    try:
        # 1. metadata ---------------------------------------------------------
        stage = Stage.METADATA
        rep.start(stage, "Fetching video details")
        meta = fetch_metadata(video_id)
        if meta.duration and meta.duration > settings.max_video_seconds:
            raise VidAskError(
                f"Video is longer than the {settings.max_video_seconds // 60} min limit.",
                code="video_too_long",
            )
        rec = store.get_video(video_id) or VideoRecord(meta=meta)
        rec.meta, rec.status, rec.error, rec.latest_job_id = (
            meta,
            VideoStatus.PROCESSING,
            None,
            job_id,
        )
        store.upsert_video(rec)
        rep.finish(stage, meta.title)

        # 2. transcript -------------------------------------------------------
        stage = Stage.TRANSCRIPT
        rep.start(stage, "Looking for captions")
        transcript = None if force else store.get_transcript(video_id)
        if transcript is None:
            transcript = get_transcript(
                video_id,
                settings,
                meta.duration,
                lambda f, m: rep.update(Stage.TRANSCRIPT, f, m),
                spoken_hint=meta.language,
            )
            store.save_transcript(transcript)
        rec.transcript_source = transcript.source
        if not meta.duration and transcript.segments:
            rec.meta.duration = transcript.segments[-1].end
        if not rec.meta.language:
            rec.meta.language = transcript.language
        store.upsert_video(rec)
        rep.finish(stage, f"{len(transcript.segments)} lines · {transcript.source.value}")

        # 3. vision -----------------------------------------------------------
        stage = Stage.VISION
        visual: list[Chunk] = []
        if vision:
            rep.start(stage, "Analysing what's on screen")
            try:
                from app.pipeline.vision import extract_visual_chunks

                visual = extract_visual_chunks(
                    video_id,
                    settings,
                    rec.meta.duration,
                    lambda f, m: rep.update(Stage.VISION, f, m),
                )
                rec.vision_used = True
                rep.finish(stage, f"{len(visual)} on-screen moments")
            except Exception as exc:  # vision is best-effort; never fail the whole job
                log.exception("vision.failed", video_id=video_id)
                rep.finish(stage, f"Skipped: {exc}", skipped=True)
        else:
            rep.finish(stage, "Disabled", skipped=True)

        # 4. indexing ---------------------------------------------------------
        stage = Stage.INDEXING
        rep.start(stage, "Chunking transcript")
        chunks = chunk_segments(
            transcript.segments,
            video_id,
            target=settings.chunk_seconds,
            overlap=settings.chunk_overlap_seconds,
        )
        all_chunks = chunks + visual
        rep.update(stage, 0.05, "Loading embedding model")
        embedder = get_embedder_cached()
        vectors: list[list[float]] = []
        batch = max(settings.embedding_batch_size, 1)
        for i in range(0, len(all_chunks), batch):
            part = all_chunks[i : i + batch]
            vectors.extend(embedder.embed_documents([c.text for c in part]))
            done = min(i + batch, len(all_chunks))
            rep.update(
                stage, 0.1 + 0.8 * done / len(all_chunks), f"Embedding {done}/{len(all_chunks)}"
            )
        vs = get_vector_store()
        vs.delete_video(video_id)
        vs.upsert(all_chunks, vectors)
        store.save_chunks(video_id, all_chunks)
        # Searchable now: open chat while summary/chapters are written in the background.
        rec.status = VideoStatus.READY
        rec.insights_pending = settings.insights_enabled
        store.upsert_video(rec)
        rep.finish(stage, f"{len(chunks)} passages indexed")

        # 5. insights ---------------------------------------------------------
        stage = Stage.INSIGHTS
        if settings.insights_enabled:
            rep.start(stage, "Writing summary & chapters")
            from app.services.insights import generate_insights

            try:
                rec.insights = asyncio.run(
                    generate_insights(transcript, meta.title, rec.meta.duration, get_llm())
                )
            except Exception as exc:
                log.exception("insights.failed", video_id=video_id)
                from app.models.schemas import Insights

                rec.insights = Insights(error=str(exc))
            rep.finish(stage, "Done" if not rec.insights.error else "Summary unavailable")
        else:
            rep.finish(stage, "Disabled", skipped=True)

        rec.insights_pending = False
        store.upsert_video(rec)
        rep.complete()
        log.info(
            "job.done",
            job_id=job_id,
            video_id=video_id,
            seconds=round(time.perf_counter() - t_start, 1),
            chunks=len(chunks),
            visual=len(visual),
        )
    except Exception as exc:
        code = exc.code if isinstance(exc, VidAskError) else "processing_failed"
        message = exc.message if isinstance(exc, VidAskError) else str(exc)
        log.exception("job.failed", job_id=job_id, stage=stage, code=code)
        rep.fail(stage, message, code)
        failed = store.get_video(video_id)
        if failed and failed.status == VideoStatus.READY and failed.insights_pending:
            # Already indexed and chat-able; only the summary is lost.
            failed.insights_pending = False
            store.upsert_video(failed)
        elif failed:
            failed.status, failed.error = VideoStatus.FAILED, message
            store.upsert_video(failed)
