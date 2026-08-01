from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import httpx

from daily_texts.domain.exceptions import BibleLookupError
from daily_texts.infrastructure.config import Settings

logger = logging.getLogger(__name__)

_REF_PATTERN = re.compile(
    r"^(?P<book>\d?\s?[A-Za-z]+(?:\s+of\s+[A-Za-z]+)?)\s+"
    r"(?P<chapter>\d+):(?P<verse>\d+)(?:[–-](?P<end>\d+))?$",
)


@dataclass(frozen=True)
class ParsedReference:
    book: str
    bid: int
    chapter: int
    verse: str  # FHL sec format, e.g. "7" or "1-5"


@lru_cache(maxsize=1)
def _load_book_map() -> dict[str, int]:
    path = Path(__file__).with_name("book_map.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    return {key.lower(): value for key, value in data.items()}


def parse_reference(reference: str) -> ParsedReference:
    cleaned = reference.strip().replace("–", "-").replace("—", "-")
    match = _REF_PATTERN.match(cleaned)
    if not match:
        raise BibleLookupError(f"Unable to parse Bible reference: {reference!r}")

    book = re.sub(r"\s+", " ", match.group("book").strip())
    book_map = _load_book_map()
    bid = book_map.get(book.lower())
    if bid is None:
        raise BibleLookupError(f"Unknown Bible book: {book!r}")

    chapter = int(match.group("chapter"))
    start = match.group("verse")
    end = match.group("end")
    verse = f"{start}-{end}" if end else start
    return ParsedReference(book=book, bid=bid, chapter=chapter, verse=verse)


class FhlRcuvBibleService:
    """Lookup Traditional Chinese RCUV text via the FHL Bible JSON API."""

    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    async def lookup(self, reference: str, *, version: str = "rcuv") -> str:
        version = version or self._settings.bible_version
        try:
            parsed = parse_reference(reference)
        except BibleLookupError:
            logger.warning("Could not parse reference %r", reference)
            raise

        url = f"{self._settings.fhl_api_base.rstrip('/')}/qb.php"
        params = {
            "bid": parsed.bid,
            "chap": parsed.chapter,
            "sec": parsed.verse,
            "version": version,
            "gb": 0,
        }
        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise BibleLookupError(f"FHL API request failed for {reference}: {exc}") from exc

        if payload.get("status") != "success" or not payload.get("record"):
            raise BibleLookupError(f"FHL API returned no verses for {reference}")

        texts = [str(row.get("bible_text", "")).strip() for row in payload["record"]]
        joined = "".join(texts).strip()
        if not joined:
            raise BibleLookupError(f"Empty FHL response for {reference}")
        return joined
