from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_REF_PATTERN = re.compile(
    r"^(?P<book>\d?\s?[A-Za-z]+(?:\s+(?:of\s+)?[A-Za-z]+)?)\s+"
    r"(?P<chapter>\d+)"
    r"(?::(?P<verse>\d+)"
    r"(?:(?:[–-]|,\s*)"
    r"(?:(?P<end_chapter>\d+):(?P<end_verse>\d+)|(?P<end>\d+))"
    r")?"
    r")?"
    r"$",
)


@lru_cache(maxsize=1)
def _load_book_names_zh() -> dict[str, str]:
    path = Path(__file__).with_name("data") / "book_names_zh.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {key.lower(): value for key, value in data.items()}


def localize_reference(reference: str) -> str:
    """Convert English reference (e.g. 'Jeremiah 9:7') to Traditional Chinese."""
    cleaned = reference.strip().replace("–", "-").replace("—", "-")
    match = _REF_PATTERN.match(cleaned)
    if not match:
        return reference

    book = re.sub(r"\s+", " ", match.group("book").strip())
    name = _load_book_names_zh().get(book.lower())
    if not name:
        return reference

    chapter = match.group("chapter")
    verse = match.group("verse")
    if verse is None:
        return f"{name} {chapter}"

    end_chapter = match.group("end_chapter")
    end_verse = match.group("end_verse")
    end = match.group("end")
    if end_chapter and end_verse:
        span = f"{chapter}:{verse}–{end_chapter}:{end_verse}"
    elif end:
        span = f"{chapter}:{verse}–{end}"
    else:
        span = f"{chapter}:{verse}"
    return f"{name} {span}"
