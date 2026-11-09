"""End-to-end API tests with network/model calls replaced by fakes."""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from app.models.schemas import Transcript, VideoMeta
from app.providers.llm.fake import FakeProvider
from app.services import container
from tests.conftest import make_transcript

VID = "abcdefghijk"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    import app.pipeline.runner as runner

    def fake_meta(video_id: str) -> VideoMeta:
        return VideoMeta(video_id=video_id, url=f"https://youtu.be/{video_id}", title="Decorators", channel="Ch", duration=132)

    def fake_transcript(video_id: str, *_: object, **__: object) -> Transcript:
        return make_transcript(video_id)

    monkeypatch.setattr(runner, "fetch_metadata", fake_meta)
    monkeypatch.setattr(runner, "get_transcript", fake_transcript)
    container.override(llm=FakeProvider("A decorator wraps a function [00:12]. Fake [50:00]."))

    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c  # type: ignore[misc]


def wait_ready(client: TestClient, job_id: str) -> dict:  # type: ignore[type-arg]
    for _ in range(100):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("ready", "failed"):
            return job  # type: ignore[no-any-return]
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def sse_events(text: str) -> list[tuple[str, str]]:
    events, name = [], None
    for line in text.splitlines():
        if line.startswith("event:"):
            name = line[6:].strip()
        elif line.startswith("data:") and name:
            events.append((name, line[5:].strip()))
    return events


def test_health(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["queue"] == "thread"
    assert body["device"]["device"] in ("cpu", "cuda")


def test_invalid_url_returns_structured_error(client: TestClient) -> None:
    r = client.post("/api/videos", json={"url": "https://vimeo.com/1"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_url"


def test_process_then_cache_then_chat(client: TestClient) -> None:
    r = client.post("/api/videos", json={"url": f"https://youtu.be/{VID}?t=3"})
    assert r.status_code == 200
    body = r.json()
    assert body["cached"] is False
    job = wait_ready(client, body["job_id"])
    assert job["status"] == "ready", job
    assert job["progress"] == 1.0
    statuses = {s["stage"]: s["status"] for s in job["stages"]}
    assert statuses["vision"] == "skipped"
    assert statuses["indexing"] == "done"

    # SSE progress stream terminates with an end event
    ev = sse_events(client.get(f"/api/jobs/{body['job_id']}/events").text)
    assert ev[-1] == ("end", "ready")

    # second request is a cache hit
    again = client.post("/api/videos", json={"url": f"https://www.youtube.com/watch?v={VID}"}).json()
    assert again["cached"] is True and again["job_id"] is None

    video = client.get(f"/api/videos/{VID}").json()
    assert video["meta"]["title"] == "Decorators"
    assert video["transcript_source"] == "manual_captions"
    assert client.get("/api/videos").json()[0]["meta"]["video_id"] == VID

    tr = client.get(f"/api/videos/{VID}/transcript").json()
    assert len(tr["segments"]) == 11

    resp = client.post(f"/api/videos/{VID}/chat", json={"question": "What is a decorator?"})
    events = sse_events(resp.text)
    names = [n for n, _ in events]
    assert names[0] == "meta" and names[-1] == "done" and "token" in names
    done = json.loads(events[-1][1])
    assert [c["label"] for c in done["citations"]] == ["00:12"]
    assert done["removed_citations"] == ["50:00"]


def test_chat_unknown_video(client: TestClient) -> None:
    r = client.post("/api/videos/zzzzzzzzzzz/chat", json={"question": "hi"})
    assert r.status_code == 404


def test_settings_roundtrip(client: TestClient) -> None:
    body = client.put("/api/settings", json={"vision_enabled": True}).json()
    assert body["current"]["vision_enabled"] is True
    assert "ollama" in body["providers"]
