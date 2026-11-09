"use client";

import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Clock, Link2, Loader2, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Kbd, Skeleton } from "@/components/ui/misc";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { formatDuration } from "@/lib/time";
import type { VideoMeta } from "@/lib/types";
import { cn, isTypingTarget, looksLikeYouTube } from "@/lib/utils";

export function UrlHero() {
  const { t } = useI18n();
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [url, setUrl] = useState("");
  const [preview, setPreview] = useState<VideoMeta | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "/" && !isTypingTarget(e.target)) {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    setError(null);
    const value = url.trim();
    if (!value) {
      setPreview(null);
      return;
    }
    if (!looksLikeYouTube(value)) {
      setPreview(null);
      return;
    }
    const ctrl = new AbortController();
    const timer = setTimeout(() => {
      setLoadingPreview(true);
      api
        .preview(value, ctrl.signal)
        .then(setPreview)
        .catch((e: ApiError) => {
          if (e.name === "AbortError") return;
          setPreview(null);
          setError(e.code === "network_error" ? t("error.network") : e.message);
        })
        .finally(() => setLoadingPreview(false));
    }, 300);
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
  }, [url, t]);

  const submit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    const value = url.trim();
    if (!value) return inputRef.current?.focus();
    if (!looksLikeYouTube(value)) {
      setError(t("home.invalid"));
      return;
    }
    setSubmitting(true);
    try {
      const res = await api.process(value);
      router.push(`/v/${res.video_id}${res.job_id ? `?job=${res.job_id}` : ""}`);
    } catch (err) {
      const e2 = err as ApiError;
      setError(e2.code === "network_error" ? t("error.network") : e2.code === "invalid_url" ? t("home.invalid") : e2.message);
      setSubmitting(false);
    }
  };

  const showInvalid = url.trim().length > 8 && !looksLikeYouTube(url);

  return (
    <form onSubmit={submit} className="w-full" aria-label="Analyze a YouTube video">
      <div
        className={cn(
          "group relative rounded-2xl border bg-surface p-2 shadow-card transition-[border-color,box-shadow]",
          "focus-within:border-border-strong focus-within:shadow-[0_0_0_4px_var(--accent-soft),var(--shadow)]",
          error || showInvalid ? "border-danger/50" : "border-border",
        )}
      >
        <div className="flex items-center gap-2">
          <Link2 className="ml-3 size-5 shrink-0 text-fg-subtle" aria-hidden />
          <label htmlFor="url" className="sr-only">
            {t("home.placeholder")}
          </label>
          <input
            id="url"
            ref={inputRef}
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder={t("home.placeholder")}
            autoComplete="off"
            spellCheck={false}
            inputMode="url"
            autoFocus
            className="h-12 min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-fg-subtle focus-visible:outline-none"
            aria-invalid={Boolean(error || showInvalid)}
            aria-describedby="url-help"
          />
          {url && (
            <button
              type="button"
              onClick={() => {
                setUrl("");
                inputRef.current?.focus();
              }}
              className="rounded-md p-1.5 text-fg-subtle hover:bg-surface-2 hover:text-fg"
              aria-label="Clear"
            >
              <X className="size-4" />
            </button>
          )}
          <Button type="submit" size="lg" disabled={submitting} className="rounded-xl">
            {submitting ? <Loader2 className="animate-spin" /> : null}
            <span className="hidden sm:inline">{submitting ? t("home.analyzing") : t("home.analyze")}</span>
            {!submitting && <ArrowRight />}
          </Button>
        </div>

        <AnimatePresence initial={false}>
          {(preview || loadingPreview) && (
            <motion.div
              key="preview"
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.28, ease: [0.2, 0.8, 0.2, 1] }}
              className="overflow-hidden"
            >
              <div className="mt-2 flex items-center gap-4 rounded-xl border border-border bg-bg-subtle p-2.5">
                {preview ? (
                  <>
                    <motion.div
                      initial={{ scale: 0.94, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      className="relative aspect-video w-32 shrink-0 overflow-hidden rounded-lg bg-surface-2 sm:w-40"
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={preview.thumbnail} alt="" className="size-full object-cover" />
                      {preview.duration > 0 && (
                        <span className="absolute right-1 bottom-1 rounded bg-black/75 px-1 py-px font-mono text-[10.5px] text-white">
                          {formatDuration(preview.duration)}
                        </span>
                      )}
                    </motion.div>
                    <div className="min-w-0 flex-1 text-left">
                      <p className="line-clamp-2 text-sm leading-snug font-medium">{preview.title}</p>
                      <p className="mt-1 flex items-center gap-2 text-xs text-fg-muted">
                        <span className="truncate">{preview.channel}</span>
                        {preview.duration > 0 && (
                          <span className="flex items-center gap-1 tabular">
                            <Clock className="size-3" aria-hidden />
                            {formatDuration(preview.duration)}
                          </span>
                        )}
                      </p>
                    </div>
                  </>
                ) : (
                  <>
                    <Skeleton className="aspect-video w-32 rounded-lg sm:w-40" />
                    <div className="flex-1 space-y-2">
                      <Skeleton className="h-4 w-4/5" />
                      <Skeleton className="h-3 w-1/3" />
                    </div>
                  </>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      <p id="url-help" className="mt-3 min-h-5 text-center text-xs text-fg-subtle" aria-live="polite">
        {error ? (
          <span className="text-danger">{error}</span>
        ) : showInvalid ? (
          <span className="text-danger">{t("home.invalid")}</span>
        ) : (
          <span className="hidden items-center gap-1.5 sm:inline-flex">
            <Kbd>/</Kbd> · <Kbd>Enter</Kbd>
          </span>
        )}
      </p>
    </form>
  );
}
