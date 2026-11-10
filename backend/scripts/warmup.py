"""Download and load every configured model once, so the first request is fast.

Usage: uv run python scripts/warmup.py
"""

from __future__ import annotations

import time

from app.core.config import get_settings
from app.core.device import detect_device
from app.core.logging import configure_logging, get_logger
from app.providers.embeddings import get_embedder, get_reranker


def main() -> None:
    s = get_settings()
    configure_logging(s.log_level)
    log = get_logger("warmup")
    dev = detect_device(s.device, s.min_gpu_vram_gb)
    log.info("warmup.device", device=dev.device, reason=dev.reason)

    t = time.perf_counter()
    emb = get_embedder(s)
    emb.embed_query("merhaba dünya / hello world")
    log.info(
        "warmup.embedder_ready",
        model=s.embedding_model,
        dim=emb.dim,
        s=round(time.perf_counter() - t, 1),
    )

    t = time.perf_counter()
    rr = get_reranker(s)
    if rr:
        rr.score("test", ["a test passage"])
        log.info(
            "warmup.reranker_ready", model=s.reranker_model, s=round(time.perf_counter() - t, 1)
        )


if __name__ == "__main__":
    main()
