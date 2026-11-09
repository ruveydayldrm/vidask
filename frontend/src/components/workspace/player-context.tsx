"use client";

import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";

import type { Segment } from "@/lib/types";

/** Minimal surface of the YouTube IFrame player we rely on. */
export interface YTPlayerLike {
  seekTo(seconds: number, allowSeekAhead: boolean): void;
  playVideo(): void;
  pauseVideo(): void;
  getCurrentTime(): number;
  getPlayerState(): number;
}

interface PlayerContextValue {
  currentTime: number;
  playing: boolean;
  ready: boolean;
  /** Bumped on every explicit jump so the transcript can scroll + flash the line. */
  jump: { t: number; nonce: number } | null;
  segments: Segment[];
  seekTo: (t: number, opts?: { play?: boolean }) => void;
  togglePlay: () => void;
  nudge: (delta: number) => void;
  /** wiring used by <YouTubePlayer> */
  attach: (p: YTPlayerLike | null) => void;
  setTime: (t: number) => void;
  setPlaying: (p: boolean) => void;
  setSegments: (s: Segment[]) => void;
}

const PlayerContext = createContext<PlayerContextValue | null>(null);

export function PlayerProvider({ children }: { children: React.ReactNode }) {
  const playerRef = useRef<YTPlayerLike | null>(null);
  const [currentTime, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [ready, setReady] = useState(false);
  const [jump, setJump] = useState<PlayerContextValue["jump"]>(null);
  const [segments, setSegments] = useState<Segment[]>([]);

  const attach = useCallback((p: YTPlayerLike | null) => {
    playerRef.current = p;
    setReady(Boolean(p));
  }, []);

  const seekTo = useCallback((t: number, opts: { play?: boolean } = { play: true }) => {
    const p = playerRef.current;
    setJump({ t, nonce: Date.now() });
    setTime(t);
    if (!p) return;
    p.seekTo(Math.max(0, t), true);
    if (opts.play !== false) p.playVideo();
  }, []);

  const togglePlay = useCallback(() => {
    const p = playerRef.current;
    if (!p) return;
    if (p.getPlayerState() === 1) p.pauseVideo();
    else p.playVideo();
  }, []);

  const nudge = useCallback((delta: number) => {
    const p = playerRef.current;
    if (!p) return;
    const t = Math.max(0, p.getCurrentTime() + delta);
    p.seekTo(t, true);
    setTime(t);
  }, []);

  const value = useMemo(
    () => ({
      currentTime,
      playing,
      ready,
      jump,
      segments,
      seekTo,
      togglePlay,
      nudge,
      attach,
      setTime,
      setPlaying,
      setSegments,
    }),
    [currentTime, playing, ready, jump, segments, seekTo, togglePlay, nudge, attach],
  );
  return <PlayerContext.Provider value={value}>{children}</PlayerContext.Provider>;
}

export function usePlayer(): PlayerContextValue {
  const ctx = useContext(PlayerContext);
  if (!ctx) throw new Error("usePlayer must be used inside <PlayerProvider>");
  return ctx;
}

/** For components rendered both inside and outside a workspace (e.g. tests). */
export function usePlayerOptional(): PlayerContextValue | null {
  return useContext(PlayerContext);
}
