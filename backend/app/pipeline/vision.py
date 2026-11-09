"""Visual understanding: scene-change keyframes → OCR (+ optional VLM caption).

Only frames at scene changes are analysed (not every frame), the frame budget is
capped, and near-duplicate screens (a slide that stays up while the speaker
talks) are merged, so a 20-minute talk typically costs 15-40 OCR calls.
"""

from __future__ import annotations

import base64
import difflib
import re
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from app.core.config import Settings
from app.core.device import detect_device
from app.core.logging import get_logger
from app.models.schemas import Chunk, ChunkSource
from app.pipeline.url import canonical_url

log = get_logger(__name__)
ProgressFn = Callable[[float, str], None]

_ocr_readers: dict[tuple[tuple[str, ...], bool], Any] = {}
VLM_PROMPT = (
    "Describe what is shown on this video frame in 1-2 sentences. "
    "Mention slide titles, code, diagrams or charts if present. Do not guess."
)


def download_low_res(video_id: str, out_dir: Path) -> Path:
    import yt_dlp

    opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "bv*[height<=480][ext=mp4]/bv*[height<=480]/b[height<=480]/b",
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(canonical_url(video_id), download=True)
        return Path(ydl.prepare_filename(info))


def pick_timestamps(
    scene_bounds: list[tuple[float, float]], duration: float, max_frames: int, min_gap: float = 4.0
) -> list[float]:
    """Midpoint of each scene; evenly sampled if there are no cuts; capped and de-clustered."""
    if not scene_bounds and duration > 0:
        step = max(duration / max_frames, 20.0)
        scene_bounds = [(t, min(t + step, duration)) for t in _frange(0, duration, step)]
    times = [(s + e) / 2 for s, e in scene_bounds if e - s >= 1.0]
    spaced: list[float] = []
    for t in sorted(times):
        if not spaced or t - spaced[-1] >= min_gap:
            spaced.append(t)
    if len(spaced) > max_frames:
        stride = len(spaced) / max_frames
        spaced = [spaced[int(i * stride)] for i in range(max_frames)]
    return spaced


def _frange(start: float, stop: float, step: float) -> list[float]:
    out, t = [], start
    while t < stop:
        out.append(t)
        t += step
    return out


def clean_ocr(lines: list[str]) -> str:
    text = " ".join(line.strip() for line in lines if line.strip())
    text = re.sub(r"\s+", " ", text)
    alnum = sum(ch.isalnum() for ch in text)
    return text if len(text) >= 12 and alnum / max(len(text), 1) > 0.5 else ""


def similar(a: str, b: str, threshold: float = 0.85) -> bool:
    return difflib.SequenceMatcher(None, a, b).ratio() >= threshold


def _reader(langs: list[str], gpu: bool) -> Any:
    import easyocr

    key = (tuple(langs), gpu)
    if key not in _ocr_readers:
        _ocr_readers[key] = easyocr.Reader(list(langs), gpu=gpu, verbose=False)
    return _ocr_readers[key]


def _caption(settings: Settings, jpg: bytes) -> str:
    try:
        resp = httpx.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/generate",
            json={
                "model": settings.vision_vlm_model,
                "prompt": VLM_PROMPT,
                "images": [base64.b64encode(jpg).decode()],
                "stream": False,
                "options": {"temperature": 0},
            },
            timeout=120,
        )
        resp.raise_for_status()
        return str(resp.json().get("response", "")).strip()
    except httpx.HTTPError as exc:
        log.warning("vision.vlm_failed", error=str(exc))
        return ""


def extract_visual_chunks(
    video_id: str, settings: Settings, duration: float, progress: ProgressFn
) -> list[Chunk]:
    try:
        import cv2
        from scenedetect import ContentDetector, detect
    except ImportError as exc:
        raise RuntimeError(
            "Vision extras are not installed. Run `uv sync --extra vision`."
        ) from exc

    device = detect_device(settings.device, settings.min_gpu_vram_gb).device
    with tempfile.TemporaryDirectory(prefix="vidask_vis_") as tmp:
        progress(0.02, "Downloading low-res video")
        path = download_low_res(video_id, Path(tmp))

        progress(0.15, "Detecting scene changes")
        scenes = detect(
            str(path), ContentDetector(threshold=settings.vision_scene_threshold), show_progress=False
        )
        bounds = [(s.get_seconds(), e.get_seconds()) for s, e in scenes]
        times = pick_timestamps(bounds, duration, settings.vision_max_frames)
        log.info("vision.scenes", video_id=video_id, scenes=len(bounds), frames=len(times))

        progress(0.25, f"Loading OCR ({'+'.join(settings.vision_ocr_languages)})")
        reader = _reader(settings.vision_ocr_languages, gpu=device == "cuda")
        cap = cv2.VideoCapture(str(path))
        items: list[tuple[float, str]] = []
        try:
            for i, t in enumerate(times):
                cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
                ok, frame = cap.read()
                if not ok:
                    continue
                text = clean_ocr(reader.readtext(frame, detail=0, paragraph=True))
                caption = ""
                if settings.vision_vlm_model:
                    ok_jpg, buf = cv2.imencode(".jpg", frame)
                    if ok_jpg:
                        caption = _caption(settings, buf.tobytes())
                combined = " | ".join(
                    p for p in (f"Ekranda/On screen: {text}" if text else "", caption) if p
                )
                if combined:
                    items.append((t, combined))
                progress(0.25 + 0.75 * (i + 1) / len(times), f"Reading frame {i + 1}/{len(times)}")
        finally:
            cap.release()

    chunks: list[Chunk] = []
    for t, text in items:
        if chunks and similar(chunks[-1].text, text):
            continue  # same slide still on screen
        chunks.append(
            Chunk(
                video_id=video_id,
                idx=len(chunks),
                start=round(t, 2),
                end=round(t, 2),
                text=text[:1200],
                source=ChunkSource.VISUAL,
            )
        )
    for i, ch in enumerate(chunks):
        nxt = chunks[i + 1].start if i + 1 < len(chunks) else (duration or ch.start + 15)
        chunks[i] = ch.model_copy(update={"end": round(max(min(nxt, ch.start + 60), ch.start + 5), 2)})
    log.info("vision.done", video_id=video_id, visual_chunks=len(chunks))
    return chunks
