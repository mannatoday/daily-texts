from __future__ import annotations

import asyncio
import csv
import logging
from datetime import date
from pathlib import Path

from daily_texts.domain.bible_versions import (
    DEFAULT_ENGLISH_VERSION,
    ENGLISH_LOOKUP_VERSIONS,
    ENGLISH_VERSIONS,
    FHL_VERSION_CODES,
    SITE_VERSIONS,
)
from daily_texts.domain.exceptions import BibleLookupError
from daily_texts.infrastructure.bible.cache import CachingBibleService

logger = logging.getLogger(__name__)


def _lookup_version(site_code: str) -> str | None:
    """Resolve a site version code to the string passed to BibleService.lookup.

    Mirrors ``FetchAndLocalizeDailyText._lookup_all_versions`` so the cache keys
    the backfill writes are the exact keys the daily run reads.
    """
    english = ENGLISH_LOOKUP_VERSIONS.get(site_code)
    if english:
        return english
    return FHL_VERSION_CODES.get(site_code)


def _site_codes() -> list[str]:
    return [code for code, _label in SITE_VERSIONS] + [
        code for code, _label in ENGLISH_VERSIONS
    ]


def _load_day_refs(days_csv: Path) -> list[tuple[str, dict[str, str]]]:
    with days_csv.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    out: list[tuple[str, dict[str, str]]] = []
    for row in rows:
        day = (row.get("date") or "").strip()
        if not day:
            continue
        refs = {
            "ot": (row.get("ot_ref") or "").strip(),
            "nt": (row.get("nt_ref") or "").strip(),
        }
        out.append((day, refs))
    return out


async def backfill_verse_cache(
    bible: CachingBibleService,
    days_csv: Path,
    *,
    start: date | None = None,
    end: date | None = None,
    delay_seconds: float = 0.3,
) -> list[tuple[str, str, str]]:
    """Fill the verse cache for every reference in the days table.

    Returns a list of ``(date, role, reference)`` tuples whose default English
    (NIV) text is still blank after the run, for manual versification review.
    Only the cache is written; no site pages are produced.
    """
    site_codes = _site_codes()
    days = _load_day_refs(days_csv)
    niv_blanks: list[tuple[str, str, str]] = []

    for day, refs in days:
        day_date = date.fromisoformat(day)
        if start is not None and day_date < start:
            continue
        if end is not None and day_date > end:
            continue
        for role, reference in refs.items():
            if not reference:
                continue
            for site_code in site_codes:
                version = _lookup_version(site_code)
                if not version:
                    continue
                already = bible.has_text(version, reference)
                try:
                    await bible.lookup(reference, version=version)
                except BibleLookupError as exc:
                    logger.warning(
                        "Backfill miss %s %s %s (%s): %s",
                        day,
                        role,
                        reference,
                        site_code,
                        exc,
                    )
                if not already and delay_seconds > 0:
                    await asyncio.sleep(delay_seconds)
            niv_version = ENGLISH_LOOKUP_VERSIONS[DEFAULT_ENGLISH_VERSION]
            if not bible.has_text(niv_version, reference):
                niv_blanks.append((day, role, reference))

    bible.save()
    return niv_blanks
