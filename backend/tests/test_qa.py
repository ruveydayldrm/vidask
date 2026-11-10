from __future__ import annotations

from typing import Any

import pytest

from app.core.config import get_settings
from app.models.schemas import ChatRequest, ChatTurn, Transcript
from app.pipeline.chunking import chunk_segments
from app.providers.embeddings import HashEmbedder, OverlapReranker
from app.providers.llm import Message
from app.providers.llm.fake import FakeProvider
from app.services.qa import QAService, choose_strategy, retrieval_query
from app.services.retrieval import HybridRetriever
from app.services.vector_store import VectorStore


async def run(qa: QAService, t: Transcript, q: str, **kw: Any) -> list[dict[str, Any]]:
    chunks = chunk_segments(t.segments, t.video_id, target=45, overlap=10)
    req = ChatRequest(question=q, **kw)
    return [ev async for ev in qa.stream_answer(t, chunks, "Decorators 101", req)]


def streamed_text(events: list[dict[str, Any]]) -> str:
    return "".join(e["data"]["text"] for e in events if e["event"] == "token")


async def test_full_context_answer_with_valid_and_fake_citations(transcript: Transcript) -> None:
    llm = FakeProvider("A decorator wraps another function [00:12]. Invented by aliens [09:59].")
    qa = QAService(get_settings(), llm, retriever=None)
    events = await run(qa, transcript, "What is a decorator?")

    assert events[0]["event"] == "meta"
    assert events[0]["data"]["strategy"] == "full"
    done = events[-1]["data"]
    assert done["abstained"] is False
    assert [c["label"] for c in done["citations"]] == ["00:12"]
    assert done["removed_citations"] == ["09:59"]
    assert "09:59" not in streamed_text(events)
    assert "[00:12]" in streamed_text(events)
    # the prompt carried timestamped excerpts and the question
    prompt = llm.calls[0][-1].content
    assert "[00:00] Welcome" in prompt
    assert "Answer in English" in prompt
    assert "What is a decorator?" in prompt


@pytest.mark.parametrize(
    "reply", ["NO_ANSWER", "  NO_ANSWER.", "`NO_ANSWER`", "NO_ANSWER\nThe video..."]
)
async def test_abstention_is_localized(transcript: Transcript, reply: str) -> None:
    qa = QAService(get_settings(), FakeProvider(reply, chunk_size=2), retriever=None)
    events = await run(qa, transcript, "Videoda kuantum fiziğinden bahsediliyor mu?")
    done = events[-1]["data"]
    assert done["abstained"] is True
    assert done["answer"] == "Videoda bu konudan bahsedilmiyor."
    assert streamed_text(events) == ""


async def test_short_answer_that_looks_like_marker_prefix(transcript: Transcript) -> None:
    qa = QAService(get_settings(), FakeProvider("NO", chunk_size=1), retriever=None)
    events = await run(qa, transcript, "Is it yes or no?")
    assert events[-1]["data"]["abstained"] is False
    assert streamed_text(events) == "NO"


async def test_history_is_sent(transcript: Transcript) -> None:
    llm = FakeProvider("ok [00:12]")
    qa = QAService(get_settings(), llm, retriever=None)
    hist = [
        ChatTurn(role="user", content="first?"),
        ChatTurn(role="assistant", content="first answer"),
    ]
    await run(qa, transcript, "and then?", history=hist)
    roles = [m.role for m in llm.calls[0]]
    assert roles == ["system", "user", "assistant", "user"]


def test_choose_strategy() -> None:
    s = get_settings()
    assert choose_strategy(1000, 8192, s)[0] == "full"
    assert choose_strategy(7000, 8192, s)[0] == "rag"
    forced = s.model_copy(update={"context_strategy": "rag"})
    assert choose_strategy(10, 8192, forced)[0] == "rag"


def test_retrieval_query_includes_previous_question() -> None:
    req = ChatRequest(question="why?", history=[ChatTurn(role="user", content="what is wraps")])
    assert retrieval_query(req) == "what is wraps why?"


async def test_rag_path_uses_retrieved_passages_only(transcript: Transcript) -> None:
    s = get_settings().model_copy(update={"context_strategy": "rag", "retrieval_top_k": 2})
    emb = HashEmbedder()
    vs = VectorStore(s, emb.dim, "hash")
    chunks = chunk_segments(transcript.segments, transcript.video_id, target=45, overlap=10)
    vs.upsert(chunks, emb.embed_documents([c.text for c in chunks]))
    retriever = HybridRetriever(emb, vs, OverlapReranker(), candidates=5)

    def respond(msgs: list[Message]) -> str:
        return "Class decorators receive the class object [01:12]. Also [00:00]."

    qa = QAService(s, FakeProvider(respond), retriever)
    events = await run(qa, transcript, "What do class decorators receive?")
    meta = events[0]["data"]
    assert meta["strategy"] == "rag"
    assert len(meta["context"]) == 2
    assert any("class object" in c["text"] for c in meta["context"])
    done = events[-1]["data"]
    # [00:00] belongs to a passage that was NOT retrieved, so it must be dropped.
    assert "00:00" in done["removed_citations"]
    assert all(c["label"] != "00:00" for c in done["citations"])
