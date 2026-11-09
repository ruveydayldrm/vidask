"use client";

import { Check, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { SettingsPayload } from "@/lib/types";
import { cn } from "@/lib/utils";

type Current = SettingsPayload["current"];
const PROVIDERS = ["ollama", "groq", "gemini"] as const;

export function SettingsDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const { t } = useI18n();
  const [data, setData] = useState<SettingsPayload | null>(null);
  const [draft, setDraft] = useState<Current | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!open) return;
    setSaved(false);
    setError(null);
    api
      .settings()
      .then((d) => {
        setData(d);
        setDraft(d.current);
      })
      .catch((e: ApiError) => setError(e.code === "network_error" ? t("error.network") : e.message));
  }, [open, t]);

  const save = async () => {
    if (!draft) return;
    setSaving(true);
    try {
      const d = await api.updateSettings({
        llm_provider: draft.llm_provider,
        llm_model: draft.llm_model,
        vision_enabled: draft.vision_enabled,
        reranker_enabled: draft.reranker_enabled,
      });
      setData(d);
      setDraft(d.current);
      setSaved(true);
      setTimeout(() => onOpenChange(false), 600);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const models = draft ? (data?.providers[draft.llm_provider]?.models ?? []) : [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={t("settings.title")}>
        {error && (
          <p role="alert" className="mb-4 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">
            {error}
          </p>
        )}
        {!draft || !data ? (
          !error && (
            <div className="space-y-3" aria-busy>
              <div className="skeleton h-9 rounded-lg" />
              <div className="skeleton h-9 rounded-lg" />
              <div className="skeleton h-14 rounded-lg" />
            </div>
          )
        ) : (
          <div className="space-y-5">
            <fieldset>
              <legend className="mb-2 text-xs font-medium text-fg-muted">{t("settings.provider")}</legend>
              <div className="grid grid-cols-3 gap-1 rounded-xl bg-surface-2 p-1" role="radiogroup">
                {PROVIDERS.map((p) => {
                  const available = data.providers[p]?.available ?? false;
                  const active = draft.llm_provider === p;
                  return (
                    <button
                      key={p}
                      role="radio"
                      aria-checked={active}
                      disabled={!available}
                      title={available ? undefined : t("settings.noKey")}
                      onClick={() =>
                        setDraft({
                          ...draft,
                          llm_provider: p,
                          llm_model:
                            p === draft.llm_provider
                              ? draft.llm_model
                              : (data.providers[p]?.models[0] ?? draft.llm_model),
                        })
                      }
                      className={cn(
                        "h-8 rounded-lg text-sm font-medium capitalize transition-colors",
                        active ? "bg-surface text-fg shadow-sm" : "text-fg-muted hover:text-fg",
                        !available && "cursor-not-allowed opacity-40",
                      )}
                    >
                      {p}
                    </button>
                  );
                })}
              </div>
            </fieldset>

            <label className="block">
              <span className="mb-2 block text-xs font-medium text-fg-muted">{t("settings.model")}</span>
              {models.length > 0 ? (
                <select
                  value={draft.llm_model}
                  onChange={(e) => setDraft({ ...draft, llm_model: e.target.value })}
                  className="h-9 w-full rounded-lg border border-border bg-surface px-3 font-mono text-sm"
                >
                  {!models.includes(draft.llm_model) && <option value={draft.llm_model}>{draft.llm_model}</option>}
                  {models.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  value={draft.llm_model}
                  onChange={(e) => setDraft({ ...draft, llm_model: e.target.value })}
                  className="h-9 w-full rounded-lg border border-border bg-surface px-3 font-mono text-sm"
                />
              )}
            </label>

            <ToggleRow
              label={t("settings.vision")}
              hint={t("settings.visionHint")}
              checked={draft.vision_enabled}
              onChange={(v) => setDraft({ ...draft, vision_enabled: v })}
            />
            <ToggleRow
              label={t("settings.reranker")}
              hint={t("settings.rerankerHint")}
              checked={draft.reranker_enabled}
              onChange={(v) => setDraft({ ...draft, reranker_enabled: v })}
            />

            <div className="rounded-xl border border-border bg-bg-subtle p-3">
              <p className="mb-2 text-xs font-medium text-fg-muted">{t("settings.models")}</p>
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 font-mono text-[11.5px]">
                <dt className="text-fg-subtle">embed</dt>
                <dd className="truncate">{draft.embedding_model}</dd>
                <dt className="text-fg-subtle">rerank</dt>
                <dd className="truncate">{draft.reranker_model}</dd>
                <dt className="text-fg-subtle">whisper</dt>
                <dd>{draft.whisper_model}</dd>
                <dt className="text-fg-subtle">ctx</dt>
                <dd>{draft.context_window.toLocaleString()} tokens</dd>
              </dl>
            </div>

            <div className="flex justify-end">
              <Button onClick={save} disabled={saving}>
                {saving ? <Loader2 className="animate-spin" /> : saved ? <Check /> : null}
                {saved ? t("settings.saved") : t("settings.save")}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function ToggleRow({
  label,
  hint,
  checked,
  onChange,
}: {
  label: string;
  hint: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-start justify-between gap-4">
      <span>
        <span className="block text-sm font-medium">{label}</span>
        <span className="mt-0.5 block text-xs leading-relaxed text-fg-muted">{hint}</span>
      </span>
      <Switch checked={checked} onCheckedChange={onChange} className="mt-0.5" aria-label={label} />
    </label>
  );
}
