"use client";

import { memo } from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";

import { linkifyTimestamps } from "@/lib/time";
import type { Citation } from "@/lib/types";

import { TimestampChip } from "./timestamp-chip";

function AnswerMarkdownImpl({ content, citations }: { content: string; citations?: Citation[] }) {
  const byLabel = new Map((citations ?? []).map((c) => [Math.round(c.seconds), c]));
  return (
    <div className="prose-answer">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeHighlight, { detect: true, ignoreMissing: true }]]}
        components={{
          a({ href, children, ...props }) {
            if (href?.startsWith("#t=")) {
              const secs = Number(href.slice(3));
              return <TimestampChip seconds={secs} citation={byLabel.get(Math.round(secs))} />;
            }
            return (
              <a href={href} target="_blank" rel="noreferrer noopener" {...props}>
                {children}
              </a>
            );
          },
        }}
      >
        {linkifyTimestamps(content)}
      </ReactMarkdown>
    </div>
  );
}

export const AnswerMarkdown = memo(AnswerMarkdownImpl);
