import { fireEvent, render, screen } from "@testing-library/react";
import { useEffect } from "react";

import { TooltipProvider } from "@/components/ui/tooltip";
import { I18nProvider } from "@/lib/i18n";
import type { ChatMessage } from "@/lib/types";

import { AnswerMarkdown } from "./answer-markdown";
import { ChatPanel } from "./chat-panel";
import { PlayerProvider, usePlayer, type YTPlayerLike } from "./player-context";
import { previewFromSegments } from "./timestamp-chip";
import type { ChatState } from "./use-chat";

function fakePlayer() {
  const calls: number[] = [];
  const player: YTPlayerLike = {
    seekTo: (t) => calls.push(t),
    playVideo: () => {},
    pauseVideo: () => {},
    getCurrentTime: () => 0,
    getPlayerState: () => 2,
  };
  return { player, calls };
}

function Attach({ player }: { player: YTPlayerLike }) {
  const { attach } = usePlayer();
  useEffect(() => attach(player), [attach, player]);
  return null;
}

function wrap(ui: React.ReactNode, player?: YTPlayerLike) {
  return render(
    <I18nProvider initial="en">
      <TooltipProvider>
        <PlayerProvider>
          {player && <Attach player={player} />}
          {ui}
        </PlayerProvider>
      </TooltipProvider>
    </I18nProvider>,
  );
}

describe("AnswerMarkdown", () => {
  it("renders timestamps as chips that seek the embedded player", () => {
    const { player, calls } = fakePlayer();
    wrap(<AnswerMarkdown content={"A decorator wraps a function [01:05]."} />, player);
    const chip = screen.getByRole("button", { name: /jump to 01:05/i });
    fireEvent.click(chip);
    expect(calls).toEqual([65]);
    expect(document.querySelector("a[href^='#t=']")).toBeNull();
  });

  it("opens YouTube at the cited second when embedding is blocked", () => {
    const open = vi.spyOn(window, "open").mockReturnValue(null);
    function Block() {
      const { setEmbedBlocked } = usePlayer();
      useEffect(() => setEmbedBlocked(true), [setEmbedBlocked]);
      return null;
    }
    render(
      <I18nProvider initial="en">
        <TooltipProvider>
          <PlayerProvider videoId="abc123def45">
            <Block />
            <AnswerMarkdown content={"Explained here [01:05]."} />
          </PlayerProvider>
        </TooltipProvider>
      </I18nProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: /jump to 01:05/i }));
    expect(open).toHaveBeenCalledWith(
      "https://www.youtube.com/watch?v=abc123def45&t=65s",
      "_blank",
      "noopener",
    );
    open.mockRestore();
  });

  it("marks on-screen citations", () => {
    wrap(
      <AnswerMarkdown
        content="See the slide [02:00]."
        citations={[
          {
            label: "02:00",
            seconds: 120,
            chunk_start: 120,
            chunk_end: 140,
            source: "visual",
            preview: "def foo()",
          },
        ]}
      />,
    );
    expect(screen.getByRole("button", { name: /shown on screen/i })).toBeInTheDocument();
  });

  it("renders code blocks", () => {
    wrap(<AnswerMarkdown content={"```python\nprint('hi')\n```"} />);
    expect(document.querySelector("pre code")).not.toBeNull();
  });
});

describe("ChatPanel", () => {
  const baseChat = (messages: ChatMessage[] = []): ChatState => ({
    messages,
    busy: false,
    send: vi.fn(),
    stop: vi.fn(),
    reset: vi.fn(),
  });

  it("shows suggested questions and sends on click", () => {
    const chat = baseChat();
    wrap(<ChatPanel chat={chat} suggestions={["What is a decorator?"]} />);
    fireEvent.click(screen.getByRole("button", { name: "What is a decorator?" }));
    expect(chat.send).toHaveBeenCalledWith("What is a decorator?");
  });

  it("submits on Enter and shows abstention clearly", () => {
    const chat = baseChat([
      { id: "1", role: "user", content: "Quantum?" },
      {
        id: "2",
        role: "assistant",
        content: "This topic isn't covered in the video.",
        status: "done",
        result: {
          answer: "This topic isn't covered in the video.",
          citations: [],
          abstained: true,
          strategy: "full",
          removed_citations: [],
          latency_ms: 900,
        },
      },
    ]);
    wrap(<ChatPanel chat={chat} suggestions={[]} />);
    expect(screen.getByText("Not covered in the video")).toBeInTheDocument();
    const box = screen.getByLabelText(/ask a question/i);
    fireEvent.change(box, { target: { value: "Next question" } });
    fireEvent.keyDown(box, { key: "Enter" });
    expect(chat.send).toHaveBeenCalledWith("Next question");
  });
});

describe("previewFromSegments", () => {
  it("joins text from the timestamp onward", () => {
    const segs = [
      { start: 0, end: 5, text: "intro" },
      { start: 5, end: 10, text: "decorators wrap" },
      { start: 10, end: 15, text: "functions" },
    ];
    expect(previewFromSegments(segs, 6)).toBe("decorators wrap functions");
  });
});
