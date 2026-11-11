"""Transcript acquisition: captions first (manual > auto), Whisper fallback."""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.core.device import detect_device, whisper_compute_type
from app.core.errors import TranscriptUnavailableError
from app.core.logging import get_logger
from app.models.schemas import Segment, Transcript, TranscriptSource
from app.pipeline.url import canonical_url

log = get_logger(__name__)

ProgressFn = Callable[[float, str], None]


def _noop(_: float, __: str) -> None:
    return None


def _base(code: str) -> str:
    return code.split("-")[0].lower()


def _spoken_language(
    auto: list[Any], manual: list[Any], preferred: list[str], hint: str | None
) -> str:
    """Which auto track is the original audio?

    Usually there is exactly one. Videos with AI-dubbed audio (YouTube
    auto-dubbing) get one auto track per audio language, though, and the dub can
    come first. Tie-breakers: the language YouTube reports for the video, then
    an auto language the creator also wrote captions in, then preference order.
    """
    langs = [_base(t.language_code) for t in auto]
    if len(set(langs)) == 1:
        return langs[0]
    if hint and _base(hint) in langs:
        return _base(hint)
    manual_langs = {_base(t.language_code) for t in manual}
    with_manual = [lang for lang in langs if lang in manual_langs]
    if len(with_manual) == 1:
        return with_manual[0]
    for lang in preferred:
        if lang in (with_manual or langs):
            return lang
    return (with_manual or langs)[0]


def choose_track(
    tracks: list[Any], preferred: list[str], spoken_hint: str | None = None
) -> tuple[Any, TranscriptSource] | None:
    """Pick the caption track that matches what is actually *spoken*.

    YouTube's auto-generated track is in the spoken language, so it tells us the
    original language. Manual captions in other languages are usually community
    translations — using them would make citations quote words that were never
    said. Order:
      1. manual captions in the spoken language
      2. auto captions (spoken language)
      3. manual captions in a preferred language (no auto track to compare with)
      4. any manual captions
    """
    if not tracks:
        return None
    manual = [t for t in tracks if not t.is_generated]
    auto = [t for t in tracks if t.is_generated]
    if auto:
        spoken = _spoken_language(auto, manual, preferred, spoken_hint)
        same = next((t for t in manual if _base(t.language_code) == spoken), None)
        if same:
            return same, TranscriptSource.MANUAL
        return next(t for t in auto if _base(t.language_code) == spoken), TranscriptSource.AUTO
    for lang in preferred:
        hit = next((t for t in manual if _base(t.language_code) == lang), None)
        if hit:
            return hit, TranscriptSource.MANUAL
    return manual[0], TranscriptSource.MANUAL


def fetch_captions(
    video_id: str, languages: list[str], spoken_hint: str | None = None
) -> Transcript | None:
    """Return captions or ``None`` if the video has none / they are blocked."""
    from youtube_transcript_api import YouTubeTranscriptApi

    api = YouTubeTranscriptApi()
    try:
        listing = api.list(video_id)
    except Exception as exc:
        log.info("captions.unavailable", video_id=video_id, error=type(exc).__name__)
        return None

    picked = choose_track(list(listing), languages, spoken_hint)
    if picked is None:
        return None
    chosen, source = picked

    try:
        fetched = chosen.fetch()
    except Exception as exc:
        log.warning("captions.fetch_failed", video_id=video_id, error=str(exc))
        return None

    segments = [
        Segment(start=float(s.start), end=float(s.start + s.duration), text=s.text) for s in fetched
    ]
    log.info(
        "captions.fetched",
        video_id=video_id,
        language=chosen.language_code,
        source=source.value,
        segments=len(segments),
    )
    return Transcript(
        video_id=video_id,
        language=_base(chosen.language_code),
        source=source,
        segments=segments,
    )


def download_audio(video_id: str, out_dir: Path) -> Path:
    import yt_dlp

    opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(canonical_url(video_id), download=True)
        return Path(ydl.prepare_filename(info))


_whisper_cache: dict[tuple[str, str, str], object] = {}


def _run_whisper(
    model: object, audio: Path, duration: float, *, vad: bool, progress: ProgressFn
) -> tuple[list[Segment], object]:
    seg_iter, info = model.transcribe(  # type: ignore[attr-defined]
        str(audio), vad_filter=vad, beam_size=1
    )
    total = duration or float(getattr(info, "duration", 0) or 0)
    segments: list[Segment] = []
    for s in seg_iter:
        text = s.text.strip()
        if text:
            segments.append(Segment(start=s.start, end=s.end, text=text))
        if total:
            frac = min(s.end / total, 1.0)
            progress(0.1 + 0.9 * frac, f"Whisper {int(frac * 100)}%")
    return segments, info


def transcribe_whisper(
    video_id: str,
    settings: Settings,
    duration: float,
    progress: ProgressFn = _noop,
) -> Transcript:
    from faster_whisper import WhisperModel

    dev = detect_device(settings.device, settings.min_gpu_vram_gb).device
    compute = whisper_compute_type(dev, settings.whisper_compute_type)
    key = (settings.whisper_model, dev, compute)
    if key not in _whisper_cache:
        progress(0.02, f"Loading Whisper '{settings.whisper_model}' on {dev}")
        _whisper_cache[key] = WhisperModel(settings.whisper_model, device=dev, compute_type=compute)
    model = _whisper_cache[key]

    with tempfile.TemporaryDirectory(prefix="vidask_") as tmp:
        progress(0.05, "Downloading audio")
        try:
            audio = download_audio(video_id, Path(tmp))
        except Exception as exc:
            raise TranscriptUnavailableError(f"Audio download failed: {exc}") from exc
        progress(0.1, "Transcribing with Whisper")
        segments, info = _run_whisper(model, audio, duration, vad=True, progress=progress)
        if not segments:
            # Silero VAD treats singing over music (and some noisy speech) as
            # non-speech. Retry once without it before giving up.
            log.info("whisper.vad_empty_retry", video_id=video_id)
            progress(0.1, "No speech detected, retrying without VAD")
            segments, info = _run_whisper(model, audio, duration, vad=False, progress=progress)

    if not segments:
        raise TranscriptUnavailableError("Whisper produced no speech for this video.")
    language = str(getattr(info, "language", "") or "")
    log.info("whisper.done", video_id=video_id, language=language, segments=len(segments))
    return Transcript(
        video_id=video_id,
        language=language,
        source=TranscriptSource.WHISPER,
        segments=segments,
    )


def get_transcript(
    video_id: str,
    settings: Settings,
    duration: float,
    progress: ProgressFn = _noop,
    spoken_hint: str | None = None,
) -> Transcript:
    progress(0.0, "Looking for captions")
    captions = fetch_captions(video_id, settings.transcript_languages, spoken_hint)
    if captions and captions.segments:
        progress(1.0, f"Using {captions.source.value.replace('_', ' ')}")
        return captions
    progress(0.0, "No captions — falling back to Whisper")
    return transcribe_whisper(video_id, settings, duration, progress)
