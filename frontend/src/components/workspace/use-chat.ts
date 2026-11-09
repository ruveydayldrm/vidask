"use client";

import { useCallback, useRef, useState } from "react";

import { ApiError, streamChat } from "@/lib/api";
import type { Lang } from "@/lib/i18n";
import type { AnswerResult, ChatMessage } from "@/lib/types";
import { uid } from "@/lib/utils";

export function useChat(videoId: string, lang: Lang) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const patch = (id: string, fn: (m: ChatMessage) => ChatMessage) =>
    setMessages((prev) => prev.map((m) => (m.id === id ? fn(m) : m)));

  const send = useCallback(
    async (question: string) => {
      const q = question.trim();
      if (!q || busy) return;
      const history = messages
        .filter((m) => m.status !== "error" && m.content)
        .map((m) => ({ role: m.role, content: m.result?.answer ?? m.content }));
      const userMsg: ChatMessage = { id: uid(), role: "user", content: q };
      const botId = uid();
      setMessages((prev) => [...prev, userMsg, { id: botId, role: "assistant", content: "", status: "streaming" }]);
      setBusy(true);
      const ctrl = new AbortController();
      abortRef.current = ctrl;

      try {
        const events = await streamChat(videoId, { question: q, history, lang }, ctrl.signal);
        for await (const ev of events) {
          const data = JSON.parse(ev.data);
          if (ev.event === "meta") {
            patch(botId, (m) => ({ ...m, meta: { strategy: data.strategy, model: data.model, provider: data.provider } }));
          } else if (ev.event === "token") {
            patch(botId, (m) => ({ ...m, content: m.content + data.text }));
          } else if (ev.event === "done") {
            const result = data as AnswerResult;
            patch(botId, (m) => ({ ...m, content: result.answer, result, status: "done" }));
          } else if (ev.event === "error") {
            patch(botId, (m) => ({ ...m, status: "error", error: data.message }));
          }
        }
      } catch (e) {
        if ((e as Error).name === "AbortError") {
          patch(botId, (m) => ({ ...m, status: "done" }));
        } else {
          const err = e as ApiError;
          patch(botId, (m) => ({ ...m, status: "error", error: err.message, content: m.content }));
        }
      } finally {
        setMessages((prev) =>
          prev.map((m) => (m.id === botId && m.status === "streaming" ? { ...m, status: "done" } : m)),
        );
        setBusy(false);
        abortRef.current = null;
      }
    },
    [busy, messages, videoId, lang],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);
  const reset = useCallback(() => {
    abortRef.current?.abort();
    setMessages([]);
  }, []);

  return { messages, busy, send, stop, reset };
}

export type ChatState = ReturnType<typeof useChat>;
