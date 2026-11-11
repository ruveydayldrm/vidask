from dataclasses import dataclass

from app.models.schemas import TranscriptSource
from app.pipeline.transcript import choose_track


@dataclass
class Track:
    language_code: str
    is_generated: bool


def test_prefers_spoken_language_over_translated_manual() -> None:
    # English video with a community Turkish translation and auto English captions.
    tracks = [Track("tr", False), Track("ar", False), Track("en", True)]
    track, src = choose_track(tracks, ["tr", "en"])
    assert (track.language_code, src) == ("en", TranscriptSource.AUTO)


def test_manual_in_spoken_language_wins() -> None:
    tracks = [Track("tr", False), Track("en-US", False), Track("en", True)]
    track, src = choose_track(tracks, ["tr", "en"])
    assert (track.language_code, src) == ("en-US", TranscriptSource.MANUAL)


def test_no_auto_track_uses_preferred_then_any() -> None:
    assert (
        choose_track([Track("de", False), Track("en", False)], ["tr", "en"])[0].language_code
        == "en"
    )
    assert choose_track([Track("de", False)], ["tr", "en"])[0].language_code == "de"


def test_auto_dubbed_video_uses_original_language() -> None:
    # Turkish video with YouTube AI dubbing: the English dub's auto track is listed first.
    # Real listing for OkEMTyZaGEQ.
    tracks = [Track("tr", False), Track("en", True), Track("tr", True)]
    track, src = choose_track(tracks, ["en"])  # even when English is preferred
    assert (track.language_code, src) == ("tr", TranscriptSource.MANUAL)


def test_auto_dubbed_uses_video_language_hint() -> None:
    tracks = [Track("en", True), Track("es", True), Track("tr", True)]
    track, src = choose_track(tracks, ["en"], spoken_hint="tr")
    assert (track.language_code, src) == ("tr", TranscriptSource.AUTO)


def test_auto_dubbed_without_hints_falls_back_to_preference() -> None:
    tracks = [Track("es", True), Track("en", True)]
    assert choose_track(tracks, ["tr", "en"])[0].language_code == "en"


def test_empty() -> None:
    assert choose_track([], ["tr"]) is None
