"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  ArrowUp,
  Info,
  MessageSquarePlus,
  Search,
  Sparkles,
  Square,
} from "lucide-react";
import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";

import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { Badge, Kbd } from "@/components/ui/misc";
import { SimpleTooltip } from "@/components/ui/tooltip";
import { useI18n } from "@/lib/i18n";
import type { ChatMessage } from "@/lib/types";
import { cn } from "@/lib/utils";

import { AnswerMarkdown } from "./answer-markdown";
import { TimestampChip } from "./timestamp-chip";
import type { ChatState } from "./use-chat";

export interface ChatPanelHandle {
  focus: () => void;
}

export const ChatPanel = forwardRef<
  ChatPanelHandle,
  { chat: ChatState; suggestions: string[]; className?: string }
>(function ChatPanel({ chat, suggestions, className }, ref) {
  const { t } = useI18n();
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const stickRef = useRef(true);
  const [draft, setDraft] = useState("");

  useImperativeHandle(ref, () => ({ focus: () => inputRef.current?.focus() }), []);

  // Keep pinned to the bottom while streaming unless the user scrolled up.
  useEffect(() => {
    const el = scrollRef.current;
    if (el && stickRef.current) el.scrollTop = el.scrollHeight;
  }, [chat.messages]);

  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [draft]);

  const submit = (q?: string) => {
    const text = (q ?? draft).trim();
    if (!text || chat.busy) return;
    stickRef.current = true;
    chat.send(text);
    setDraft("");
  };

  const empty = chat.messages.length === 0;

  return (
    <section className={cn("flex min-h-0 flex-col", className)} aria-label={t("chat.title")}>
      <div className="border-border flex h-12 shrink-0 items-center justify-between border-b px-4">
        <h2 className="flex items-center gap-2 text-sm font-medium">
          <Sparkles className="text-accent size-4" aria-hidden />
          {t("chat.title")}
        </h2>
        {!empty && (
          <SimpleTooltip label={t("chat.clear")}>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={chat.reset}
              aria-label={t("chat.clear")}
            >
              <MessageSquarePlus />
            </Button>
          </SimpleTooltip>
        )}
      </div>

      <div
        ref={scrollRef}
        onScroll={(e) => {
          const el = e.currentTarget;
          stickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
        }}
        className="min-h-0 flex-1 scrollbar-thin overflow-y-auto px-4 py-5"
        aria-live="polite"
        aria-busy={chat.busy}
      >
        {empty ? (
          <EmptyChat suggestions={suggestions} onPick={submit} />
        ) : (
          <ol className="space-y-6">
            <AnimatePresence initial={false}>
              {chat.messages.map((m) => (
                <motion.li
                  key={m.id}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2 }}
                >
                  {m.role === "user" ? <UserBubble text={m.content} /> : <AssistantMessage m={m} />}
                </motion.li>
              ))}
            </AnimatePresence>
          </ol>
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="border-border shrink-0 border-t p-3"
      >
        <div className="border-border bg-surface focus-within:border-border-strong flex items-end gap-2 rounded-xl border p-1.5 pl-3 transition-shadow focus-within:shadow-[0_0_0_3px_var(--accent-soft)]">
          <label htmlFor="question" className="sr-only">
            {t("chat.placeholder")}
          </label>
          <textarea
            id="question"
            ref={inputRef}
            rows={1}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                submit();
              }
              if (e.key === "Escape") inputRef.current?.blur();
            }}
            placeholder={t("chat.placeholder")}
            className="placeholder:text-fg-subtle max-h-40 min-h-9 flex-1 resize-none bg-transparent py-2 text-sm leading-5 outline-none focus-visible:outline-none"
          />
          {!draft && !chat.busy && <Kbd className="mb-2 hidden sm:inline-flex">/</Kbd>}
          {chat.busy ? (
            <Button
              type="button"
              size="icon-sm"
              variant="secondary"
              onClick={chat.stop}
              aria-label={t("chat.stop")}
            >
              <Square className="fill-current" />
            </Button>
          ) : (
            <Button
              type="submit"
              size="icon-sm"
              variant="accent"
              disabled={!draft.trim()}
              aria-label={t("chat.send")}
            >
              <ArrowUp />
            </Button>
          )}
        </div>
      </form>
    </section>
  );
});

function EmptyChat({
  suggestions,
  onPick,
}: {
  suggestions: string[];
  onPick: (q: string) => void;
}) {
  const { t } = useI18n();
  return (
    <div className="flex h-full flex-col justify-center">
      <div className="border-border bg-surface mx-auto mb-6 grid size-11 place-items-center rounded-2xl border shadow-sm">
        <Search className="text-fg-muted size-5" aria-hidden />
      </div>
      <p className="text-center text-base font-semibold tracking-tight">{t("chat.emptyTitle")}</p>
      <p className="text-fg-muted mx-auto mt-1.5 max-w-xs text-center text-sm leading-relaxed">
        {t("chat.emptyBody")}
      </p>
      {suggestions.length > 0 && (
        <div className="mt-8">
          <p className="text-fg-subtle mb-2.5 text-xs font-medium">{t("chat.suggested")}</p>
          <ul className="flex flex-col gap-2">
            {suggestions.map((q, i) => (
              <motion.li
                key={q}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.05 * i }}
              >
                <button
                  type="button"
                  onClick={() => onPick(q)}
                  className="border-border bg-surface text-fg-muted hover:border-border-strong hover:bg-surface-2 hover:text-fg w-full rounded-xl border px-3.5 py-2.5 text-left text-sm transition-colors"
                >
                  {q}
                </button>
              </motion.li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <p className="bg-fg text-bg max-w-[85%] rounded-2xl rounded-br-md px-3.5 py-2 text-sm leading-relaxed whitespace-pre-wrap">
        {text}
      </p>
    </div>
  );
}

function AssistantMessage({ m }: { m: ChatMessage }) {
  const { t } = useI18n();
  const r = m.result;
  const streaming = m.status === "streaming";
  return (
    <div className="flex gap-3">
      <Logo className="mt-0.5 size-6 shrink-0" />
      <div className="min-w-0 flex-1">
        {streaming && !m.content ? (
          <p className="text-fg-subtle flex items-center gap-2 text-sm">
            <span className="from-fg-subtle via-fg to-fg-subtle [animation:shimmer_2s_linear_infinite] bg-gradient-to-r bg-[length:200%_100%] bg-clip-text text-transparent">
              {t("chat.thinking")}
            </span>
          </p>
        ) : r?.abstained ? (
          <div className="border-border bg-bg-subtle flex items-start gap-2.5 rounded-xl border px-3.5 py-3 text-sm">
            <Info className="text-fg-subtle mt-0.5 size-4 shrink-0" aria-hidden />
            <div>
              <p className="font-medium">{t("chat.notCovered")}</p>
              <p className="text-fg-muted mt-0.5">{r.answer}</p>
            </div>
          </div>
        ) : (
          <div
            className={cn(
              streaming &&
                "[&_.prose-answer>*:last-child]:after:bg-accent [&_.prose-answer>*:last-child]:after:ml-0.5 [&_.prose-answer>*:last-child]:after:inline-block [&_.prose-answer>*:last-child]:after:h-[1em] [&_.prose-answer>*:last-child]:after:w-[2px] [&_.prose-answer>*:last-child]:after:translate-y-[2px] [&_.prose-answer>*:last-child]:after:animate-pulse [&_.prose-answer>*:last-child]:after:content-['']",
            )}
          >
            <AnswerMarkdown content={m.content} citations={r?.citations} />
          </div>
        )}

        {m.status === "error" && (
          <p
            role="alert"
            className="bg-danger-soft text-danger mt-2 flex items-center gap-2 rounded-lg px-3 py-2 text-sm"
          >
            <AlertTriangle className="size-4 shrink-0" aria-hidden />
            {m.error || t("chat.error")}
          </p>
        )}

        {r && !r.abstained && (r.citations.length > 0 || m.meta) && (
          <div className="border-border mt-3 flex flex-wrap items-center gap-x-3 gap-y-2 border-t pt-2.5">
            {r.citations.length > 0 && (
              <div className="flex flex-wrap items-center gap-1">
                <span className="text-fg-subtle mr-1 text-[11px] font-medium">
                  {t("chat.sources")}
                </span>
                {[...r.citations]
                  .sort((a, b) => a.seconds - b.seconds)
                  .map((c) => (
                    <TimestampChip key={c.label} seconds={c.seconds} citation={c} />
                  ))}
              </div>
            )}
            <span className="ml-auto flex items-center gap-1.5">
              <Badge>{t(r.strategy === "rag" ? "chat.strategy.rag" : "chat.strategy.full")}</Badge>
              <span className="text-fg-subtle tabular font-mono text-[11px]">
                {(r.latency_ms / 1000).toFixed(1)}s
              </span>
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
