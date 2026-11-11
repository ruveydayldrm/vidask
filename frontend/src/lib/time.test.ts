import { activeIndex, formatTs, linkifyTimestamps, parseTs } from "./time";
import { looksLikeYouTube } from "./utils";
import { parseEventBlock } from "./api";

describe("time helpers", () => {
  it("formats and parses timestamps", () => {
    expect(formatTs(0)).toBe("00:00");
    expect(formatTs(754.9)).toBe("12:34");
    expect(formatTs(3723)).toBe("1:02:03");
    expect(parseTs("12:34")).toBe(754);
    expect(parseTs("1:02:03")).toBe(3723);
    expect(parseTs("abc")).toBeNull();
  });

  it("linkifies citations but leaves code alone", () => {
    const md = "Wraps [01:05]. Code: `arr[1:05]`\n```py\nx[0:30]\n```\nAnd [1:00:00].";
    const out = linkifyTimestamps(md);
    expect(out).toContain("[01:05](#t=65)");
    expect(out).toContain("[1:00:00](#t=3600)");
    expect(out).toContain("`arr[1:05]`");
    expect(out).toContain("x[0:30]");
  });

  it("finds the active segment", () => {
    const segs = [{ start: 0 }, { start: 5 }, { start: 10 }];
    expect(activeIndex(segs, -1)).toBe(-1);
    expect(activeIndex(segs, 0)).toBe(0);
    expect(activeIndex(segs, 7)).toBe(1);
    expect(activeIndex(segs, 99)).toBe(2);
  });
});

describe("url + sse helpers", () => {
  it("recognises YouTube links", () => {
    expect(looksLikeYouTube("https://youtu.be/dQw4w9WgXcQ?t=3")).toBe(true);
    expect(looksLikeYouTube("https://www.youtube.com/shorts/dQw4w9WgXcQ")).toBe(true);
    expect(looksLikeYouTube("dQw4w9WgXcQ")).toBe(true);
    expect(looksLikeYouTube("https://vimeo.com/1")).toBe(false);
  });

  it("parses SSE blocks", () => {
    expect(parseEventBlock('event: token\ndata: {"text":"hi"}')).toEqual({
      event: "token",
      data: '{"text":"hi"}',
    });
    expect(parseEventBlock(": ping")).toBeNull();
  });
});
