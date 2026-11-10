"""Qdrant wrapper. Uses a Qdrant server when QDRANT_URL is set, otherwise embedded mode."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass

from qdrant_client import QdrantClient, models

from app.core.config import Settings
from app.core.logging import get_logger
from app.models.schemas import Chunk, ChunkSource

log = get_logger(__name__)

_clients: dict[str, QdrantClient] = {}
_clients_lock = threading.Lock()


def _client(settings: Settings) -> QdrantClient:
    key = settings.qdrant_url or str(settings.data_dir / "qdrant")
    with _clients_lock:
        if key not in _clients:
            if settings.qdrant_url:
                _clients[key] = QdrantClient(url=settings.qdrant_url, timeout=30)
            else:
                (settings.data_dir / "qdrant").mkdir(parents=True, exist_ok=True)
                _clients[key] = QdrantClient(path=key)
            log.info("qdrant.connected", target=key)
        return _clients[key]


@dataclass
class ScoredChunk:
    chunk: Chunk
    score: float


class VectorStore:
    def __init__(self, settings: Settings, dim: int, model_name: str) -> None:
        self.client = _client(settings)
        # One collection per embedding model so switching models never mixes vectors.
        suffix = model_name.replace("/", "_").replace(":", "_").lower()
        self.collection = f"{settings.qdrant_collection}__{suffix}"
        self.dim = dim
        self._ensure()

    def _ensure(self) -> None:
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                self.collection,
                vectors_config=models.VectorParams(size=self.dim, distance=models.Distance.COSINE),
            )
            if (
                not hasattr(self.client, "_client")
                or "Local" not in type(self.client._client).__name__
            ):
                self.client.create_payload_index(
                    self.collection, "video_id", models.PayloadSchemaType.KEYWORD
                )

    @staticmethod
    def _video_filter(video_id: str) -> models.Filter:
        return models.Filter(
            must=[models.FieldCondition(key="video_id", match=models.MatchValue(value=video_id))]
        )

    def has_video(self, video_id: str) -> bool:
        res = self.client.count(self.collection, count_filter=self._video_filter(video_id))
        return res.count > 0

    def delete_video(self, video_id: str) -> None:
        self.client.delete(
            self.collection,
            points_selector=models.FilterSelector(filter=self._video_filter(video_id)),
        )

    def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        points = [
            models.PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{c.video_id}:{c.source}:{c.idx}")),
                vector=v,
                payload=c.model_dump(mode="json"),
            )
            for c, v in zip(chunks, vectors, strict=True)
        ]
        for i in range(0, len(points), 128):
            self.client.upsert(self.collection, points=points[i : i + 128])

    def search(self, video_id: str, vector: list[float], limit: int) -> list[ScoredChunk]:
        res = self.client.query_points(
            self.collection,
            query=vector,
            query_filter=self._video_filter(video_id),
            limit=limit,
            with_payload=True,
        )
        out = []
        for p in res.points:
            payload = dict(p.payload or {})
            payload.setdefault("source", ChunkSource.TRANSCRIPT.value)
            out.append(ScoredChunk(Chunk.model_validate(payload), float(p.score)))
        return out
