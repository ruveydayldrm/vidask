"""Job queue: Redis + RQ when available (Docker/Linux), in-process thread otherwise.

RQ forks per job and therefore does not run on native Windows; the thread
backend keeps local development working there with the same interface.
"""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

log = get_logger(__name__)
JOB_FN = "app.pipeline.runner.process_video"


class JobQueue(ABC):
    backend: str

    @abstractmethod
    def enqueue(self, job_id: str, video_id: str, vision: bool, force: bool) -> None: ...


class ThreadQueue(JobQueue):
    backend = "thread"

    def __init__(self) -> None:
        # One worker: models are memory-hungry and CPU-bound; parallel jobs only thrash.
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vidask-job")

    def enqueue(self, job_id: str, video_id: str, vision: bool, force: bool) -> None:
        from app.pipeline.runner import process_video

        self.pool.submit(process_video, job_id, video_id, vision, force)


class RQQueue(JobQueue):
    backend = "rq"

    def __init__(self, redis_url: str) -> None:
        from redis import Redis
        from rq import Queue

        self.queue = Queue("vidask", connection=Redis.from_url(redis_url))

    def enqueue(self, job_id: str, video_id: str, vision: bool, force: bool) -> None:
        self.queue.enqueue(
            JOB_FN, job_id, video_id, vision, force, job_id=job_id, job_timeout=4 * 3600
        )


def _redis_ok(url: str) -> bool:
    try:
        from redis import Redis

        return bool(Redis.from_url(url, socket_connect_timeout=1).ping())
    except Exception:
        return False


def build_queue(settings: Settings) -> JobQueue:
    choice = settings.queue_backend
    if choice == "auto":
        choice = (
            "rq"
            if settings.redis_url and sys.platform != "win32" and _redis_ok(settings.redis_url)
            else "thread"
        )
    queue: JobQueue = RQQueue(settings.redis_url) if choice == "rq" else ThreadQueue()
    log.info("queue.backend", backend=queue.backend)
    return queue


@lru_cache
def get_queue() -> JobQueue:
    return build_queue(get_settings())
