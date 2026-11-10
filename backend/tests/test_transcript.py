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


def test_empty() -> None:
    assert choose_track([], ["tr"]) is None
