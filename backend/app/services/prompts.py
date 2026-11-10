"""Prompt templates. Kept short and literal so 3B-class local models follow them."""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.models.schemas import ChunkSource, ContextChunk
from app.services.citations import format_ts

NO_ANSWER = "NO_ANSWER"

ABSTAIN_MESSAGES = {
    "tr": "Videoda bu konudan bahsedilmiyor.",
    "en": "This topic isn't covered in the video.",
}

# NB: no re.IGNORECASE on the character class — with it, Python matches "İ" against
# a plain "i", which made every English question containing two i's "Turkish".
_TR_CHARS = re.compile(r"[çğıöşüÇĞİÖŞÜ]")
_TR_WORDS = re.compile(
    r"\b(?:ne|neden|nasıl|nedir|niçin|niye|mi|mı|mu|mü|midir|mıdır|hangi|hangisi|kim|kaç|"
    r"bu|şu|bir|videoda|videonun|için|ile|ve|var|yok|nerede|anlatılıyor|bahsediliyor)\b",
    re.IGNORECASE,
)
_EN_WORDS = re.compile(
    r"\b(?:what|why|how|who|when|where|which|does|do|did|is|are|was|the|a|an|of|in|"
    r"video|explain|can|about)\b",
    re.IGNORECASE,
)


def detect_lang(text: str, fallback: str = "en") -> str:
    tr = 2 * len(_TR_CHARS.findall(text)) + len(_TR_WORDS.findall(text))
    en = len(_EN_WORDS.findall(text))
    if tr > en:
        return "tr"
    if en > tr:
        return "en"
    return fallback


LANG_NAME = {"tr": "Turkish", "en": "English"}
VISUAL_TAG = "🖼 On screen:"
# Small models sometimes echo excerpt markup; strip it from answers.
LEAKED_MARKUP = re.compile(r"\((?:spoken|ON SCREEN)\)\s*|🖼\s*On screen:\s*", re.IGNORECASE)


def format_context(chunks: Sequence[ContextChunk]) -> str:
    lines = []
    for c in sorted(chunks, key=lambda c: c.start):
        text = c.text.strip()
        if c.source == ChunkSource.VISUAL:
            text = f"{VISUAL_TAG} {text.removeprefix('Ekranda/On screen:').strip()}"
        lines.append(f"[{format_ts(c.start)}] {text}")
    return "\n\n".join(lines)


def qa_system_prompt(lang: str, title: str) -> str:
    return f"""You are VidAsk. You answer questions about ONE YouTube video titled "{title}" using ONLY the excerpts the user provides. Each excerpt starts with its timestamp, e.g. [03:15].

Rules:
1. Use only facts stated in the excerpts. Never add outside knowledge or guesses.
2. Answer the question directly in your own words. Do not copy whole excerpts.
3. End each sentence with the timestamp of the excerpt it came from, e.g. [03:15]. Only use timestamps that appear at the start of an excerpt.
4. Only if none of the excerpts is about the question, reply with exactly: {NO_ANSWER}
5. Be concise: 1-4 sentences or a short bullet list. Use Markdown; put code in fenced code blocks.
6. Excerpts starting with "{VISUAL_TAG}" describe what is shown on screen; say "on screen" when you use them.

Example of the required format:
Question: What is a cache?
Answer: A cache stores recent results so they can be reused quickly [01:05]. The speaker says it trades memory for speed [02:40]."""


def qa_user_prompt(context: str, question: str, lang: str = "en") -> str:
    return f"""Excerpts from the video:
<<<
{context}
>>>

Question: {question}

Answer in {LANG_NAME.get(lang, "English")} with [mm:ss] citations:"""


def insights_prompt(
    lang: str, title: str, transcript: str, duration: str, n_chapters: int = 8
) -> str:
    language = LANG_NAME.get(lang, "English")
    lo = max(2, n_chapters - 2)
    return f"""Below is the timestamped transcript of the YouTube video "{title}" (length {duration}).

<<<
{transcript}
>>>

Return a JSON object with exactly these keys, all text written in {language}:
- "summary": 3-5 sentence summary of the whole video.
- "chapters": {lo}-{n_chapters} chapters covering the video in order, each {{"start": "mm:ss", "title": "short title"}}. The first chapter starts at "00:00". Each chapter starts where a new topic begins; use timestamps that appear in the transcript. Titles must be distinct.
- "questions": 5 short, specific questions a viewer could ask that the video answers.

Return only the JSON object."""


def notes_prompt(lang: str, transcript: str) -> str:
    return f"""Summarise this part of a video transcript as 4-8 bullet notes in {LANG_NAME.get(lang, "English")}. Start each bullet with the timestamp it refers to, copied from the transcript, e.g. "[03:15] ...".

<<<
{transcript}
>>>"""
