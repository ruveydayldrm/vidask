"""Hybrid retrieval (BM25 + dense) fused with RRF, then cross-encoder reranking."""

from __future__ import annotations

import re
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from app.core.logging import get_logger
from app.models.schemas import Chunk, ContextChunk
from app.providers.embeddings import Embedder, Reranker
from app.services.vector_store import VectorStore

log = get_logger(__name__)

_WORD = re.compile(r"\w+", re.UNICODE)
RRF_K = 60


def bm25_tokenize(text: str, prefix: int = 6) -> list[str]:
    """Case/diacritic-folded tokens truncated to a fixed prefix.

    Prefix truncation is a crude but well-known stemmer for agglutinative
    languages like Turkish ("videoda", "videonun" -> "videod"/"videon" ≈ "video"),
    and costs English very little.
    """
    folded = text.casefold().replace("̇", "").replace("ı", "i")
    return [t[:prefix] for t in _WORD.findall(folded) if len(t) > 1]


def rrf_fuse(rankings: list[list[int]], k: int = RRF_K) -> dict[int, float]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, idx in enumerate(ranking):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank + 1)
    return scores


@dataclass
class RetrievalResult:
    chunks: list[ContextChunk]
    timings_ms: dict[str, int]


class HybridRetriever:
    def __init__(
        self,
        embedder: Embedder,
        vectors: VectorStore,
        reranker: Reranker | None,
        candidates: int = 20,
    ) -> None:
        self.embedder = embedder
        self.vectors = vectors
        self.reranker = reranker
        self.candidates = candidates
        self._bm25: OrderedDict[tuple[str, int], BM25Okapi] = OrderedDict()
        self._lock = threading.Lock()

    def _bm25_for(self, video_id: str, chunks: list[Chunk]) -> BM25Okapi:
        key = (video_id, len(chunks))
        with self._lock:
            if key not in self._bm25:
                self._bm25[key] = BM25Okapi([bm25_tokenize(c.text) or ["_"] for c in chunks])
                if len(self._bm25) > 32:
                    self._bm25.popitem(last=False)
            return self._bm25[key]

    def retrieve(
        self,
        video_id: str,
        query: str,
        chunks: list[Chunk],
        top_k: int,
        *,
        use_bm25: bool = True,
        use_vector: bool = True,
        use_reranker: bool = True,
    ) -> RetrievalResult:
        """Hybrid search. The ``use_*`` switches exist for ablation studies (eval/)."""
        timings: dict[str, int] = {}
        if not chunks:
            return RetrievalResult([], timings)
        key_of = {(c.source.value, c.idx): i for i, c in enumerate(chunks)}

        bm_rank: list[int] = []
        if use_bm25:
            t0 = time.perf_counter()
            bm25 = self._bm25_for(video_id, chunks)
            bm_scores = bm25.get_scores(bm25_tokenize(query) or ["_"])
            bm_rank = sorted(range(len(chunks)), key=lambda i: bm_scores[i], reverse=True)
            bm_rank = [i for i in bm_rank if bm_scores[i] > 0][: self.candidates]
            timings["bm25"] = int((time.perf_counter() - t0) * 1000)

        vec_rank: list[int] = []
        if use_vector:
            t0 = time.perf_counter()
            qvec = self.embedder.embed_query(query)
            hits = self.vectors.search(video_id, qvec, self.candidates)
            vec_rank = [
                key_of[k] for h in hits if (k := (h.chunk.source.value, h.chunk.idx)) in key_of
            ]
            timings["vector"] = int((time.perf_counter() - t0) * 1000)

        fused = rrf_fuse([r for r in (bm_rank, vec_rank) if r])
        cand = sorted(fused, key=lambda i: fused[i], reverse=True)[: self.candidates]
        scores = {i: fused[i] for i in cand}

        if self.reranker and use_reranker and cand:
            t0 = time.perf_counter()
            rr = self.reranker.score(query, [chunks[i].text for i in cand])
            scores = dict(zip(cand, rr, strict=True))
            cand = sorted(cand, key=lambda i: scores[i], reverse=True)
            timings["rerank"] = int((time.perf_counter() - t0) * 1000)

        picked = cand[:top_k]
        result = [
            ContextChunk(
                start=chunks[i].start,
                end=chunks[i].end,
                text=chunks[i].text,
                source=chunks[i].source,
                score=round(float(scores[i]), 4),
            )
            for i in picked
        ]
        log.info(
            "retrieval.done",
            video_id=video_id,
            bm25_hits=len(bm_rank),
            vector_hits=len(vec_rank),
            returned=len(result),
            reranked=bool(self.reranker),
            **{f"{k}_ms": v for k, v in timings.items()},
        )
        return RetrievalResult(result, timings)
