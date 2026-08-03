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

    rest = re.sub(r"\s+", "", match.group("rest"))
    # Shorthand "5:16,17" (single comma, plain verses) means the range 16–17.
    pair = re.fullmatch(r"(\d+):(\d+),(\d+)", rest)
    if pair:
        rest = f"{pair.group(1)}:{pair.group(2)}-{pair.group(3)}"
    return f"{name} {rest.replace('-', '–')}"
