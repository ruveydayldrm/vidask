import json

import httpx
import pytest

from app.core.errors import ProviderError
from app.providers.llm import Message, build_llm
from app.providers.llm.fake import FakeProvider
from app.providers.llm.gemini import GeminiProvider
from app.providers.llm.groq import GroqProvider
from app.providers.llm.ollama import OllamaProvider

MSGS = [Message("system", "be brief"), Message("user", "hi"), Message("assistant", "yo"), Message("user", "q")]


def _transport(handler):  # type: ignore[no-untyped-def]
    return httpx.MockTransport(handler)


async def test_ollama_streams_ndjson() -> None:
    seen: dict[str, object] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen.update(json.loads(req.content))
        lines = [
            {"message": {"content": "Hel"}, "done": False},
            {"message": {"content": "lo"}, "done": False},
            {"message": {"content": ""}, "done": True},
        ]
        return httpx.Response(200, text="\n".join(json.dumps(x) for x in lines))

    p = OllamaProvider("qwen2.5:3b", 4096, transport=_transport(handler))
    assert await p.complete(MSGS, json_mode=True) == "Hello"
    assert seen["format"] == "json"
    assert seen["options"]["num_ctx"] == 4096  # type: ignore[index]


async def test_ollama_error_status() -> None:
    p = OllamaProvider("m", 2048, transport=_transport(lambda r: httpx.Response(404, text="model not found")))
    with pytest.raises(ProviderError, match="404"):
        await p.complete(MSGS)


async def test_groq_streams_sse() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.headers["authorization"] == "Bearer k"
        body = json.loads(req.content)
        assert body["messages"][0]["role"] == "system"
        events = [
            {"choices": [{"delta": {"content": "A"}}]},
            {"choices": [{"delta": {}}]},
            {"choices": [{"delta": {"content": "B"}}]},
        ]
        text = "".join(f"data: {json.dumps(e)}\n\n" for e in events) + "data: [DONE]\n\n"
        return httpx.Response(200, text=text)

    p = GroqProvider("llama", 32768, api_key="k", transport=_transport(handler))
    assert await p.complete(MSGS) == "AB"


async def test_gemini_maps_roles_and_streams() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        assert body["systemInstruction"]["parts"][0]["text"] == "be brief"
        assert [c["role"] for c in body["contents"]] == ["user", "model", "user"]
        assert req.url.params["alt"] == "sse"
        ev = {"candidates": [{"content": {"parts": [{"text": "Merhaba"}]}}]}
        return httpx.Response(200, text=f"data: {json.dumps(ev)}\n\n")

    p = GeminiProvider("gemini-x", 100000, api_key="k", transport=_transport(handler))
    assert await p.complete(MSGS) == "Merhaba"


def test_hosted_providers_require_keys() -> None:
    with pytest.raises(ProviderError):
        GroqProvider("m", 1, api_key="")
    with pytest.raises(ProviderError):
        GeminiProvider("m", 1, api_key="")


async def test_fake_provider_records_calls() -> None:
    p = FakeProvider(lambda m: m[-1].content.upper())
    assert await p.complete([Message("user", "abc")]) == "ABC"
    assert len(p.calls) == 1


def test_factory() -> None:
    from app.core.config import get_settings

    s = get_settings()
    assert build_llm(s, provider="ollama").name == "ollama"
    assert build_llm(s, provider="fake").name == "fake"
    with pytest.raises(ProviderError):
        build_llm(s, provider="groq")  # no key in test env
