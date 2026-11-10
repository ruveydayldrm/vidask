"""VidAsk evaluation harness.

Two parts:

1. Retrieval ablation (no LLM, fast): Recall@k / MRR for chunk sizes x search modes
   (BM25 only, vector only, hybrid, hybrid + reranker).
2. End-to-end QA (LLM): full-context vs. hybrid RAG, scored on
   timestamp accuracy (±15 s), abstention, answer correctness and faithfulness
   (LLM-as-judge), and latency.

Usage (from repo root):
    cd backend && uv run python ../eval/run_eval.py               # everything
    ... run_eval.py --retrieval-only                               # skip the LLM part
    ... run_eval.py --configs full,rag --limit 10 --no-judge
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DATA_DIR", str(ROOT / "eval" / "cache"))

from app.core.config import get_settings  # noqa: E402
from app.core.device import detect_device  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402
from app.models.schemas import ChatRequest, Chunk, ContextChunk, Transcript, VideoMeta  # noqa: E402
from app.pipeline.chunking import chunk_segments  # noqa: E402
from app.pipeline.metadata import fetch_metadata  # noqa: E402
from app.pipeline.transcript import get_transcript  # noqa: E402
from app.pipeline.url import extract_video_id  # noqa: E402
from app.providers.embeddings import get_embedder, get_reranker  # noqa: E402
from app.providers.llm import LLMProvider, Message, build_llm  # noqa: E402
from app.services.citations import format_ts  # noqa: E402
from app.services.insights import extract_json  # noqa: E402
from app.services.qa import QAService  # noqa: E402
from app.services.retrieval import HybridRetriever  # noqa: E402
from app.services.store import Store  # noqa: E402
from app.services.vector_store import VectorStore  # noqa: E402

TS_TOLERANCE = 15.0
CHUNK_CONFIGS = [(20.0, 5.0), (45.0, 10.0), (90.0, 15.0)]
SEARCH_MODES = {
    "BM25": dict(use_bm25=True, use_vector=False, use_reranker=False),
    "Vector": dict(use_bm25=False, use_vector=True, use_reranker=False),
    "Hybrid (RRF)": dict(use_bm25=True, use_vector=True, use_reranker=False),
    "Hybrid + rerank": dict(use_bm25=True, use_vector=True, use_reranker=True),
}


@dataclass
class Item:
    id: str
    lang: str
    video_id: str
    question: str
    gold_answer: str
    gold_start: float | None
    gold_end: float | None
    answerable: bool


@dataclass
class VideoData:
    meta: VideoMeta
    transcript: Transcript
    indexes: dict[float, tuple[list[Chunk], VectorStore]] = field(default_factory=dict)


def load_items(path: Path) -> list[Item]:
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        items.append(
            Item(
                id=d["id"],
                lang=d.get("lang", "en"),
                video_id=extract_video_id(d["video_url"]),
                question=d["question"],
                gold_answer=d.get("gold_answer", ""),
                gold_start=d.get("gold_start"),
                gold_end=d.get("gold_end"),
                answerable=bool(d["answerable"]),
            )
        )
    return items


def overlaps(start: float, end: float, item: Item, tol: float = 0.0) -> bool:
    assert item.gold_start is not None and item.gold_end is not None
    return start <= item.gold_end + tol and end >= item.gold_start - tol


# ----------------------------------------------------------------------------- data


def prepare_videos(items: list[Item], store: Store) -> dict[str, VideoData]:
    settings = get_settings()
    videos: dict[str, VideoData] = {}
    for vid in dict.fromkeys(i.video_id for i in items):
        rec = store.get_video(vid)
        meta = rec.meta if rec else fetch_metadata(vid)
        transcript = store.get_transcript(vid)
        if transcript is None:
            transcript = get_transcript(vid, settings, meta.duration)
            store.save_transcript(transcript)
        if rec is None:
            from app.models.schemas import VideoRecord

            store.upsert_video(VideoRecord(meta=meta, transcript_source=transcript.source))
        videos[vid] = VideoData(meta, transcript)
        print(f"  · {vid}  {transcript.source.value:<16} {meta.title[:60]}")
    return videos


def build_indexes(videos: dict[str, VideoData]) -> None:
    settings = get_settings()
    emb = get_embedder(settings)
    for target, overlap in CHUNK_CONFIGS:
        vs = VectorStore(settings, emb.dim, f"{settings.embedding_model}_eval_c{int(target)}")
        for vid, v in videos.items():
            chunks = chunk_segments(v.transcript.segments, vid, target=target, overlap=overlap)
            if not vs.has_video(vid):
                vs.upsert(chunks, emb.embed_documents([c.text for c in chunks]))
            v.indexes[target] = (chunks, vs)


# ------------------------------------------------------------------------ retrieval


def retrieval_ablation(
    items: list[Item], videos: dict[str, VideoData], top_k: int
) -> list[dict[str, Any]]:
    settings = get_settings()
    emb = get_embedder(settings)
    reranker = get_reranker(settings.model_copy(update={"reranker_enabled": True}))
    rows = []
    answerable = [i for i in items if i.answerable]
    for target, _ in CHUNK_CONFIGS:
        for mode, flags in SEARCH_MODES.items():
            hits1 = hits3 = hitsk = 0
            rr_sum = 0.0
            ctx_seconds: list[float] = []
            lat: list[float] = []
            for it in answerable:
                chunks, vs = videos[it.video_id].indexes[target]
                retr = HybridRetriever(emb, vs, reranker, candidates=settings.retrieval_candidates)
                t0 = time.perf_counter()
                res = retr.retrieve(it.video_id, it.question, chunks, top_k, **flags)
                lat.append((time.perf_counter() - t0) * 1000)
                ranks = [r for r, c in enumerate(res.chunks, 1) if overlaps(c.start, c.end, it)]
                first = ranks[0] if ranks else None
                hits1 += first == 1
                hits3 += bool(first and first <= 3)
                hitsk += bool(first)
                rr_sum += 1 / first if first else 0.0
                ctx_seconds.append(sum(c.end - c.start for c in res.chunks))
            n = len(answerable)
            rows.append(
                {
                    "chunk": f"{int(target)}s",
                    "mode": mode,
                    "R@1": hits1 / n,
                    "R@3": hits3 / n,
                    f"R@{top_k}": hitsk / n,
                    "MRR": rr_sum / n,
                    "ctx_s": statistics.mean(ctx_seconds),
                    "ms": statistics.median(lat),
                }
            )
            print(
                f"  {int(target):>3}s  {mode:<16} R@{top_k}={hitsk / n:.2f}  MRR={rr_sum / n:.2f}"
            )
    return rows


# ---------------------------------------------------------------------------- QA


JUDGE_PROMPT = """You grade an answer produced by a video question-answering system.

Question: {question}
Reference answer: {gold}
Candidate answer: {answer}

Excerpts the candidate was given (with timestamps):
<<<
{context}
>>>

Score two things (answers may be in Turkish or English; wording may differ):
- "correct": 1 if the candidate states the key facts of the reference answer, otherwise 0.
- "faithful": 1 if every claim in the candidate is supported by the excerpts, otherwise 0.
Return only JSON like {{"correct": 1, "faithful": 1}}."""


async def judge(
    llm: LLMProvider, it: Item, answer: str, context: list[ContextChunk], cited: list[float]
) -> dict[str, int]:
    used = [c for c in context if any(c.start - 5 <= s <= c.end + 5 for s in cited)] or context[:3]
    ctx = "\n".join(f"[{format_ts(c.start)}] {c.text}" for c in used)[:4000]
    prompt = JUDGE_PROMPT.format(
        question=it.question, gold=it.gold_answer or "(not answerable)", answer=answer, context=ctx
    )
    for _ in range(2):
        try:
            out = await llm.complete([Message("user", prompt)], json_mode=True, max_tokens=60)
            d = extract_json(out)
            return {
                "correct": int(bool(d.get("correct"))),
                "faithful": int(bool(d.get("faithful"))),
            }
        except (ValueError, json.JSONDecodeError):
            continue
    return {"correct": 0, "faithful": 0}


async def qa_eval(
    items: list[Item],
    videos: dict[str, VideoData],
    configs: list[str],
    use_judge: bool,
    llm: LLMProvider,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base = get_settings()
    emb = get_embedder(base)
    reranker = get_reranker(base.model_copy(update={"reranker_enabled": True}))
    summary, raw = [], []
    for cfg in configs:
        settings = base.model_copy(update={"context_strategy": cfg})
        records = []
        for n, it in enumerate(items, 1):
            v = videos[it.video_id]
            chunks, vs = v.indexes[45.0]
            qa = QAService(
                settings, llm, HybridRetriever(emb, vs, reranker, settings.retrieval_candidates)
            )
            res, context = await qa.answer(
                v.transcript, chunks, v.meta.title, ChatRequest(question=it.question)
            )
            cites = [c.seconds for c in res.citations]
            rec: dict[str, Any] = {
                "config": cfg,
                "id": it.id,
                "answerable": it.answerable,
                "abstained": res.abstained,
                "answer": res.answer,
                "citations": [c.label for c in res.citations],
                "removed_citations": res.removed_citations,
                "latency_ms": res.latency_ms,
            }
            if it.answerable:
                rec["ts_ok"] = bool(cites) and overlaps(cites[0], cites[0], it, TS_TOLERANCE)
                rec["retrieved_gold"] = any(overlaps(c.start, c.end, it) for c in context)
                if use_judge and not res.abstained:
                    rec.update(await judge(llm, it, res.answer, context, cites))
                elif use_judge:
                    rec.update({"correct": 0, "faithful": None})
            elif use_judge and not res.abstained:
                rec.update(
                    {"faithful": (await judge(llm, it, res.answer, context, cites))["faithful"]}
                )
            records.append(rec)
            raw.append(rec)
            status = "ABSTAIN" if res.abstained else f"{len(cites)} cites"
            print(
                f"  [{cfg}] {n:>2}/{len(items)} {it.id:<8} {status:<10} {res.latency_ms / 1000:5.1f}s"
            )

        ans = [r for r in records if r["answerable"]]
        una = [r for r in records if not r["answerable"]]
        non_abst = [r for r in records if not r["abstained"] and r.get("faithful") is not None]
        lat = [r["latency_ms"] for r in records]
        row = {
            "config": "Full transcript" if cfg == "full" else "Hybrid RAG + rerank",
            "Context recall": statistics.mean(r["retrieved_gold"] for r in ans),
            "Timestamp acc (±15s)": statistics.mean(r["ts_ok"] for r in ans),
            "Abstention acc": statistics.mean(r["abstained"] for r in una) if una else float("nan"),
            "False abstention": statistics.mean(r["abstained"] for r in ans),
            "Fabricated cites removed": sum(len(r["removed_citations"]) for r in records),
            "p50 latency (s)": statistics.median(lat) / 1000,
            "p95 latency (s)": sorted(lat)[max(0, int(len(lat) * 0.95) - 1)] / 1000,
        }
        if use_judge:
            row["Correctness (judge)"] = statistics.mean(r.get("correct", 0) for r in ans)
            row["Faithfulness (judge)"] = (
                statistics.mean(r["faithful"] for r in non_abst) if non_abst else float("nan")
            )
        summary.append(row)
    return summary, raw


# ------------------------------------------------------------------------- report


def md_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "_no rows_\n"
    cols = list(rows[0])

    def fmt(v: Any) -> str:
        if isinstance(v, bool):
            return "✓" if v else "✗"
        if isinstance(v, float):
            return f"{v:.2f}" if v == v else "–"
        return str(v)

    head = "| " + " | ".join(cols) + " |\n|" + "|".join("---" for _ in cols) + "|\n"
    return head + "".join("| " + " | ".join(fmt(r[c]) for c in cols) + " |\n" for r in rows)


def write_report(
    path: Path, ctx: dict[str, Any], retrieval: list[dict[str, Any]], qa: list[dict[str, Any]]
) -> None:
    parts = [
        f"# VidAsk eval — {ctx['date']}\n",
        f"- Dataset: `{ctx['dataset']}` — {ctx['n']} questions ({ctx['n_ans']} answerable, {ctx['n_un']} unanswerable) over {ctx['videos']} videos (TR + EN)",
        f"- LLM: `{ctx['llm']}` · Embeddings: `{ctx['emb']}` · Reranker: `{ctx['rr']}`",
        f"- Hardware: {ctx['device']}\n",
    ]
    if qa:
        parts += ["## End-to-end QA\n", md_table(qa), ""]
    if retrieval:
        parts += [
            f"## Retrieval ablation (answerable questions, top-{ctx['k']})\n",
            "`ctx_s` = seconds of video put into the prompt; bigger chunks buy recall with context budget.\n",
            md_table(retrieval),
        ]
    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=str(ROOT / "eval" / "datasets" / "vidask_v1.jsonl"))
    ap.add_argument("--configs", default="full,rag")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--retrieval-only", action="store_true")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--provider")
    ap.add_argument("--model")
    args = ap.parse_args()

    settings = get_settings()
    configure_logging("WARNING")
    items = load_items(Path(args.dataset))
    if args.limit:
        items = items[: args.limit]
    store = Store(settings.db_path)

    print("▸ Preparing videos")
    videos = prepare_videos(items, store)
    print("▸ Building indexes")
    build_indexes(videos)
    print("▸ Retrieval ablation")
    retrieval = retrieval_ablation(items, videos, settings.retrieval_top_k)

    qa_rows: list[dict[str, Any]] = []
    raw: list[dict[str, Any]] = []
    llm = build_llm(settings, provider=args.provider, model=args.model)
    if not args.retrieval_only:
        print(f"▸ QA eval with {llm.name}:{llm.model}")
        qa_rows, raw = asyncio.run(
            qa_eval(items, videos, args.configs.split(","), not args.no_judge, llm)
        )

    out_dir = ROOT / "eval" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    dev = detect_device(settings.device, settings.min_gpu_vram_gb)
    ctx = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "dataset": Path(args.dataset).name,
        "n": len(items),
        "n_ans": sum(i.answerable for i in items),
        "n_un": sum(not i.answerable for i in items),
        "videos": len(videos),
        "llm": f"{llm.name}:{llm.model}",
        "emb": settings.embedding_model,
        "rr": settings.reranker_model,
        "device": f"{dev.device} ({dev.reason})",
        "k": settings.retrieval_top_k,
    }
    report = out_dir / f"results-{stamp}.md"
    write_report(report, ctx, retrieval, qa_rows)
    (out_dir / "latest.md").write_text(report.read_text(encoding="utf-8"), encoding="utf-8")
    if raw:
        (out_dir / f"raw-{stamp}.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in raw), encoding="utf-8"
        )
    print(f"\n✔ Report: {report.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
