export type TranscriptSource = "manual_captions" | "auto_captions" | "whisper";
export type VideoStatus = "pending" | "processing" | "ready" | "failed";
export type Stage = "metadata" | "transcript" | "vision" | "indexing" | "insights";
export type ChunkSource = "transcript" | "visual";

export interface VideoMeta {
  video_id: string;
  url: string;
  title: string;
  channel: string;
  duration: number;
  thumbnail: string;
  language: string | null;
}

export interface Chapter {
  start: number;
  title: string;
}

export interface Insights {
  summary: string;
  chapters: Chapter[];
  suggested_questions: string[];
  error: string | null;
}

export interface VideoRecord {
  meta: VideoMeta;
  status: VideoStatus;
  transcript_source: TranscriptSource | null;
  vision_used: boolean;
  insights: Insights | null;
  error: string | null;
  latest_job_id: string | null;
  updated_at: string;
}

export interface StageState {
  stage: Stage;
  status: "pending" | "running" | "done" | "skipped" | "failed";
  progress: number;
  message: string;
}

export interface Job {
  id: string;
  video_id: string;
  status: VideoStatus;
  progress: number;
  stage: Stage | null;
  message: string;
  error: string | null;
  error_code: string | null;
  stages: StageState[];
}

export interface Segment {
  start: number;
  end: number;
  text: string;
}

export interface VisualChunk {
  start: number;
  end: number;
  text: string;
  source: "visual";
}

export interface TranscriptData {
  video_id: string;
  language: string | null;
  source: TranscriptSource;
  segments: Segment[];
  visual: VisualChunk[];
}

export interface Citation {
  label: string;
  seconds: number;
  chunk_start: number;
  chunk_end: number;
  source: ChunkSource;
  preview: string;
}

export interface AnswerResult {
  answer: string;
  citations: Citation[];
  abstained: boolean;
  strategy: "full" | "rag";
  removed_citations: string[];
  latency_ms: number;
}

export interface ProcessResponse {
  video_id: string;
  job_id: string | null;
  cached: boolean;
  status: VideoStatus;
}

export interface SettingsPayload {
  current: {
    llm_provider: "ollama" | "groq" | "gemini";
    llm_model: string;
    vision_enabled: boolean;
    reranker_enabled: boolean;
    embedding_model: string;
    reranker_model: string;
    whisper_model: string;
    context_window: number;
  };
  providers: Record<string, { available: boolean; models: string[] }>;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  status?: "streaming" | "done" | "error";
  result?: AnswerResult;
  error?: string;
  meta?: { strategy: "full" | "rag"; model: string; provider: string };
}
