"use client";

import { ImageIcon, Play } from "lucide-react";
import { useMemo } from "react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useI18n } from "@/lib/i18n";
import { activeIndex, formatTs } from "@/lib/time";
import type { Citation, Segment } from "@/lib/types";
import { cn } from "@/lib/utils";

import { usePlayerOptional } from "./player-context";

export function previewFromSegments(segments: Segment[], t: number, maxChars = 220): string {
  if (!segments.length) return "";
  const i = Math.max(0, activeIndex(segments, t));
  let out = "";
  for (let j = i; j < segments.length && out.length < maxChars; j++)
    out += (out ? " " : "") + segments[j]!.text;
  return out.length > maxChars ? out.slice(0, maxChars).replace(/\s+\S*$/, "") + "…" : out;
}

export function TimestampChip({
  seconds,
  citation,
  className,
}: {
  seconds: number;
  citation?: Citation;
  className?: string;
}) {
  const player = usePlayerOptional();
  const { t } = useI18n();
  const label = formatTs(seconds);
  const visual = citation?.source === "visual";
  const preview = useMemo(
    () => citation?.preview || previewFromSegments(player?.segments ?? [], seconds),
    [citation, player?.segments, seconds],
  );

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          data-ts={seconds}
          onClick={() => player?.seekTo(seconds)}
          aria-label={`${visual ? t("chat.onScreen") + " · " : ""}Jump to ${label}`}
          className={cn(
            "tabular mx-0.5 inline-flex translate-y-[-1px] items-center gap-1 rounded-md px-1.5 py-px align-baseline font-mono text-[0.78em] font-medium",
            "transition-colors focus-visible:outline-2",
            visual
              ? "bg-visual-soft text-visual hover:bg-visual hover:text-white"
              : "bg-accent-soft text-accent-text hover:bg-accent hover:text-accent-fg",
            className,
          )}
        >
          {visual ? (
            <ImageIcon className="size-3" aria-hidden />
          ) : (
            <Play className="size-2.5 fill-current" aria-hidden />
          )}
          {label}
        </button>
      </TooltipTrigger>
      {preview && (
        <TooltipContent side="top" className="w-72">
          <span className="text-fg-subtle mb-1.5 flex items-center gap-1.5 font-mono text-[11px]">
            {visual ? `🖼 ${t("chat.onScreen")}` : label}
          </span>
          <span className="text-fg-muted block leading-relaxed">“{preview}”</span>
        </TooltipContent>
      )}
    </Tooltip>
  );
}
