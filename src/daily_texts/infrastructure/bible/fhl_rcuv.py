from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from daily_texts.domain.exceptions import BibleLookupError
from daily_texts.infrastructure.config import Settings
from daily_texts.infrastructure.http import request_with_retries

logger = logging.getLogger(__name__)

_REF_PATTERN = re.compile(
    r"^(?P<book>\d?\s?[A-Za-z]+(?:\s+(?:of\s+)?[A-Za-z]+)?)\s+"
    r"(?P<chapter>\d+):(?P<verse>\d+)(?:(?:[–-]|,\s*)(?P<end>\d+))?$",
)


@dataclass(frozen=True)
class ParsedReference:
    book: str
    chineses: str
    chapter: int
    verse: str  # FHL sec format, e.g. "7" or "1-5"


@lru_cache(maxsize=1)
def _load_book_map() -> dict[str, str]:
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
    chineses = book_map.get(book.lower())
    if chineses is None:
        raise BibleLookupError(f"Unknown Bible book: {book!r}")

    chapter = int(match.group("chapter"))
    start = match.group("verse")
    end = match.group("end")
    verse = f"{start}-{end}" if end else start
    return ParsedReference(book=book, chineses=chineses, chapter=chapter, verse=verse)


def _strip_html(text: str) -> str:
    soup = BeautifulSoup(text, "html.parser")
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        tag.decompose()
    cleaned = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", cleaned).strip()


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

        # FHL qb.php reliably resolves books via `chineses` (中文書卷簡寫),
        # not `bid` (which can return the wrong book for some versions).
        url = f"{self._settings.fhl_api_base.rstrip('/')}/qb.php"
        params = {
            "chineses": parsed.chineses,
            "chap": parsed.chapter,
            "sec": parsed.verse,
            "version": version,
            "gb": 0,
        }
        try:
            response = await request_with_retries(
                self._client,
                "GET",
                url,
                max_retries=self._settings.http_max_retries,
                backoff_seconds=self._settings.http_retry_backoff_seconds,
                params=params,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise BibleLookupError(f"FHL API request failed for {reference}: {exc}") from exc

        if payload.get("status") != "success" or not payload.get("record"):
            raise BibleLookupError(f"FHL API returned no verses for {reference}")

        texts = [_strip_html(str(row.get("bible_text", ""))) for row in payload["record"]]
        joined = "".join(texts).strip()
        if not joined:
            raise BibleLookupError(f"Empty FHL response for {reference}")
        return joined
