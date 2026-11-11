"use client";

import { ChevronDown, ChevronUp, ImageIcon, LocateFixed, Search, X } from "lucide-react";
import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { SimpleTooltip } from "@/components/ui/tooltip";
import { useI18n } from "@/lib/i18n";
import { activeIndex, formatTs } from "@/lib/time";
import type { TranscriptData } from "@/lib/types";
import { cn } from "@/lib/utils";

import { usePlayer } from "./player-context";

interface Row {
  key: string;
  start: number;
  text: string;
  visual: boolean;
}

const norm = (s: string) => s.toLocaleLowerCase("tr").normalize("NFC");

export function TranscriptPanel({ data }: { data: TranscriptData }) {
  const { t } = useI18n();
  const { currentTime, seekTo, jump } = usePlayer();
  const containerRef = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState("");
  const [matchCursor, setMatchCursor] = useState(0);
  const [follow, setFollow] = useState(true);
  const [flashKey, setFlashKey] = useState<string | null>(null);

  const rows = useMemo<Row[]>(() => {
    const r: Row[] = data.segments.map((s, i) => ({
      key: `s${i}`,
      start: s.start,
      text: s.text,
      visual: false,
    }));
    data.visual.forEach((v, i) =>
      r.push({ key: `v${i}`, start: v.start, text: v.text, visual: true }),
    );
    return r.sort((a, b) => a.start - b.start || Number(a.visual) - Number(b.visual));
  }, [data]);

  const spoken = useMemo(() => rows.filter((r) => !r.visual), [rows]);
  const activeKey = spoken[activeIndex(spoken, currentTime)]?.key;

  const matches = useMemo(() => {
    const q = norm(query.trim());
    if (q.length < 2) return [];
    return rows.filter((r) => norm(r.text).includes(q)).map((r) => r.key);
  }, [rows, query]);

  const scrollToKey = useCallback((key: string | undefined, smooth = true) => {
    const box = containerRef.current;
    if (!key || !box) return;
    const el = box.querySelector<HTMLElement>(`[data-key="${key}"]`);
    if (!el) return;
    box.scrollTo({
      top: el.offsetTop - box.clientHeight / 3,
      behavior: smooth ? "smooth" : "auto",
    });
  }, []);

  // follow playback
  useEffect(() => {
    if (follow && !query) scrollToKey(activeKey);
  }, [activeKey, follow, query, scrollToKey]);

  // explicit jumps (timestamp chips, chapters) always scroll + flash
  useEffect(() => {
    if (!jump) return;
    const key = spoken[activeIndex(spoken, jump.t)]?.key;
    setFollow(true);
    setFlashKey(key ?? null);
    scrollToKey(key);
    const id = setTimeout(() => setFlashKey(null), 1600);
    return () => clearTimeout(id);
  }, [jump, spoken, scrollToKey]);

  useEffect(() => {
    setMatchCursor(0);
    if (matches.length) scrollToKey(matches[0]);
  }, [matches, scrollToKey]);

  const step = (dir: 1 | -1) => {
    if (!matches.length) return;
    const next = (matchCursor + dir + matches.length) % matches.length;
    setMatchCursor(next);
    scrollToKey(matches[next]);
  };

  const matchSet = useMemo(() => new Set(matches), [matches]);
  const currentMatch = matches[matchCursor];

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex shrink-0 items-center gap-2 py-3">
        <div className="relative flex-1">
          <Search
            className="text-fg-subtle pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2"
            aria-hidden
          />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                step(e.shiftKey ? -1 : 1);
              }
              if (e.key === "Escape") setQuery("");
            }}
            placeholder={t("transcript.search")}
            aria-label={t("transcript.search")}
            className="border-border bg-surface placeholder:text-fg-subtle focus:border-border-strong h-8 w-full rounded-lg border pr-24 pl-8 text-sm outline-none"
          />
          {query && (
            <div className="absolute top-1/2 right-1 flex -translate-y-1/2 items-center gap-0.5">
              <span
                className="text-fg-subtle tabular px-1 font-mono text-[11px]"
                aria-live="polite"
              >
                {matches.length
                  ? `${matchCursor + 1}/${matches.length}`
                  : t("transcript.noMatches")}
              </span>
              <button
                type="button"
                onClick={() => step(-1)}
                className="text-fg-subtle hover:text-fg rounded p-0.5"
                aria-label="Previous match"
              >
                <ChevronUp className="size-3.5" />
              </button>
              <button
                type="button"
                onClick={() => step(1)}
                className="text-fg-subtle hover:text-fg rounded p-0.5"
                aria-label="Next match"
              >
                <ChevronDown className="size-3.5" />
              </button>
              <button
                type="button"
                onClick={() => setQuery("")}
                className="text-fg-subtle hover:text-fg rounded p-0.5"
                aria-label="Clear search"
              >
                <X className="size-3.5" />
              </button>
            </div>
          )}
        </div>
        <SimpleTooltip label={t("transcript.follow")}>
          <Button
            variant={follow ? "secondary" : "ghost"}
            size="icon-sm"
            aria-pressed={follow}
            aria-label={t("transcript.follow")}
            onClick={() => {
              setFollow((f) => !f);
              if (!follow) scrollToKey(activeKey);
            }}
          >
            <LocateFixed />
          </Button>
        </SimpleTooltip>
      </div>

      <div
        ref={containerRef}
        onWheel={() => follow && setFollow(false)}
        onTouchMove={() => follow && setFollow(false)}
        className="relative min-h-0 flex-1 scrollbar-thin overflow-y-auto pr-1 pb-6"
      >
        <ol className="space-y-px">
          {rows.map((r) => (
            <TranscriptRow
              key={r.key}
              row={r}
              active={r.key === activeKey}
              flash={r.key === flashKey}
              query={matchSet.has(r.key) ? query.trim() : ""}
              current={r.key === currentMatch}
              onSeek={seekTo}
              onScreenLabel={t("transcript.onScreen")}
            />
          ))}
        </ol>
      </div>
    </div>
  );
}

const TranscriptRow = memo(function TranscriptRow({
  row,
  active,
  flash,
  query,
  current,
  onSeek,
  onScreenLabel,
}: {
  row: Row;
  active: boolean;
  flash: boolean;
  query: string;
  current: boolean;
  onSeek: (t: number) => void;
  onScreenLabel: string;
}) {
  return (
    <li data-key={row.key}>
      <button
        type="button"
        onClick={() => onSeek(row.start)}
        aria-current={active ? "true" : undefined}
        className={cn(
          "group flex w-full gap-3 rounded-lg px-2 py-1.5 text-left text-sm leading-relaxed transition-colors",
          active ? "bg-surface-2 text-fg" : "text-fg-muted hover:bg-surface-2/60 hover:text-fg",
          flash && "animate-[flash_1.6s_ease-out]",
          current && "ring-accent/50 ring-1",
          row.visual && "border-visual/60 bg-visual-soft/40 my-1 border-l-2",
        )}
      >
        <span
          className={cn(
            "tabular mt-px w-12 shrink-0 font-mono text-[11.5px]",
            active ? "text-accent-text" : "text-fg-subtle group-hover:text-fg-muted",
          )}
        >
          {formatTs(row.start)}
        </span>
        <span className="min-w-0 flex-1">
          {row.visual && (
            <span className="text-visual mr-1.5 inline-flex items-center gap-1 text-[11px] font-medium">
              <ImageIcon className="size-3" aria-hidden />
              {onScreenLabel}
            </span>
          )}
          <Highlighted
            text={row.visual ? row.text.replace(/^Ekranda\/On screen:\s*/, "") : row.text}
            query={query}
          />
        </span>
      </button>
    </li>
  );
});

function Highlighted({ text, query }: { text: string; query: string }) {
  if (!query) return <>{text}</>;
  const lower = norm(text);
  const q = norm(query);
  const parts: React.ReactNode[] = [];
  let i = 0;
  let idx = lower.indexOf(q);
  while (idx !== -1) {
    parts.push(text.slice(i, idx));
    parts.push(
      <mark key={idx} className="bg-accent-soft text-fg rounded-sm px-0.5">
        {text.slice(idx, idx + q.length)}
      </mark>,
    );
    i = idx + q.length;
    idx = lower.indexOf(q, i);
  }
  parts.push(text.slice(i));
  return <>{parts}</>;
}
