from app.core.config import get_settings
from app.models.schemas import Chunk
from app.providers.embeddings import HashEmbedder, OverlapReranker
from app.services.retrieval import HybridRetriever, bm25_tokenize, rrf_fuse
from app.services.vector_store import VectorStore


def test_bm25_tokenize_turkish_folding() -> None:
    assert bm25_tokenize("İstanbul'da IŞIK") == bm25_tokenize("istanbul'da ışık")
    # agglutinative suffixes collapse onto a shared prefix
    assert bm25_tokenize("videonun")[0][:5] == bm25_tokenize("videoda")[0][:5]


def test_rrf_prefers_items_ranked_high_in_both() -> None:
    fused = rrf_fuse([[1, 2, 3], [3, 1, 2]])
    assert max(fused, key=lambda k: fused[k]) == 1


def _chunks() -> list[Chunk]:
    texts = [
        "Introduction to the course and the instructor.",
        "Kubernetes pods are the smallest deployable units.",
        "A deployment manages replica sets for pods.",
        "Services expose pods over the network with a stable IP.",
        "Thanks for watching, subscribe for more.",
    ]
    return [
        Chunk(video_id="v", idx=i, start=i * 45, end=i * 45 + 45, text=t)
        for i, t in enumerate(texts)
    ]


def _retriever(reranker: bool) -> tuple[HybridRetriever, list[Chunk]]:
    emb = HashEmbedder()
    vs = VectorStore(get_settings(), emb.dim, "hash")
    chunks = _chunks()
    vs.upsert(chunks, emb.embed_documents([c.text for c in chunks]))
    return HybridRetriever(emb, vs, OverlapReranker() if reranker else None, candidates=5), chunks


def test_hybrid_finds_relevant_chunk() -> None:
    r, chunks = _retriever(reranker=True)
    res = r.retrieve("v", "how do services expose pods network", chunks, top_k=2)
    assert res.chunks[0].start == 135
    assert "rerank" in res.timings_ms


def test_without_reranker_returns_rrf_order() -> None:
    r, chunks = _retriever(reranker=False)
    res = r.retrieve("v", "deployment replica sets", chunks, top_k=1)
    assert res.chunks[0].start == 90


def test_ablation_switches() -> None:
    r, chunks = _retriever(reranker=True)
    bm = r.retrieve("v", "replica sets", chunks, top_k=1, use_vector=False, use_reranker=False)
    assert set(bm.timings_ms) == {"bm25"}
    vec = r.retrieve("v", "replica sets", chunks, top_k=1, use_bm25=False, use_reranker=False)
    assert set(vec.timings_ms) == {"vector"}


def test_vector_store_isolation_between_videos() -> None:
    r, _ = _retriever(reranker=False)
    assert r.vectors.has_video("v")
    assert not r.vectors.has_video("other")
    r.vectors.delete_video("v")
    assert not r.vectors.has_video("v")
