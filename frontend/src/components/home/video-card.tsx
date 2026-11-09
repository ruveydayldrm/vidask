"use client";

import { motion } from "framer-motion";
import { CheckCircle2, Loader2, Play } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Skeleton } from "@/components/ui/misc";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { formatDuration } from "@/lib/time";
import type { VideoMeta, VideoRecord } from "@/lib/types";

export function VideoCard({
  meta,
  record,
  index = 0,
}: {
  meta: VideoMeta;
  record?: VideoRecord;
  index?: number;
}) {
  const router = useRouter();
  const { t } = useI18n();
  const [busy, setBusy] = useState(false);
  const ready = record?.status === "ready";

  const open = async () => {
    if (ready) return router.push(`/v/${meta.video_id}`);
    setBusy(true);
    try {
      const res = await api.process(meta.url || meta.video_id);
      router.push(`/v/${res.video_id}${res.job_id ? `?job=${res.job_id}` : ""}`);
    } catch {
      setBusy(false);
    }
  };

  return (
    <motion.button
      type="button"
      onClick={open}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.04 * index, duration: 0.3 }}
      whileHover={{ y: -2 }}
      className="group overflow-hidden rounded-2xl border border-border bg-surface text-left shadow-sm transition-shadow hover:shadow-card"
      aria-label={`${t("home.open")}: ${meta.title}`}
    >
      <div className="relative aspect-video overflow-hidden bg-surface-2">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={meta.thumbnail || `https://i.ytimg.com/vi/${meta.video_id}/hqdefault.jpg`}
          alt=""
          loading="lazy"
          className="size-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/50 via-transparent to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
        <span className="absolute top-1/2 left-1/2 grid size-11 -translate-x-1/2 -translate-y-1/2 scale-90 place-items-center rounded-full bg-white/95 text-black opacity-0 shadow-lg transition-all group-hover:scale-100 group-hover:opacity-100">
          {busy ? <Loader2 className="size-5 animate-spin" /> : <Play className="ml-0.5 size-5 fill-current" />}
        </span>
        {meta.duration > 0 && (
          <span className="absolute right-2 bottom-2 rounded-md bg-black/75 px-1.5 py-0.5 font-mono text-[11px] text-white">
            {formatDuration(meta.duration)}
          </span>
        )}
        {ready && (
          <span className="absolute top-2 left-2 inline-flex items-center gap-1 rounded-md bg-black/70 px-1.5 py-0.5 text-[11px] font-medium text-white backdrop-blur">
            <CheckCircle2 className="size-3 text-emerald-400" aria-hidden />
            {meta.language?.toUpperCase() ?? "OK"}
          </span>
        )}
      </div>
      <div className="p-3.5">
        <p className="line-clamp-2 text-sm leading-snug font-medium">{meta.title || meta.video_id}</p>
        <p className="mt-1 truncate text-xs text-fg-muted">{meta.channel}</p>
      </div>
    </motion.button>
  );
}

export function VideoCardSkeleton() {
  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-surface">
      <Skeleton className="aspect-video rounded-none" />
      <div className="space-y-2 p-3.5">
        <Skeleton className="h-4 w-11/12" />
        <Skeleton className="h-3 w-1/3" />
      </div>
    </div>
  );
}
