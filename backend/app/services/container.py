"""Lazily-built singletons (one per process). Swappable in tests via `override`."""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.providers.embeddings import Embedder, get_embedder, get_reranker
from app.providers.llm import LLMProvider, build_llm
from app.services.retrieval import HybridRetriever
from app.services.store import Store
from app.services.vector_store import VectorStore

_overrides: dict[str, Any] = {}
_store: Store | None = None


def override(**kwargs: Any) -> None:
    """Test hook: override(llm=FakeProvider(...), embedder=HashEmbedder(), ...)."""
    _overrides.update(kwargs)


def clear_overrides() -> None:
    global _store
    _overrides.clear()
    _store = None


def get_store() -> Store:
    global _store
    if "store" in _overrides:
        return _overrides["store"]  # type: ignore[no-any-return]
    if _store is None:
        _store = Store(get_settings().db_path)
    return _store


def get_llm() -> LLMProvider:
    if "llm" in _overrides:
        return _overrides["llm"]  # type: ignore[no-any-return]
    return build_llm(get_settings())


def get_embedder_cached() -> Embedder:
    if "embedder" in _overrides:
        return _overrides["embedder"]  # type: ignore[no-any-return]
    return get_embedder(get_settings())


def get_vector_store() -> VectorStore:
    if "vector_store" in _overrides:
        return _overrides["vector_store"]  # type: ignore[no-any-return]
    s = get_settings()
    emb = get_embedder_cached()
    return VectorStore(s, emb.dim, s.embedding_model)


def get_retriever() -> HybridRetriever:
    if "retriever" in _overrides:
        return _overrides["retriever"]  # type: ignore[no-any-return]
    s = get_settings()
    reranker = _overrides["reranker"] if "reranker" in _overrides else get_reranker(s)
    return _retriever(get_embedder_cached(), get_vector_store(), reranker, s.retrieval_candidates)


_retrievers: dict[tuple[int, int, int, int], HybridRetriever] = {}


def _retriever(emb: Embedder, vs: VectorStore, rr: Any, n: int) -> HybridRetriever:
    key = (id(emb), id(vs.client), id(rr), n)
    if key not in _retrievers:
        _retrievers[key] = HybridRetriever(emb, vs, rr, n)
    return _retrievers[key]
