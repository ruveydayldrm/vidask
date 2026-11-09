"use client";

import { AudioLines, Captions, Globe, ImageIcon, ListOrdered } from "lucide-react";
import { useMemo } from "react";

import { useI18n } from "@/lib/i18n";
import { activeIndex, formatTs } from "@/lib/time";
import type { VideoRecord } from "@/lib/types";
import { cn } from "@/lib/utils";

import { AnswerMarkdown } from "./answer-markdown";
import { usePlayer } from "./player-context";

export function SummaryPanel({ record }: { record: VideoRecord }) {
  const { t } = useI18n();
  const summary = record.insights?.summary;
  const src = record.transcript_source;
  const SrcIcon = src === "whisper" ? AudioLines : Captions;

  return (
    <div className="space-y-6 py-4">
      {summary ? (
        <div className="text-[15px] leading-relaxed">
          <AnswerMarkdown content={summary} />
        </div>
      ) : (
        <p className="rounded-xl border border-dashed border-border-strong px-4 py-6 text-center text-sm text-fg-subtle">
          {t("summary.empty")}
        </p>
      )}
      <dl className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        <Fact icon={<SrcIcon />} label={t("summary.source")} value={src ? t(`source.${src}`) : "—"} />
        <Fact icon={<Globe />} label={t("summary.language")} value={(record.meta.language ?? "—").toUpperCase()} />
        <Fact
          icon={<ImageIcon />}
          label={t("summary.vision")}
          value={record.vision_used ? t("summary.on") : t("summary.off")}
        />
      </dl>
    </div>
  );
}

function Fact({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-border bg-surface px-3 py-2.5">
      <span className="grid size-8 place-items-center rounded-lg bg-surface-2 text-fg-muted [&_svg]:size-4">{icon}</span>
      <div className="min-w-0">
        <dt className="text-[11px] text-fg-subtle">{label}</dt>
        <dd className="truncate text-sm font-medium">{value}</dd>
      </div>
    </div>
  );
}

export function ChaptersPanel({ record }: { record: VideoRecord }) {
  const { t } = useI18n();
  const { currentTime, seekTo } = usePlayer();
  const chapters = useMemo(() => record.insights?.chapters ?? [], [record]);
  const active = activeIndex(chapters, currentTime);

  if (!chapters.length)
    return (
      <p className="my-4 rounded-xl border border-dashed border-border-strong px-4 py-6 text-center text-sm text-fg-subtle">
        <ListOrdered className="mx-auto mb-2 size-5" aria-hidden />
        {t("chapters.empty")}
      </p>
    );

  return (
    <ol className="relative space-y-1 py-4">
      <span className="absolute top-6 bottom-6 left-[27px] w-px bg-border" aria-hidden />
      {chapters.map((c, i) => {
        const end = chapters[i + 1]?.start ?? record.meta.duration;
        const progress =
          i === active && end > c.start ? Math.min(1, (currentTime - c.start) / (end - c.start)) : i < active ? 1 : 0;
        return (
          <li key={`${c.start}-${c.title}`}>
            <button
              type="button"
              onClick={() => seekTo(c.start)}
              aria-current={i === active ? "true" : undefined}
              className={cn(
                "group relative flex w-full items-center gap-4 rounded-xl px-3 py-2.5 text-left transition-colors",
                i === active ? "bg-surface-2" : "hover:bg-surface-2/60",
              )}
            >
              <span
                className={cn(
                  "relative z-10 grid size-[30px] shrink-0 place-items-center rounded-full border text-[11px] font-semibold tabular",
                  i === active
                    ? "border-accent bg-accent text-accent-fg"
                    : i < active
                      ? "border-border-strong bg-surface text-fg-muted"
                      : "border-border bg-surface text-fg-subtle",
                )}
              >
                {i + 1}
              </span>
              <span className="min-w-0 flex-1">
                <span className={cn("block truncate text-sm", i === active ? "font-medium text-fg" : "text-fg-muted group-hover:text-fg")}>
                  {c.title}
                </span>
                <span className="mt-1 block h-0.5 overflow-hidden rounded-full bg-border">
                  <span className="block h-full bg-accent transition-[width] duration-300" style={{ width: `${progress * 100}%` }} />
                </span>
              </span>
              <span className="font-mono text-xs text-fg-subtle tabular">{formatTs(c.start)}</span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
