"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  Check,
  CircleDashed,
  FileText,
  Film,
  ImageIcon,
  Layers,
  Loader2,
  Minus,
  Sparkles,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { useI18n, type TKey } from "@/lib/i18n";
import { formatTs } from "@/lib/time";
import type { Job, Stage, VideoMeta } from "@/lib/types";
import { cn } from "@/lib/utils";

const STAGE_ICON: Record<Stage, React.ComponentType<{ className?: string }>> = {
  metadata: Film,
  transcript: FileText,
  vision: ImageIcon,
  indexing: Layers,
  insights: Sparkles,
};

export function ProcessingView({
  jobId,
  meta,
  onDone,
  onFailed,
}: {
  jobId: string;
  meta: VideoMeta;
  onDone: () => void;
  onFailed: (job: Job) => void;
}) {
  const { t } = useI18n();
  const [job, setJob] = useState<Job | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [tip, setTip] = useState(0);

  useEffect(() => {
    const started = Date.now();
    const a = setInterval(() => setElapsed((Date.now() - started) / 1000), 1000);
    const b = setInterval(() => setTip((x) => (x + 1) % 5), 6000);
    return () => {
      clearInterval(a);
      clearInterval(b);
    };
  }, []);

  useEffect(() => {
    let closed = false;
    let poll: ReturnType<typeof setInterval> | undefined;
    const handle = (j: Job) => {
      setJob(j);
      // The video is searchable once insights start; those finish in the background.
      const chatReady = j.stages.some((s) => s.stage === "insights" && s.status === "running");
      if (closed) return;
      if (j.status === "ready" || chatReady) {
        closed = true;
        setTimeout(onDone, 500);
      } else if (j.status === "failed") {
        closed = true;
        onFailed(j);
      }
    };
    const es = new EventSource(api.jobEventsUrl(jobId));
    es.addEventListener("progress", (e) => handle(JSON.parse((e as MessageEvent).data)));
    es.addEventListener("end", () => es.close());
    es.onerror = () => {
      es.close();
      if (closed || poll) return;
      // Fallback to polling if the stream drops (proxies, sleep, etc.)
      poll = setInterval(
        () =>
          api
            .job(jobId)
            .then(handle)
            .catch(() => undefined),
        1500,
      );
    };
    return () => {
      closed = true;
      es.close();
      if (poll) clearInterval(poll);
    };
  }, [jobId, onDone, onFailed]);

  const pct = Math.round((job?.progress ?? 0) * 100);

  return (
    <div className="mx-auto flex min-h-[calc(100dvh-3.5rem)] max-w-2xl flex-col justify-center px-4 py-12">
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="border-border bg-surface shadow-card rounded-3xl border p-5 sm:p-7"
      >
        <div className="flex items-center gap-4">
          <div className="bg-surface-2 relative aspect-video w-36 shrink-0 overflow-hidden rounded-xl sm:w-44">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={meta.thumbnail || `https://i.ytimg.com/vi/${meta.video_id}/hqdefault.jpg`}
              alt=""
              className="size-full object-cover"
            />
            <div className="absolute inset-0 bg-black/20" />
            <div
              className="animate-scan via-accent/70 absolute inset-x-0 top-0 h-[10%] bg-gradient-to-b from-transparent to-transparent blur-[1px]"
              aria-hidden
            />
          </div>
          <div className="min-w-0">
            <p className="text-accent-text text-xs font-medium tracking-wide uppercase">
              {t("processing.title")}
            </p>
            <h1 className="mt-1 line-clamp-2 leading-snug font-semibold tracking-tight">
              {meta.title || meta.video_id}
            </h1>
            <p className="text-fg-muted mt-0.5 truncate text-sm">{meta.channel}</p>
          </div>
        </div>

        <div className="mt-6">
          <div className="mb-2 flex items-baseline justify-between text-xs">
            <span className="tabular font-mono text-2xl font-semibold tracking-tight">{pct}%</span>
            <span className="text-fg-subtle tabular font-mono">
              {t("processing.elapsed")} {formatTs(elapsed)}
            </span>
          </div>
          <div
            className="bg-surface-2 h-1.5 overflow-hidden rounded-full"
            role="progressbar"
            aria-valuenow={pct}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <motion.div
              className="bg-accent h-full rounded-full"
              animate={{ width: `${pct}%` }}
              transition={{ ease: "easeOut", duration: 0.5 }}
            />
          </div>
        </div>

        <ol className="mt-6 space-y-1">
          {(job?.stages ?? DEFAULT_STAGES).map((s) => {
            const Icon = STAGE_ICON[s.stage];
            const running = s.status === "running";
            return (
              <li
                key={s.stage}
                className={cn(
                  "flex items-center gap-3 rounded-xl px-3 py-2.5 transition-colors",
                  running && "bg-surface-2",
                  (s.status === "pending" || s.status === "skipped") && "opacity-55",
                )}
              >
                <span className="border-border bg-surface text-fg-muted grid size-8 shrink-0 place-items-center rounded-lg border">
                  <Icon className="size-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{t(`stage.${s.stage}` as TKey)}</p>
                  <AnimatePresence mode="wait">
                    <motion.p
                      key={s.message}
                      initial={{ opacity: 0, y: 3 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      className="text-fg-muted truncate text-xs"
                    >
                      {s.status === "skipped" ? t("stage.skipped") : s.message || " "}
                    </motion.p>
                  </AnimatePresence>
                </div>
                {running && s.progress > 0 && (
                  <span className="text-fg-subtle tabular font-mono text-xs">
                    {Math.round(s.progress * 100)}%
                  </span>
                )}
                <StatusIcon status={s.status} />
              </li>
            );
          })}
        </ol>
      </motion.div>

      <div className="text-fg-muted mt-6 h-10 text-center text-sm" aria-live="polite">
        <AnimatePresence mode="wait">
          <motion.p
            key={tip}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
          >
            <span className="mr-1.5">💡</span>
            {t(`tips.${tip}` as TKey)}
          </motion.p>
        </AnimatePresence>
      </div>
      <p className="text-fg-subtle text-center text-xs">{t("processing.subtitle")}</p>
    </div>
  );
}

const DEFAULT_STAGES: Job["stages"] = (
  ["metadata", "transcript", "vision", "indexing", "insights"] as Stage[]
).map((stage) => ({
  stage,
  status: "pending",
  progress: 0,
  message: "",
}));

function StatusIcon({ status }: { status: Job["stages"][number]["status"] }) {
  const base = "size-5 shrink-0";
  if (status === "done")
    return (
      <motion.span
        initial={{ scale: 0.4 }}
        animate={{ scale: 1 }}
        className="bg-success grid size-5 place-items-center rounded-full text-white"
      >
        <Check className="size-3" strokeWidth={3} />
      </motion.span>
    );
  if (status === "running") return <Loader2 className={cn(base, "text-accent animate-spin")} />;
  if (status === "failed") return <X className={cn(base, "text-danger")} />;
  if (status === "skipped") return <Minus className={cn(base, "text-fg-subtle")} />;
  return <CircleDashed className={cn(base, "text-fg-subtle")} />;
}
