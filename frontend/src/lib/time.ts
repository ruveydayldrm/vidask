export function formatTs(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

export function parseTs(label: string): number | null {
  const parts = label.trim().split(":").map(Number);
  if (parts.some((p) => Number.isNaN(p)) || parts.length < 2 || parts.length > 3) return null;
  return parts.length === 2
    ? parts[0]! * 60 + parts[1]!
    : parts[0]! * 3600 + parts[1]! * 60 + parts[2]!;
}

export function formatDuration(seconds: number): string {
  if (!seconds) return "";
  return formatTs(seconds);
}

const TS_RE = /\[((?:\d{1,2}:)?\d{1,2}:\d{2})\]/g;

/**
 * Turn `[12:34]` citations into markdown links `[12:34](#t=754)` so the markdown
 * renderer hands them to <TimestampChip>. Fenced and inline code are left alone.
 */
export function linkifyTimestamps(markdown: string): string {
  const parts = markdown.split(/(```[\s\S]*?(?:```|$)|`[^`\n]*`)/g);
  return parts
    .map((part, i) =>
      i % 2 === 1
        ? part
        : part.replace(TS_RE, (_m, label: string) => {
            const secs = parseTs(label);
            return secs === null ? _m : `[${label}](#t=${secs})`;
          }),
    )
    .join("");
}

/** Index of the segment playing at `t` (binary search over sorted starts). */
export function activeIndex(items: { start: number }[], t: number): number {
  let lo = 0;
  let hi = items.length - 1;
  let ans = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (items[mid]!.start <= t + 0.05) {
      ans = mid;
      lo = mid + 1;
    } else hi = mid - 1;
  }
  return ans;
}
