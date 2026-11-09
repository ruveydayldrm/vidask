# VidAsk

**Ask any YouTube video a question — get answers with verified, clickable timestamps. Runs fully locally.**

> 🚧 Work in progress. Full README (architecture diagram, eval results, setup guides) is coming.

- Captions first (manual › auto), Whisper fallback
- Hybrid retrieval (BM25 + `bge-m3` vectors + `bge-reranker-v2-m3`) or full-context when the transcript fits
- Every `[mm:ss]` citation is validated against the passages actually retrieved — fabricated timestamps are removed, even mid-stream
- Says "the video doesn't cover this" instead of guessing
- Optional on-screen understanding: scene detection + OCR (+ VLM captions)
- Next.js workspace: embedded player, synced transcript, chapters, chat with streaming answers
- LLM providers: Ollama (default), Groq, Gemini

## Quick start (local, no Docker)

```bash
# backend
cd backend && uv sync && uv run uvicorn app.main:app --reload --port 8000
# frontend
cd frontend && npm install && npm run dev
# LLM
ollama pull qwen2.5:3b
```

MIT licensed.
