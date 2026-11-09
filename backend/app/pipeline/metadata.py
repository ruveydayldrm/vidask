"""Video metadata via yt-dlp (no download) with a fast oEmbed preview path."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.errors import VideoUnavailableError
from app.core.logging import get_logger
from app.models.schemas import VideoMeta
from app.pipeline.url import canonical_url

log = get_logger(__name__)


def _ydl_opts() -> dict[str, Any]:
    return {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True}


def fetch_metadata(video_id: str) -> VideoMeta:
    import yt_dlp

    url = canonical_url(video_id)
    try:
        with yt_dlp.YoutubeDL(_ydl_opts()) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:  # yt-dlp raises DownloadError/ExtractorError
        log.warning("metadata.ytdlp_failed", video_id=video_id, error=str(exc))
        return fetch_oembed(video_id)
    if not info:
        raise VideoUnavailableError(f"Video {video_id} not found.")
    return VideoMeta(
        video_id=video_id,
        url=url,
        title=info.get("title") or "",
        channel=info.get("channel") or info.get("uploader") or "",
        duration=float(info.get("duration") or 0),
        thumbnail=info.get("thumbnail") or _thumb(video_id),
        language=info.get("language"),
    )


def fetch_oembed(video_id: str) -> VideoMeta:
    """Quick metadata without duration (used for previews and as a fallback)."""
    url = canonical_url(video_id)
    try:
        resp = httpx.get(
            "https://www.youtube.com/oembed",
            params={"url": url, "format": "json"},
            timeout=10,
        )
    except httpx.HTTPError as exc:
        raise VideoUnavailableError(f"Could not reach YouTube: {exc}") from exc
    if resp.status_code in (401, 403, 404):
        raise VideoUnavailableError("Video is private, removed or does not exist.")
    resp.raise_for_status()
    data = resp.json()
    return VideoMeta(
        video_id=video_id,
        url=url,
        title=data.get("title", ""),
        channel=data.get("author_name", ""),
        thumbnail=_thumb(video_id),
    )


def _thumb(video_id: str) -> str:
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
