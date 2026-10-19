from __future__ import annotations

import logging
import re
from urllib.parse import quote

import httpx

from daily_texts.application.ports.bible import BibleService
from daily_texts.domain.exceptions import BibleLookupError
from daily_texts.infrastructure.config import Settings
from daily_texts.infrastructure.http import request_with_retries

logger = logging.getLogger(__name__)


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class EsvBibleService:
    """Lookup ESV text via the Crossway ESV API."""

    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    async def lookup(self, reference: str) -> str:
        token = self._settings.esv_api_key.strip()
        if not token:
            raise BibleLookupError("ESV_API_KEY is not set")

        url = f"{self._settings.esv_api_base.rstrip('/')}/passage/text/"
        params = {
            "q": reference.strip(),
            "include-headings": "false",
            "include-footnotes": "false",
            "include-footnote-body": "false",
            "include-verse-numbers": "false",
            "include-short-copyright": "false",
            "include-passage-references": "false",
            "include-first-verse-numbers": "false",
            "include-passage-horizontal-whitespace": "false",
            "include-heading-horizontal-whitespace": "false",
        }
        try:
            response = await request_with_retries(
                self._client,
                "GET",
                url,
                max_retries=self._settings.http_max_retries,
                backoff_seconds=self._settings.http_retry_backoff_seconds,
                params=params,
                headers={"Authorization": f"Token {token}"},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise BibleLookupError(f"ESV API request failed for {reference}: {exc}") from exc

        passages = payload.get("passages") if isinstance(payload, dict) else None
        if not passages:
            raise BibleLookupError(f"ESV API returned no text for {reference}")
        text = _collapse(str(passages[0]))
        if not text:
            raise BibleLookupError(f"Empty ESV response for {reference}")
        return text


class KjvBibleService:
    """Lookup public-domain KJV text via bible-api.com."""

    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    async def lookup(self, reference: str) -> str:
        cleaned = reference.strip()
        url = f"{self._settings.kjv_api_base.rstrip('/')}/{quote(cleaned, safe='')}"
        try:
            response = await request_with_retries(
                self._client,
                "GET",
                url,
                max_retries=self._settings.http_max_retries,
                backoff_seconds=self._settings.http_retry_backoff_seconds,
                params={"translation": "kjv"},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise BibleLookupError(f"KJV API request failed for {reference}: {exc}") from exc

        if not isinstance(payload, dict) or not payload.get("text"):
            raise BibleLookupError(f"KJV API returned no text for {reference}")
        text = _collapse(str(payload["text"]))
        if not text:
            raise BibleLookupError(f"Empty KJV response for {reference}")
        return text


class RoutingBibleService:
    """Send Chinese lookups to FHL and English lookups to their sources."""

    def __init__(
        self,
        fhl: BibleService,
        esv: EsvBibleService,
        kjv: KjvBibleService,
        api_bible: ApiBibleService,
    ) -> None:
        self._fhl = fhl
        self._esv = esv
        self._kjv = kjv
        self._api_bible = api_bible

    async def lookup(self, reference: str, *, version: str = "rcuv") -> str:
        key = version.lower()
        if key == "esv":
            return await self._esv.lookup(reference)
        if key == "kjv":
            return await self._kjv.lookup(reference)
        if key in ApiBibleService.VERSIONS:
            return await self._api_bible.lookup(reference, version=key)
        return await self._fhl.lookup(reference, version=version)

    def fums_token(self, version: str, reference: str) -> str:
        return self._api_bible.fums_token(version, reference)


# USFM book ids used by API.Bible passage ids.
_USFM_BOOKS = {
    "genesis": "GEN",
    "exodus": "EXO",
    "leviticus": "LEV",
    "numbers": "NUM",
    "deuteronomy": "DEU",
    "joshua": "JOS",
    "judges": "JDG",
    "ruth": "RUT",
    "1 samuel": "1SA",
    "2 samuel": "2SA",
    "1 kings": "1KI",
    "2 kings": "2KI",
    "1 chronicles": "1CH",
    "2 chronicles": "2CH",
    "ezra": "EZR",
    "nehemiah": "NEH",
    "esther": "EST",
    "job": "JOB",
    "psalm": "PSA",
    "psalms": "PSA",
    "proverbs": "PRO",
    "ecclesiastes": "ECC",
    "song of solomon": "SNG",
    "song of songs": "SNG",
    "isaiah": "ISA",
    "jeremiah": "JER",
    "lamentations": "LAM",
    "ezekiel": "EZK",
    "daniel": "DAN",
    "hosea": "HOS",
    "joel": "JOL",
    "amos": "AMO",
    "obadiah": "OBA",
    "jonah": "JON",
    "micah": "MIC",
    "nahum": "NAM",
    "habakkuk": "HAB",
    "zephaniah": "ZEP",
    "haggai": "HAG",
    "zechariah": "ZEC",
    "malachi": "MAL",
    "matthew": "MAT",
    "mark": "MRK",
    "luke": "LUK",
    "john": "JHN",
    "acts": "ACT",
    "romans": "ROM",
    "1 corinthians": "1CO",
    "2 corinthians": "2CO",
    "galatians": "GAL",
    "ephesians": "EPH",
    "philippians": "PHP",
    "colossians": "COL",
    "1 thessalonians": "1TH",
    "2 thessalonians": "2TH",
    "1 timothy": "1TI",
    "2 timothy": "2TI",
    "titus": "TIT",
    "philemon": "PHM",
    "hebrews": "HEB",
    "james": "JAS",
    "1 peter": "1PE",
    "2 peter": "2PE",
    "1 john": "1JN",
    "2 john": "2JN",
    "3 john": "3JN",
    "jude": "JUD",
    "revelation": "REV",
}

_REFERENCE = re.compile(
    r"^(?P<book>(?:\d\s+)?[A-Za-z]+(?:\s+[A-Za-z]+)*)\s+"
    r"(?P<chapter>\d+):(?P<verse>\d+)"
    r"(?:\s*(?P<sep>[-–—,])\s*(?:(?P<end_chapter>\d+):)?(?P<end>\d+))?$"
)


def passage_ids(reference: str) -> list[str]:
    """Turn an English reference into one or more API.Bible passage ids."""
    cleaned = reference.strip().replace("–", "-").replace("—", "-")
    match = _REFERENCE.match(cleaned)
    if not match:
        raise BibleLookupError(f"Unable to parse Bible reference: {reference!r}")
    book = re.sub(r"\s+", " ", match.group("book").strip()).lower()
    usfm = _USFM_BOOKS.get(book)
    if usfm is None:
        raise BibleLookupError(f"Unknown Bible book: {match.group('book')!r}")
    chapter = int(match.group("chapter"))
    verse = int(match.group("verse"))
    end = match.group("end")
    if not end:
        return [f"{usfm}.{chapter}.{verse}"]
    end_verse = int(end)
    end_chapter = int(match.group("end_chapter") or chapter)
    sep = match.group("sep")
    start_id = f"{usfm}.{chapter}.{verse}"
    end_id = f"{usfm}.{end_chapter}.{end_verse}"
    # A comma that skips a verse (Psalm 103:2,4) must not pull the verse between.
    if sep == "," and end_chapter == chapter and end_verse != verse + 1:
        return [start_id, end_id]
    if start_id == end_id:
        return [start_id]
    return [f"{start_id}-{end_id}"]


class ApiBibleService:
    """Lookup NIV, NLT, and NIrV through API.Bible."""

    VERSIONS = ("niv", "nlt", "nirv")
    _ABBR = {"niv": "NIV", "nlt": "NLT", "nirv": "NIRV"}

    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings
        self._bible_ids: dict[str, str] = {}
        self._fums: dict[tuple[str, str], str] = {}

    def fums_token(self, version: str, reference: str) -> str:
        return self._fums.get((version.lower(), reference.strip()), "")

    async def lookup(self, reference: str, *, version: str) -> str:
        key = version.lower()
        if key not in self.VERSIONS:
            raise BibleLookupError(f"API.Bible does not serve {version}")
        token = self._settings.api_bible_api_key.strip()
        if not token:
            raise BibleLookupError("API_BIBLE_API_KEY is not set")
        bible_id = await self._bible_id(key, token)
        parts: list[str] = []
        fums: list[str] = []
        for passage_id in passage_ids(reference):
            text, fums_token = await self._passage(bible_id, passage_id, token, reference)
            parts.append(text)
            if fums_token:
                fums.append(fums_token)
        joined = _collapse(" ".join(parts))
        if not joined:
            raise BibleLookupError(f"Empty API.Bible response for {reference}")
        self._fums[(key, reference.strip())] = " ".join(fums)
        return joined

    async def _bible_id(self, version: str, token: str) -> str:
        cached = self._bible_ids.get(version)
        if cached:
            return cached
        if not self._bible_ids:
            url = f"{self._settings.api_bible_api_base.rstrip('/')}/bibles"
            try:
                response = await request_with_retries(
                    self._client,
                    "GET",
                    url,
                    max_retries=self._settings.http_max_retries,
                    backoff_seconds=self._settings.http_retry_backoff_seconds,
                    params={"language": "eng"},
                    headers={"api-key": token},
                )
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise BibleLookupError(f"API.Bible bible list failed: {exc}") from exc
            bibles = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(bibles, list):
                raise BibleLookupError("API.Bible returned no bible list")
            for code, abbr in self._ABBR.items():
                match = _match_bible(bibles, abbr)
                if match:
                    self._bible_ids[code] = match
        found = self._bible_ids.get(version)
        if not found:
            raise BibleLookupError(
                f"API.Bible account has no {self._ABBR[version]} bible"
            )
        return found

    async def _passage(
        self,
        bible_id: str,
        passage_id: str,
        token: str,
        reference: str,
    ) -> tuple[str, str]:
        url = (
            f"{self._settings.api_bible_api_base.rstrip('/')}"
            f"/bibles/{bible_id}/passages/{passage_id}"
        )
        params = {
            "content-type": "text",
            "include-notes": "false",
            "include-titles": "false",
            "include-chapter-numbers": "false",
            "include-verse-numbers": "false",
            "include-verse-spans": "false",
        }
        try:
            response = await request_with_retries(
                self._client,
                "GET",
                url,
                max_retries=self._settings.http_max_retries,
                backoff_seconds=self._settings.http_retry_backoff_seconds,
                params=params,
                headers={"api-key": token},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise BibleLookupError(
                f"API.Bible request failed for {reference}: {exc}"
            ) from exc
        data = payload.get("data") if isinstance(payload, dict) else None
        content = data.get("content") if isinstance(data, dict) else None
        text = _plain(str(content or ""))
        if not text:
            raise BibleLookupError(f"API.Bible returned no text for {reference}")
        meta = payload.get("meta") if isinstance(payload, dict) else None
        fums = ""
        if isinstance(meta, dict):
            fums = str(meta.get("fumsToken") or "").strip()
        return text, fums


def _plain(text: str) -> str:
    stripped = re.sub(r"<[^>]+>", " ", text)
    return _collapse(stripped.replace("\u00a0", " "))


def _match_bible(bibles: list[dict], abbreviation: str) -> str | None:
    wanted = abbreviation.upper()
    loose: str | None = None
    for bible in bibles:
        if not isinstance(bible, dict) or not bible.get("id"):
            continue
        abbr = re.sub(r"[^A-Za-z0-9]", "", str(bible.get("abbreviation") or "")).upper()
        name = str(bible.get("name") or "").lower()
        if abbr == wanted:
            if wanted == "NIV" and "reader" in name:
                continue
            return str(bible["id"])
        if wanted == "NIRV" and "reader" in name and "international" in name:
            loose = loose or str(bible["id"])
        elif (
            wanted == "NIV"
            and abbr.startswith("NIV")
            and "reader" not in name
            and "uk" not in name
        ):
            loose = loose or str(bible["id"])
    return loose
