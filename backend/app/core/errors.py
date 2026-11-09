"""Domain errors with stable codes the frontend can translate."""

from __future__ import annotations


class VidAskError(Exception):
    code = "internal_error"
    status_code = 500

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code


class InvalidURLError(VidAskError):
    code = "invalid_url"
    status_code = 422


class VideoUnavailableError(VidAskError):
    code = "video_unavailable"
    status_code = 404


class TranscriptUnavailableError(VidAskError):
    code = "transcript_unavailable"
    status_code = 422


class NotFoundError(VidAskError):
    code = "not_found"
    status_code = 404


class ProviderError(VidAskError):
    code = "provider_error"
    status_code = 502
