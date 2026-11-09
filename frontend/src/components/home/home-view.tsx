"use client";

import { motion } from "framer-motion";
import { Cpu, ShieldCheck, Timer } from "lucide-react";
import { useEffect, useState } from "react";

import { UrlHero } from "@/components/home/url-hero";
import { VideoCard, VideoCardSkeleton } from "@/components/home/video-card";
import { api } from "@/lib/api";
import { EXAMPLES } from "@/lib/examples";
import { useI18n } from "@/lib/i18n";
import type { VideoRecord } from "@/lib/types";

export function HomeView() {
  const { t } = useI18n();
  const [recent, setRecent] = useState<VideoRecord[] | null>(null);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    api
      .videos(12)
      .then(setRecent)
      .catch(() => {
        setOffline(true);
        setRecent([]);
      });
  }, []);

  const exampleIds = new Set(EXAMPLES.map((e) => e.video_id));
  const recentOnly = (recent ?? []).filter((r) => !exampleIds.has(r.meta.video_id));
  const known = new Map((recent ?? []).map((r) => [r.meta.video_id, r]));

  return (
    <div className="relative">
      <div className="bg-grid pointer-events-none absolute inset-x-0 top-0 h-[520px] opacity-60" aria-hidden />
      <section className="relative mx-auto max-w-3xl px-4 pt-16 pb-12 sm:pt-24">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.2, 0.8, 0.2, 1] }}
          className="text-center"
        >
          <span className="mb-5 inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-3 py-1 text-xs font-medium text-fg-muted shadow-sm">
            <span className="size-1.5 rounded-full bg-success" aria-hidden />
            {t("home.local")}
          </span>
          <h1 className="text-[clamp(2rem,5.5vw,3.4rem)] leading-[1.05] font-semibold tracking-[-0.035em] text-balance">
            {t("home.title")}
          </h1>
          <p className="mx-auto mt-4 max-w-xl text-[15px] leading-relaxed text-pretty text-fg-muted sm:text-base">
            {t("home.subtitle")}
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, delay: 0.08, ease: [0.2, 0.8, 0.2, 1] }}
          className="mt-10"
        >
          <UrlHero />
        </motion.div>

        {offline && (
          <p role="alert" className="mt-4 text-center text-sm text-danger">
            {t("error.network")}
          </p>
        )}

        <ul className="mt-10 grid grid-cols-1 gap-3 text-sm text-fg-muted sm:grid-cols-3">
          {[
            { icon: Timer, en: "Clickable, verified timestamps", tr: "Doğrulanmış, tıklanabilir zaman damgaları" },
            { icon: ShieldCheck, en: "Says so when the video doesn't", tr: "Videoda yoksa uydurmaz" },
            { icon: Cpu, en: "Local models, GPU optional", tr: "Lokal modeller, GPU isteğe bağlı" },
          ].map(({ icon: Icon, en, tr }) => (
            <li key={en} className="flex items-center justify-center gap-2 sm:justify-start">
              <Icon className="size-4 shrink-0 text-fg-subtle" aria-hidden />
              <FeatureText en={en} tr={tr} />
            </li>
          ))}
        </ul>
      </section>

      <section className="mx-auto max-w-6xl px-4 pb-24 sm:px-6" aria-labelledby="examples-h">
        {EXAMPLES.length > 0 && (
          <>
            <SectionTitle id="examples-h">{t("home.examples")}</SectionTitle>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {EXAMPLES.map((ex, i) => (
                <VideoCard key={ex.video_id} meta={known.get(ex.video_id)?.meta ?? ex} record={known.get(ex.video_id)} index={i} />
              ))}
            </div>
          </>
        )}

        <SectionTitle id="recent-h" className="mt-14">
          {t("home.recent")}
        </SectionTitle>
        {recent === null ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <VideoCardSkeleton key={i} />
            ))}
          </div>
        ) : recentOnly.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border-strong px-6 py-12 text-center text-sm text-fg-subtle">
            {t("home.recentEmpty")}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {recentOnly.map((r, i) => (
              <VideoCard key={r.meta.video_id} meta={r.meta} record={r} index={i} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function FeatureText({ en, tr }: { en: string; tr: string }) {
  const { lang } = useI18n();
  return <span>{lang === "tr" ? tr : en}</span>;
}

function SectionTitle({
  children,
  id,
  className = "",
}: {
  children: React.ReactNode;
  id: string;
  className?: string;
}) {
  return (
    <h2 id={id} className={`mb-4 text-sm font-medium text-fg-muted ${className}`}>
      {children}
    </h2>
  );
}
