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

_TR_HINTS = re.compile(
    r"[çğışöüÇĞİŞÖÜ]|\b(ne|neden|nasıl|nedir|mi|mı|mu|mü|hangi|kim|kaç|bu|videoda|için|ile|ve)\b",
    re.IGNORECASE,
)


def detect_lang(text: str, fallback: str = "en") -> str:
    hits = len(_TR_HINTS.findall(text))
    if hits >= 1 and (hits >= 2 or re.search(r"[çğışöüİ]", text)):
        return "tr"
    if re.search(r"\b(what|why|how|who|when|which|does|is|the|video)\b", text, re.I):
        return "en"
    return fallback


LANG_NAME = {"tr": "Turkish", "en": "English"}


def format_context(chunks: Sequence[ContextChunk]) -> str:
    lines = []
    for c in sorted(chunks, key=lambda c: c.start):
        tag = "ON SCREEN" if c.source == ChunkSource.VISUAL else "spoken"
        lines.append(f"[{format_ts(c.start)}] ({tag}) {c.text.strip()}")
    return "\n\n".join(lines)


def qa_system_prompt(lang: str, title: str) -> str:
    return f"""You are VidAsk. You answer questions about ONE YouTube video titled "{title}" using ONLY the excerpts the user provides. Each excerpt starts with its timestamp, e.g. [03:15].

Rules:
1. Use only facts stated in the excerpts. Never add outside knowledge or guesses.
2. After each sentence or bullet, cite the timestamp of the excerpt it came from, copied exactly, e.g. [03:15]. Only cite timestamps that appear at the start of an excerpt.
3. If the excerpts do not answer the question, reply with exactly: {NO_ANSWER}
4. Write the answer in {LANG_NAME.get(lang, "English")}. Be concise (1-5 sentences or a short bullet list). Use Markdown; put code in fenced code blocks.
5. Excerpts marked (ON SCREEN) describe text shown on screen rather than spoken; mention that when you use them."""


def qa_user_prompt(context: str, question: str) -> str:
    return f"""Excerpts from the video:
<<<
{context}
>>>

Question: {question}

Answer using only the excerpts, with [mm:ss] citations, or reply {NO_ANSWER}."""


def insights_prompt(lang: str, title: str, transcript: str, duration: str) -> str:
    language = LANG_NAME.get(lang, "English")
    return f"""Below is the timestamped transcript of the YouTube video "{title}" (length {duration}).

<<<
{transcript}
>>>

Return a JSON object with exactly these keys, all text written in {language}:
- "summary": 3-5 sentence summary of the whole video.
- "chapters": 3-10 chapters covering the video in order, each {{"start": "mm:ss", "title": "short title"}}. The first chapter starts at "00:00". Use timestamps that appear in the transcript.
- "questions": 5 short, specific questions a viewer could ask that the video answers.

Return only the JSON object."""


def notes_prompt(lang: str, transcript: str) -> str:
    return f"""Summarise this part of a video transcript as 4-8 bullet notes in {LANG_NAME.get(lang, "English")}. Start each bullet with the timestamp it refers to, copied from the transcript, e.g. "[03:15] ...".

<<<
{transcript}
>>>"""
