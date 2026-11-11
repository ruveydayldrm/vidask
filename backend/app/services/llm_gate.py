"""Lets interactive chat pre-empt background LLM work on a shared local model.

A local Ollama on a laptop CPU usually serves one request at a time, so a
3-minute "summarise this window" call would make a chat question wait three
minutes. Background callers (insights) go through ``background_complete``: it
yields while any chat is in flight and, if a chat starts mid-generation, aborts
its own stream (closing the HTTP connection stops Ollama generating), waits for
the chat to finish and starts that call again.

The gate is per process: it covers the API + in-process thread queue used for
local runs. With a separate RQ worker, chat and insights don't coordinate.
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from typing import cast

from app.core.logging import get_logger
from app.providers.llm import LLMProvider, Message

log = get_logger(__name__)


class LLMGate:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active = 0

    @property
    def busy(self) -> bool:
        return self._active > 0

    @contextmanager
    def interactive(self) -> Iterator[None]:
        with self._lock:
            self._active += 1
        try:
            yield
        finally:
            with self._lock:
                self._active -= 1


gate = LLMGate()


async def _wait_idle(g: LLMGate, poll: float) -> None:
    # Polling on purpose: chat and insights run on different threads/event loops,
    # so an asyncio.Event can't be shared between them.
    while g.busy:  # noqa: ASYNC110
        await asyncio.sleep(poll)


async def _consume(stream: AsyncIterator[str], parts: list[str]) -> None:
    async for delta in stream:
        parts.append(delta)


async def background_complete(
    llm: LLMProvider,
    messages: list[Message],
    *,
    json_mode: bool = False,
    max_tokens: int | None = None,
    g: LLMGate | None = None,
    poll: float = 0.5,
    max_restarts: int = 20,
) -> str:
    """``llm.complete`` that steps aside whenever an interactive request is running.

    The busy check runs beside the stream, not between tokens, because a CPU
    model can spend a minute reading a long prompt before its first token.
    """
    g = g or gate
    restarts = 0
    while True:
        await _wait_idle(g, poll)
        stream = cast(
            "AsyncIterator[str]", llm.stream(messages, json_mode=json_mode, max_tokens=max_tokens)
        )
        parts: list[str] = []
        task = asyncio.ensure_future(_consume(stream, parts))
        preempted = False
        try:
            while not task.done():
                await asyncio.wait({task}, timeout=poll)
                if not task.done() and g.busy and restarts < max_restarts:
                    task.cancel()
                    preempted = True
                    break
            if not preempted:
                task.result()  # re-raise provider errors
                return "".join(parts)
        finally:
            if not task.done():
                task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            aclose = getattr(stream, "aclose", None)
            if aclose is not None:
                await aclose()
        restarts += 1
        log.info("llm_gate.preempted", restarts=restarts)
