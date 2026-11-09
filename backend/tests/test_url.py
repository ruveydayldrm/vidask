import pytest

from app.core.errors import InvalidURLError
from app.pipeline.url import canonical_url, extract_video_id

VID = "dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "url",
    [
        f"https://www.youtube.com/watch?v={VID}",
        f"https://youtube.com/watch?v={VID}&t=42s",
        f"https://www.youtube.com/watch?feature=share&v={VID}&list=PL123",
        f"https://m.youtube.com/watch?v={VID}",
        f"https://music.youtube.com/watch?v={VID}",
        f"https://youtu.be/{VID}",
        f"https://youtu.be/{VID}?t=90",
        f"https://www.youtube.com/shorts/{VID}",
        f"https://www.youtube.com/shorts/{VID}?feature=share",
        f"https://www.youtube.com/embed/{VID}?start=10",
        f"https://www.youtube-nocookie.com/embed/{VID}",
        f"https://www.youtube.com/live/{VID}?si=abc",
        f"youtube.com/watch?v={VID}",
        f"  https://youtu.be/{VID}  ",
        VID,
    ],
)
def test_extracts_id(url: str) -> None:
    assert extract_video_id(url) == VID


@pytest.mark.parametrize(
    "url",
    [
        "",
        "https://vimeo.com/123456",
        "https://www.youtube.com/watch?v=short",
        "https://www.youtube.com/channel/UC123",
        "https://youtu.be/",
        "not a url at all",
    ],
)
def test_rejects_invalid(url: str) -> None:
    with pytest.raises(InvalidURLError):
        extract_video_id(url)


def test_canonical() -> None:
    assert canonical_url(VID) == f"https://www.youtube.com/watch?v={VID}"
