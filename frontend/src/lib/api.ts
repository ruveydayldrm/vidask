import type {
  Job,
  ProcessResponse,
  SettingsPayload,
  TranscriptData,
  VideoMeta,
  VideoRecord,
} from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

export class ApiError extends Error {
  constructor(
    message: string,
    public code: string,
    public status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError("Backend is unreachable", "network_error", 0);
  }
  if (!res.ok) {
    let code = "http_error";
    let message = res.statusText;
    try {
      const body = await res.json();
      code = body?.error?.code ?? (res.status === 422 ? "invalid_request" : code);
      message = body?.error?.message ?? JSON.stringify(body?.detail ?? body);
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(message, code, res.status);
  }
  return res.json() as Promise<T>;
}

export const api = {
  preview: (url: string, signal?: AbortSignal) =>
    request<VideoMeta>(`/api/videos/preview?url=${encodeURIComponent(url)}`, { signal }),
  process: (url: string, opts: { force?: boolean; vision?: boolean } = {}) =>
    request<ProcessResponse>("/api/videos", {
      method: "POST",
      body: JSON.stringify({ url, ...opts }),
    }),
  videos: (limit = 12) => request<VideoRecord[]>(`/api/videos?limit=${limit}`),
  video: (id: string) => request<VideoRecord>(`/api/videos/${id}`),
  transcript: (id: string) => request<TranscriptData>(`/api/videos/${id}/transcript`),
  job: (id: string) => request<Job>(`/api/jobs/${id}`),
  settings: () => request<SettingsPayload>("/api/settings"),
  updateSettings: (body: Partial<SettingsPayload["current"]>) =>
    request<SettingsPayload>("/api/settings", { method: "PUT", body: JSON.stringify(body) }),
  jobEventsUrl: (id: string) => `${API_URL}/api/jobs/${id}/events`,
};

export interface SSEEvent {
  event: string;
  data: string;
}

/** Parse a text/event-stream body incrementally (works for POST, unlike EventSource). */
export async function* readSSE(body: ReadableStream<Uint8Array>): AsyncGenerator<SSEEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n?/g, "\n");
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const parsed = parseEventBlock(raw);
      if (parsed) yield parsed;
    }
  }
  const tail = parseEventBlock(buffer);
  if (tail) yield tail;
}

export function parseEventBlock(raw: string): SSEEvent | null {
  let event = "message";
  const data: string[] = [];
  for (const line of raw.split("\n")) {
    if (line.startsWith(":")) continue;
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
  }
  return data.length ? { event, data: data.join("\n") } : null;
}

export async function streamChat(
  videoId: string,
  body: { question: string; history: { role: string; content: string }[]; lang: string },
  signal: AbortSignal,
): Promise<AsyncGenerator<SSEEvent>> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/videos/${videoId}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(body),
      signal,
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError("Backend is unreachable", "network_error", 0);
  }
  if (!res.ok || !res.body) {
    let message = res.statusText;
    let code = "http_error";
    try {
      const b = await res.json();
      message = b?.error?.message ?? message;
      code = b?.error?.code ?? code;
    } catch {
      /* ignore */
    }
    throw new ApiError(message, code, res.status);
  }
  return readSSE(res.body);
}
