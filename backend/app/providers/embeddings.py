"""Embedding and reranking models behind small interfaces (so tests can fake them)."""

from __future__ import annotations

import hashlib
import math
import re
import threading
from abc import ABC, abstractmethod
from functools import lru_cache

from app.core.config import Settings
from app.core.device import detect_device
from app.core.logging import get_logger

log = get_logger(__name__)


class Embedder(ABC):
    dim: int

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    def embed_query(self, text: str) -> list[float]: ...


class Reranker(ABC):
    @abstractmethod
    def score(self, query: str, docs: list[str]) -> list[float]: ...


class SentenceTransformerEmbedder(Embedder):
    def __init__(self, model_name: str, device: str, batch_size: int = 16) -> None:
        from sentence_transformers import SentenceTransformer

        log.info("embedder.loading", model=model_name, device=device)
        self.model = SentenceTransformer(model_name, device=device)
        self.batch_size = batch_size
        self.dim = int(self.model.get_sentence_embedding_dimension() or 0)
        self._lock = threading.Lock()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        with self._lock:
            vecs = self.model.encode(
                texts, batch_size=self.batch_size, normalize_embeddings=True, show_progress_bar=False
            )
        return [v.tolist() for v in vecs]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class CrossEncoderReranker(Reranker):
    def __init__(self, model_name: str, device: str) -> None:
        from sentence_transformers import CrossEncoder

        log.info("reranker.loading", model=model_name, device=device)
        self.model = CrossEncoder(model_name, device=device, max_length=512)
        self._lock = threading.Lock()

    def score(self, query: str, docs: list[str]) -> list[float]:
        if not docs:
            return []
        with self._lock:
            scores = self.model.predict([(query, d) for d in docs], show_progress_bar=False)
        return [float(s) for s in scores]


_TOKEN = re.compile(r"\w+", re.UNICODE)


class HashEmbedder(Embedder):
    """Bag-of-words hashing embedder. Zero downloads; used in tests."""

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        for tok in _TOKEN.findall(text.lower()):
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            v[h % self.dim] += 1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


class OverlapReranker(Reranker):
    """Token-overlap scorer for tests."""

    def score(self, query: str, docs: list[str]) -> list[float]:
        q = set(_TOKEN.findall(query.lower()))
        return [len(q & set(_TOKEN.findall(d.lower()))) / (len(q) or 1) for d in docs]


_lock = threading.Lock()


@lru_cache
def _embedder(model: str, device: str, batch: int) -> Embedder:
    return SentenceTransformerEmbedder(model, device, batch)


@lru_cache
def _reranker(model: str, device: str) -> Reranker:
    return CrossEncoderReranker(model, device)


def get_embedder(settings: Settings) -> Embedder:
    if settings.embedding_model == "hash":
        return HashEmbedder()
    dev = detect_device(settings.device, settings.min_gpu_vram_gb).device
    with _lock:
        return _embedder(settings.embedding_model, dev, settings.embedding_batch_size)


def get_reranker(settings: Settings) -> Reranker | None:
    if not settings.reranker_enabled:
        return None
    if settings.reranker_model == "overlap":
        return OverlapReranker()
    dev = detect_device(settings.device, settings.min_gpu_vram_gb).device
    with _lock:
        return _reranker(settings.reranker_model, dev)
