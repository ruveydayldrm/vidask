"use client";

import { motion } from "framer-motion";
import { AlignLeft, ExternalLink, FileText, ListOrdered, MessageCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Skeleton } from "@/components/ui/misc";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { formatDuration } from "@/lib/time";
import type { TranscriptData, VideoRecord } from "@/lib/types";
import { isTypingTarget } from "@/lib/utils";

import { ChatPanel, type ChatPanelHandle } from "./chat-panel";
import { PlayerProvider, usePlayer } from "./player-context";
import { ChaptersPanel, SummaryPanel } from "./summary-panels";
import { TranscriptPanel } from "./transcript-panel";
import { useChat } from "./use-chat";
import { YouTubePlayer } from "./youtube-player";

function useIsDesktop() {
  const [desktop, setDesktop] = useState(true);
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 1024px)");
    const update = () => setDesktop(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);
  return desktop;
}

export function Workspace({ record }: { record: VideoRecord }) {
  return (
    <PlayerProvider videoId={record.meta.video_id}>
      <WorkspaceInner record={record} />
    </PlayerProvider>
  );
}

function WorkspaceInner({ record }: { record: VideoRecord }) {
  const { t, lang } = useI18n();
  const desktop = useIsDesktop();
  const chat = useChat(record.meta.video_id, lang);
  const chatRef = useRef<ChatPanelHandle>(null);
  const { togglePlay, nudge, setSegments } = usePlayer();
  const [transcript, setTranscript] = useState<TranscriptData | null>(null);
  const [tab, setTab] = useState("summary");

  useEffect(() => {
    api
      .transcript(record.meta.video_id)
      .then((d) => {
        setTranscript(d);
        setSegments(d.segments);
      })
      .catch(() =>
        setTranscript({
          video_id: record.meta.video_id,
          language: null,
          source: "auto_captions",
          segments: [],
          visual: [],
        }),
      );
  }, [record.meta.video_id, setSegments]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (isTypingTarget(e.target) || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "/") {
        e.preventDefault();
        if (!desktop) setTab("chat");
        setTimeout(() => chatRef.current?.focus(), 0);
      } else if (e.key === " " && !(e.target instanceof HTMLButtonElement)) {
        e.preventDefault();
        togglePlay();
      } else if (e.key.toLowerCase() === "j") nudge(-10);
      else if (e.key.toLowerCase() === "l") nudge(10);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [desktop, togglePlay, nudge]);

  // When a timestamp is clicked on mobile, keep the user where they are (player is sticky).
  const suggestions = record.insights?.suggested_questions ?? [];
  const chatPanel = (
    <ChatPanel ref={chatRef} chat={chat} suggestions={suggestions} className="h-full" />
  );

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="mx-auto grid max-w-[1600px] grid-cols-1 lg:h-[calc(100dvh-3.5rem)] lg:grid-cols-[minmax(0,1.2fr)_minmax(380px,0.8fr)]"
    >
      {/* left column */}
      <div className="lg:border-border flex min-h-0 flex-col lg:border-r">
        <div className="bg-bg sticky top-14 z-20 px-0 pt-0 sm:px-6 sm:pt-5 lg:static">
          <YouTubePlayer videoId={record.meta.video_id} title={record.meta.title} />
        </div>
        <div className="px-4 pt-4 sm:px-6">
          <h1 className="text-lg leading-snug font-semibold tracking-tight text-balance">
            {record.meta.title}
          </h1>
          <p className="text-fg-muted mt-1 flex items-center gap-2 text-sm">
            <span className="truncate">{record.meta.channel}</span>
            {record.meta.duration > 0 && (
              <span className="tabular font-mono text-xs">
                · {formatDuration(record.meta.duration)}
              </span>
            )}
            <a
              href={record.meta.url}
              target="_blank"
              rel="noreferrer"
              className="text-fg-subtle hover:text-fg ml-auto inline-flex items-center gap-1 rounded text-xs"
            >
              YouTube <ExternalLink className="size-3" aria-hidden />
            </a>
          </p>
        </div>

        <Tabs
          value={tab}
          onValueChange={setTab}
          className="flex min-h-0 flex-1 flex-col px-4 pt-3 sm:px-6"
        >
          <TabsList className="shrink-0 overflow-x-auto">
            {!desktop && (
              <TabsTrigger value="chat">
                <MessageCircle /> {t("tabs.chat")}
              </TabsTrigger>
            )}
            <TabsTrigger value="summary">
              <AlignLeft /> {t("tabs.summary")}
            </TabsTrigger>
            <TabsTrigger value="chapters">
              <ListOrdered /> {t("tabs.chapters")}
            </TabsTrigger>
            <TabsTrigger value="transcript">
              <FileText /> {t("tabs.transcript")}
            </TabsTrigger>
          </TabsList>
          {!desktop && (
            <TabsContent value="chat" forceMount hidden={tab !== "chat"} className="h-[70dvh]">
              {chatPanel}
            </TabsContent>
          )}
          <TabsContent value="summary" className="min-h-0 flex-1 scrollbar-thin overflow-y-auto">
            <SummaryPanel record={record} />
          </TabsContent>
          <TabsContent value="chapters" className="min-h-0 flex-1 scrollbar-thin overflow-y-auto">
            <ChaptersPanel record={record} />
          </TabsContent>
          <TabsContent
            value="transcript"
            forceMount
            hidden={tab !== "transcript"}
            className="min-h-0 flex-1 max-lg:h-[70dvh]"
          >
            {transcript ? (
              <TranscriptPanel data={transcript} />
            ) : (
              <div className="space-y-3 py-4">
                {Array.from({ length: 8 }).map((_, i) => (
                  <div key={i} className="flex gap-3">
                    <Skeleton className="h-4 w-10" />
                    <Skeleton className="h-4 flex-1" />
                  </div>
                ))}
              </div>
            )}
          </TabsContent>
        </Tabs>
      </div>

      {/* right column */}
      {desktop && <aside className="bg-bg-subtle/50 min-h-0">{chatPanel}</aside>}
    </motion.div>
  );
}
