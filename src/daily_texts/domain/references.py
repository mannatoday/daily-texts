from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_REF_PATTERN = re.compile(
    r"^(?P<book>\d?\s?[A-Za-z]+(?:\s+(?:of\s+)?[A-Za-z]+)?)\s+"
    r"(?P<chapter>\d+):(?P<verse>\d+)(?:[–-](?P<end>\d+))?$",
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
    start = match.group("verse")
    end = match.group("end")
    verse = f"{start}–{end}" if end else start
    return f"{name} {chapter}:{verse}"
