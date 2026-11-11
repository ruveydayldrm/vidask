"use client";

import { ExternalLink } from "lucide-react";
import { useEffect, useRef } from "react";

import { useI18n } from "@/lib/i18n";

import { usePlayer, youtubeUrlAt, type YTPlayerLike } from "./player-context";

declare global {
  interface Window {
    YT?: {
      Player: new (
        el: HTMLElement,
        opts: {
          videoId: string;
          host?: string;
          playerVars?: Record<string, number | string>;
          events?: {
            onReady?: (e: { target: YTPlayerLike }) => void;
            onStateChange?: (e: { data: number; target: YTPlayerLike }) => void;
            onError?: (e: { data: number }) => void;
          };
        },
      ) => YTPlayerLike & { destroy(): void };
    };
    onYouTubeIframeAPIReady?: () => void;
  }
}

let apiPromise: Promise<void> | null = null;

function loadYouTubeApi(): Promise<void> {
  if (typeof window === "undefined") return Promise.resolve();
  if (window.YT?.Player) return Promise.resolve();
  if (apiPromise) return apiPromise;
  apiPromise = new Promise((resolve) => {
    const prev = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => {
      prev?.();
      resolve();
    };
    const tag = document.createElement("script");
    tag.src = "https://www.youtube.com/iframe_api";
    tag.async = true;
    document.head.appendChild(tag);
  });
  return apiPromise;
}

/** IFrame API error codes meaning "the owner does not allow playback in embeds". */
const EMBED_BLOCKED = new Set([101, 150, 153]);

export function YouTubePlayer({ videoId, title }: { videoId: string; title: string }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const { attach, setTime, setPlaying, embedBlocked, setEmbedBlocked } = usePlayer();
  const { t } = useI18n();

  useEffect(() => {
    let player: (YTPlayerLike & { destroy(): void }) | null = null;
    let timer: ReturnType<typeof setInterval> | undefined;
    let cancelled = false;
    const host = hostRef.current;

    loadYouTubeApi().then(() => {
      if (cancelled || !host || !window.YT) return;
      const mount = document.createElement("div");
      host.appendChild(mount);
      player = new window.YT.Player(mount, {
        videoId,
        host: "https://www.youtube-nocookie.com",
        playerVars: { rel: 0, modestbranding: 1, playsinline: 1, enablejsapi: 1 },
        events: {
          onReady: (e) => {
            attach(e.target);
            const iframe = host.querySelector("iframe");
            iframe?.setAttribute("title", title);
          },
          onStateChange: (e) => setPlaying(e.data === 1),
          onError: (e) => {
            if (EMBED_BLOCKED.has(e.data)) setEmbedBlocked(true);
          },
        },
      });
      timer = setInterval(() => {
        try {
          if (player && typeof player.getCurrentTime === "function")
            setTime(player.getCurrentTime());
        } catch {
          /* player not ready */
        }
      }, 250);
    });

    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
      attach(null);
      try {
        player?.destroy();
      } catch {
        /* already gone */
      }
      if (host) host.innerHTML = "";
    };
  }, [videoId, title, attach, setTime, setPlaying, setEmbedBlocked]);

  return (
    <div className="shadow-card ring-border relative aspect-video w-full overflow-hidden rounded-xl bg-black ring-1">
      <div ref={hostRef} className="absolute inset-0 [&_iframe]:size-full" />
      {embedBlocked && (
        <div
          role="status"
          className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-[radial-gradient(ellipse_at_center,oklch(0.25_0.02_40),oklch(0.12_0_0))] px-6 text-center text-white"
        >
          <span className="grid size-11 place-items-center rounded-2xl bg-white/10">
            <ExternalLink className="size-5" aria-hidden />
          </span>
          <p className="text-base font-semibold tracking-tight">{t("player.blockedTitle")}</p>
          <p className="max-w-md text-sm leading-relaxed text-white/70">
            {t("player.blockedBody")}
          </p>
          <a
            href={youtubeUrlAt(videoId, 0)}
            target="_blank"
            rel="noreferrer"
            className="mt-1 inline-flex items-center gap-2 rounded-full bg-white px-4 py-2 text-sm font-medium text-black hover:bg-white/90"
          >
            {t("player.openYoutube")} <ExternalLink className="size-3.5" aria-hidden />
          </a>
        </div>
      )}
    </div>
  );
}
