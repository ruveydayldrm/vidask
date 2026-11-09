"""YouTube URL → video id."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from app.core.errors import InvalidURLError

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_YT_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
}
_PATH_PREFIXES = ("/shorts/", "/embed/", "/live/", "/v/", "/e/")


def extract_video_id(url: str) -> str:
    """Return the 11-char video id for any common YouTube URL form.

    Supports ``watch?v=``, ``youtu.be/``, ``shorts/``, ``embed/``, ``live/``,
    URLs with timestamps/playlists, missing scheme, and bare ids.
    """
    raw = (url or "").strip()
    if not raw:
        raise InvalidURLError("URL is empty.")
    if _ID_RE.match(raw):
        return raw
    if "://" not in raw:
        raw = "https://" + raw

    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    candidate: str | None = None

    if host in {"youtu.be", "www.youtu.be"}:
        candidate = parsed.path.lstrip("/").split("/")[0]
    elif host in _YT_HOSTS:
        if parsed.path in ("/watch", "/watch/"):
            candidate = parse_qs(parsed.query).get("v", [None])[0]
        else:
            for prefix in _PATH_PREFIXES:
                if parsed.path.startswith(prefix):
                    candidate = parsed.path[len(prefix) :].split("/")[0]
                    break
        if candidate is None and "v" in parse_qs(parsed.query):
            candidate = parse_qs(parsed.query)["v"][0]
    else:
        raise InvalidURLError(f"Not a YouTube URL: {url!r}")

    if not candidate or not _ID_RE.match(candidate):
        raise InvalidURLError(f"Could not find a valid video id in {url!r}")
    return candidate


def canonical_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"
