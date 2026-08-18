from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

# Book name followed by chapter and an optional verse spec that may contain
# ranges, cross-chapter ranges, and comma-separated segments,
# e.g. "Psalm 145:8-9,14-21" or "Joshua 8:30-9:27".
_REF_PATTERN = re.compile(
    r"^(?P<book>\d?\s?[A-Za-z]+(?:\s+(?:of\s+)?[A-Za-z]+)?)\s+"
    r"(?P<rest>\d+(?::\d+(?:-\d+(?::\d+)?)?(?:,\s*\d+(?:-\d+(?::\d+)?)?)*)?)"
    r"$",
)
# Cross-book lectionary span, e.g. "Joshua 24:14–Judges 1:16".
_CROSS_BOOK_REF = re.compile(
    r"^(?P<book1>\d?\s?[A-Za-z]+(?:\s+(?:of\s+)?[A-Za-z]+)?)\s+"
    r"(?P<rest1>\d+:\d+)\s*[-–—]\s*"
    r"(?P<book2>\d?\s?[A-Za-z]+(?:\s+(?:of\s+)?[A-Za-z]+)?)\s+"
    r"(?P<rest2>\d+(?::\d+)?)$",
)


@lru_cache(maxsize=1)
def _load_book_names_zh() -> dict[str, str]:
    path = Path(__file__).with_name("data") / "book_names_zh.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {key.lower(): value for key, value in data.items()}


def _book_zh(book: str) -> str | None:
    book = re.sub(r"\s+", " ", book.strip())
    return _load_book_names_zh().get(book.lower())


def localize_reference(reference: str) -> str:
    """Convert English reference (e.g. 'Jeremiah 9:7') to Traditional Chinese."""
    cleaned = reference.strip().replace("–", "-").replace("—", "-")

    cross = _CROSS_BOOK_REF.match(cleaned)
    if cross:
        name1 = _book_zh(cross.group("book1"))
        name2 = _book_zh(cross.group("book2"))
        if name1 and name2:
            rest1 = re.sub(r"\s+", "", cross.group("rest1"))
            rest2 = re.sub(r"\s+", "", cross.group("rest2"))
            return f"{name1} {rest1}–{name2} {rest2}"
        return reference

    match = _REF_PATTERN.match(cleaned)
    if not match:
        return reference

    name = _book_zh(match.group("book"))
    if not name:
        return reference

    rest = re.sub(r"\s+", "", match.group("rest"))
    # Shorthand "5:16,17" (single comma, plain verses) means the range 16–17.
    pair = re.fullmatch(r"(\d+):(\d+),(\d+)", rest)
    if pair:
        rest = f"{pair.group(1)}:{pair.group(2)}-{pair.group(3)}"
    return f"{name} {rest.replace('-', '–')}"
