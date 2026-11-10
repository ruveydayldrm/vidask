import json

from app.models.schemas import Transcript
from app.providers.llm.fake import FakeProvider
from app.services.insights import (
    chapter_budget,
    clean_chapters,
    extract_json,
    generate_insights,
)


def test_extract_json_from_fenced_output() -> None:
    assert extract_json('Sure!\n```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('prefix {"b": [1,2]} suffix') == {"b": [1, 2]}


def test_clean_chapters_sorts_filters_and_anchors_intro() -> None:
    raw = [
        {"start": "05:00", "title": "Later"},
        {"start": "00:40", "title": "First topic"},
        {"start": "00:45", "title": "Too close"},
        {"start": "99:00", "title": "Beyond end"},
        {"start": "nope", "title": "Bad"},
        "garbage",
    ]
    chapters = clean_chapters(raw, duration=600, intro_title="Intro")
    assert [(c.start, c.title) for c in chapters] == [
        (0, "Intro"),
        (40, "First topic"),
        (300, "Later"),
    ]


def test_chapters_snap_to_anchors_and_respect_budget() -> None:
    raw = [{"start": f"00:{s:02d}", "title": f"t{s}"} for s in (0, 15, 25, 40, 56)]
    raw += [{"start": "01:10", "title": "late"}, {"start": "01:40", "title": "later"}]
    anchors = [0.0, 31.0, 62.0, 95.0]
    chapters = clean_chapters(raw, 120, "Intro", anchors=anchors, max_chapters=3)
    assert len(chapters) == 3
    assert all(c.start in anchors for c in chapters)
    assert chapter_budget(165) == 5
    assert chapter_budget(3600) == 12


async def test_generate_insights(transcript: Transcript) -> None:
    payload = {
        "summary": "A tutorial on decorators.",
        "chapters": [
            {"start": "00:00", "title": "Basics"},
            {"start": "01:12", "title": "Class decorators"},
        ],
        "questions": ["What is a decorator?", "Why use wraps?", "q3", "q4", "q5", "q6"],
    }
    llm = FakeProvider(json.dumps(payload))
    ins = await generate_insights(transcript, "Decorators", 132, llm)
    assert ins.error is None
    assert ins.summary.startswith("A tutorial")
    assert [c.start for c in ins.chapters] == [0, 72]
    assert len(ins.suggested_questions) == 5


async def test_generate_insights_parse_failure(transcript: Transcript) -> None:
    ins = await generate_insights(transcript, "x", 132, FakeProvider("not json"))
    assert ins.error and "parse" in ins.error


def test_vision_helpers() -> None:
    from app.pipeline.vision import clean_ocr, pick_timestamps, similar

    times = pick_timestamps([(0, 10), (10, 12), (12, 13), (13, 40)], duration=40, max_frames=10)
    assert times == [5.0, 11.0, 26.5]  # 12.5 dropped: too close to 11.0
    capped = pick_timestamps([(i * 10, i * 10 + 10) for i in range(100)], 1000, max_frames=10)
    assert len(capped) == 10
    sampled = pick_timestamps([], duration=200, max_frames=5)
    assert len(sampled) == 5
    assert clean_ocr(["def hello():", "  return 42"]) == "def hello(): return 42"
    assert clean_ocr(["|||", "--"]) == ""
    assert similar("Slide 1: Intro to Kubernetes", "Slide 1: Intro to Kubernetes!")
