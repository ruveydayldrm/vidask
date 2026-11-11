import asyncio
from collections.abc import AsyncIterator

import pytest

from app.providers.llm import LLMProvider, Message
from app.services.llm_gate import LLMGate, background_complete

MSG = [Message("user", "summarise")]


class SlowProvider(LLMProvider):
    """Waits `prefill` seconds before the first token (like a CPU model reading a long prompt)."""

    name = "slow"

    def __init__(self, prefill: float = 0.0, tokens: int = 5, gap: float = 0.0) -> None:
        super().__init__("slow", 4096)
        self.prefill, self.tokens, self.gap = prefill, tokens, gap
        self.started = 0
        self.closed = 0

    async def stream(
        self, messages: list[Message], *, json_mode: bool = False, max_tokens: int | None = None
    ) -> AsyncIterator[str]:
        self.started += 1
        try:
            await asyncio.sleep(self.prefill)
            for i in range(self.tokens):
                yield f"t{i} "
                await asyncio.sleep(self.gap)
        finally:
            self.closed += 1


async def test_runs_normally_when_idle() -> None:
    llm = SlowProvider(tokens=3)
    out = await background_complete(llm, MSG, g=LLMGate(), poll=0.01)
    assert out == "t0 t1 t2 "
    assert llm.started == 1


async def test_waits_while_chat_is_active() -> None:
    g = LLMGate()
    llm = SlowProvider(tokens=2)
    with g.interactive():
        task = asyncio.create_task(background_complete(llm, MSG, g=g, poll=0.01))
        await asyncio.sleep(0.05)
        assert llm.started == 0  # did not start while chat was running
    assert await task == "t0 t1 "


async def test_chat_preempts_during_prefill_and_call_restarts() -> None:
    g = LLMGate()
    llm = SlowProvider(prefill=0.2, tokens=2)
    task = asyncio.create_task(background_complete(llm, MSG, g=g, poll=0.01))
    await asyncio.sleep(0.05)  # background call is "reading the prompt"
    with g.interactive():
        await asyncio.sleep(0.05)
        assert llm.closed == 1  # aborted without waiting for the first token
    assert await task == "t0 t1 "
    assert llm.started == 2


async def test_provider_errors_propagate() -> None:
    class Broken(SlowProvider):
        async def stream(self, messages, *, json_mode=False, max_tokens=None):  # type: ignore[override]
            raise RuntimeError("ollama down")
            yield ""

    with pytest.raises(RuntimeError, match="ollama down"):
        await background_complete(Broken(), MSG, g=LLMGate(), poll=0.01)


def test_gate_counts_nested_requests() -> None:
    g = LLMGate()
    with g.interactive():
        with g.interactive():
            assert g.busy
        assert g.busy
    assert not g.busy
