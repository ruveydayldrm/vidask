"use client";

import { AlertTriangle, ArrowLeft, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/misc";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Job, VideoRecord } from "@/lib/types";

import { ProcessingView } from "./processing-view";
import { Workspace } from "./workspace";

type State =
  | { kind: "loading" }
  | { kind: "processing"; record: VideoRecord; jobId: string }
  | { kind: "ready"; record: VideoRecord }
  | { kind: "error"; message: string; record?: VideoRecord };

export function VideoView({ id, jobParam }: { id: string; jobParam?: string }) {
  const { t } = useI18n();
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback(async () => {
    try {
      const record = await api.video(id);
      if (record.status === "ready") return setState({ kind: "ready", record });
      const jobId = jobParam ?? record.latest_job_id;
      if ((record.status === "processing" || record.status === "pending") && jobId)
        return setState({ kind: "processing", record, jobId });
      setState({ kind: "error", message: record.error ?? t("processing.failed"), record });
    } catch (e) {
      const err = e as ApiError;
      setState({
        kind: "error",
        message:
          err.code === "network_error"
            ? t("error.network")
            : err.status === 404
              ? t("error.notFound")
              : err.message,
      });
    }
  }, [id, jobParam, t]);

  useEffect(() => {
    load();
  }, [load]);

  // Summary/chapters are still being written: refresh the record until they land.
  const pending = state.kind === "ready" && state.record.insights_pending;
  useEffect(() => {
    if (!pending) return;
    const timer = setInterval(async () => {
      try {
        const record = await api.video(id);
        if (!record.insights_pending) setState({ kind: "ready", record });
      } catch {
        // transient; try again on the next tick
      }
    }, 4000);
    return () => clearInterval(timer);
  }, [pending, id]);

  const onFailed = useCallback((job: Job) => {
    setState((s) => ({
      kind: "error",
      message: job.error ?? "",
      record: s.kind === "processing" ? s.record : undefined,
    }));
  }, []);

  const retry = async () => {
    setState({ kind: "loading" });
    try {
      const res = await api.process(id, { force: true });
      const record = await api.video(id);
      if (res.job_id) setState({ kind: "processing", record, jobId: res.job_id });
      else setState({ kind: "ready", record });
    } catch (e) {
      setState({ kind: "error", message: (e as Error).message });
    }
  };

  if (state.kind === "loading") return <WorkspaceSkeleton />;
  if (state.kind === "processing")
    return (
      <ProcessingView
        jobId={state.jobId}
        meta={state.record.meta}
        onDone={load}
        onFailed={onFailed}
      />
    );
  if (state.kind === "ready") return <Workspace record={state.record} />;

  return (
    <div className="mx-auto flex min-h-[calc(100dvh-3.5rem)] max-w-md flex-col items-center justify-center px-4 text-center">
      <div className="bg-danger-soft text-danger mb-5 grid size-12 place-items-center rounded-2xl">
        <AlertTriangle className="size-5" aria-hidden />
      </div>
      <h1 className="text-lg font-semibold tracking-tight">{t("processing.failed")}</h1>
      {state.record?.meta.title && (
        <p className="text-fg-muted mt-1 text-sm font-medium">{state.record.meta.title}</p>
      )}
      <p role="alert" className="text-fg-muted mt-3 text-sm leading-relaxed">
        {state.message}
      </p>
      <div className="mt-6 flex gap-2">
        <Button variant="outline" asChild>
          <Link href="/">
            <ArrowLeft /> {t("processing.home")}
          </Link>
        </Button>
        <Button onClick={retry}>
          <RotateCcw /> {t("processing.retry")}
        </Button>
      </div>
    </div>
  );
}

function WorkspaceSkeleton() {
  return (
    <div
      className="mx-auto grid max-w-[1600px] grid-cols-1 gap-6 p-4 sm:p-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(380px,0.8fr)]"
      aria-busy
    >
      <div className="space-y-4">
        <Skeleton className="aspect-video w-full rounded-xl" />
        <Skeleton className="h-6 w-2/3" />
        <Skeleton className="h-4 w-1/3" />
        <div className="space-y-2 pt-4">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-11/12" />
          <Skeleton className="h-4 w-4/5" />
        </div>
      </div>
      <Skeleton className="hidden h-[70vh] rounded-2xl lg:block" />
    </div>
  );
}
