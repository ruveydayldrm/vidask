"""SQLite persistence for videos, transcripts, chunks, insights and jobs.

SQLite (WAL mode) is shared by the API and the worker process, which is what lets
progress flow from a background RQ worker to the SSE endpoint without extra
infrastructure. Large structures are stored as JSON columns: they are always
read and written as a whole, so normalising them would buy nothing.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.core.errors import NotFoundError
from app.models.schemas import (
    STAGE_ORDER,
    Chunk,
    Insights,
    Job,
    StageState,
    Transcript,
    VideoRecord,
    VideoStatus,
    utcnow,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    video_id TEXT PRIMARY KEY,
    record_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS transcripts (
    video_id TEXT PRIMARY KEY,
    transcript_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
    video_id TEXT PRIMARY KEY,
    chunks_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL,
    job_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS jobs_video ON jobs(video_id);
"""


class Store:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        with self._conn() as c:
            c.executescript(_SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn = conn
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    # --- videos ------------------------------------------------------------
    def upsert_video(self, rec: VideoRecord) -> VideoRecord:
        rec.updated_at = utcnow()
        with self._conn() as c:
            c.execute(
                "INSERT INTO videos(video_id, record_json, updated_at) VALUES(?,?,?) "
                "ON CONFLICT(video_id) DO UPDATE SET record_json=excluded.record_json, "
                "updated_at=excluded.updated_at",
                (rec.meta.video_id, rec.model_dump_json(), rec.updated_at.isoformat()),
            )
        return rec

    def get_video(self, video_id: str) -> VideoRecord | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT record_json FROM videos WHERE video_id=?", (video_id,)
            ).fetchone()
        return VideoRecord.model_validate_json(row[0]) if row else None

    def require_video(self, video_id: str) -> VideoRecord:
        rec = self.get_video(video_id)
        if rec is None:
            raise NotFoundError(f"Video {video_id} has not been processed.")
        return rec

    def list_videos(self, limit: int = 20, status: VideoStatus | None = None) -> list[VideoRecord]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT record_json FROM videos ORDER BY updated_at DESC LIMIT ?", (limit * 3,)
            ).fetchall()
        recs = [VideoRecord.model_validate_json(r[0]) for r in rows]
        if status:
            recs = [r for r in recs if r.status == status]
        return recs[:limit]

    def set_insights(self, video_id: str, insights: Insights) -> None:
        rec = self.require_video(video_id)
        rec.insights = insights
        self.upsert_video(rec)

    # --- transcript / chunks -----------------------------------------------
    def save_transcript(self, t: Transcript) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO transcripts(video_id, transcript_json) VALUES(?,?)",
                (t.video_id, t.model_dump_json()),
            )

    def get_transcript(self, video_id: str) -> Transcript | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT transcript_json FROM transcripts WHERE video_id=?", (video_id,)
            ).fetchone()
        return Transcript.model_validate_json(row[0]) if row else None

    def save_chunks(self, video_id: str, chunks: list[Chunk]) -> None:
        data = json.dumps([ch.model_dump(mode="json") for ch in chunks])
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO chunks(video_id, chunks_json) VALUES(?,?)", (video_id, data)
            )

    def get_chunks(self, video_id: str) -> list[Chunk]:
        with self._conn() as c:
            row = c.execute(
                "SELECT chunks_json FROM chunks WHERE video_id=?", (video_id,)
            ).fetchone()
        return [Chunk.model_validate(x) for x in json.loads(row[0])] if row else []

    # --- jobs --------------------------------------------------------------
    def create_job(self, video_id: str, skip: set[str] | None = None) -> Job:
        skip = skip or set()
        job = Job(
            id=uuid.uuid4().hex,
            video_id=video_id,
            stages=[
                StageState(stage=s, status="skipped" if s.value in skip else "pending")
                for s in STAGE_ORDER
            ],
        )
        self.save_job(job)
        return job

    def save_job(self, job: Job) -> Job:
        job.updated_at = utcnow()
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO jobs(id, video_id, job_json, updated_at) VALUES(?,?,?,?)",
                (job.id, job.video_id, job.model_dump_json(), job.updated_at.isoformat()),
            )
        return job

    def get_job(self, job_id: str) -> Job | None:
        with self._conn() as c:
            row = c.execute("SELECT job_json FROM jobs WHERE id=?", (job_id,)).fetchone()
        return Job.model_validate_json(row[0]) if row else None

    def active_job_for(self, video_id: str) -> Job | None:
        with self._conn() as c:
            rows = c.execute(
                "SELECT job_json FROM jobs WHERE video_id=? ORDER BY updated_at DESC LIMIT 1",
                (video_id,),
            ).fetchall()
        for (raw,) in rows:
            job = Job.model_validate_json(raw)
            if job.status in (VideoStatus.PENDING, VideoStatus.PROCESSING):
                return job
        return None

    def fail_stale_jobs(self) -> int:
        """Mark jobs left 'processing' by a crashed process as failed (called on startup)."""
        count = 0
        with self._conn() as c:
            rows = c.execute("SELECT job_json FROM jobs").fetchall()
        for (raw,) in rows:
            job = Job.model_validate_json(raw)
            if job.status in (VideoStatus.PENDING, VideoStatus.PROCESSING):
                job.status = VideoStatus.FAILED
                job.error = "Interrupted by a server restart. Please retry."
                job.error_code = "interrupted"
                self.save_job(job)
                rec = self.get_video(job.video_id)
                if rec and rec.status != VideoStatus.READY:
                    rec.status = VideoStatus.FAILED
                    rec.error = job.error
                    self.upsert_video(rec)
                count += 1
        return count
