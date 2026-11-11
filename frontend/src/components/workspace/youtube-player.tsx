"use client";

import { useEffect, useRef } from "react";

import { usePlayer, type YTPlayerLike } from "./player-context";

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

export function YouTubePlayer({ videoId, title }: { videoId: string; title: string }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const { attach, setTime, setPlaying } = usePlayer();

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
  }, [videoId, title, attach, setTime, setPlaying]);

  return (
    <div className="shadow-card ring-border relative aspect-video w-full overflow-hidden rounded-xl bg-black ring-1">
      <div ref={hostRef} className="absolute inset-0 [&_iframe]:size-full" />
    </div>
  );
}
