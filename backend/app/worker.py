"""RQ worker entry point: `python -m app.worker` (Linux/Docker only)."""

from __future__ import annotations

from redis import Redis
from rq import Worker

from app.core.config import get_settings
from app.core.logging import configure_logging


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    if not settings.redis_url:
        raise SystemExit("REDIS_URL is not set; the API runs jobs in-process instead.")
    conn = Redis.from_url(settings.redis_url)
    Worker(["vidask"], connection=conn).work(with_scheduler=False)


if __name__ == "__main__":
    main()
