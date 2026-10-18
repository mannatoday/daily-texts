"""Build a daily text from the offline Oct–Dec tables.

Watchword references come from the days CSV. Chinese verse text is filled later
by the existing Bible lookup. Lectionary references come from the lectionary
CSV. The week watchword is not in these tables, so that field stays empty.
"""
from __future__ import annotations

import csv
import re
from datetime import date
from functools import lru_cache
from pathlib import Path

from daily_texts.domain.church_year import church_day_label_zh
from daily_texts.domain.exceptions import ProviderError
from daily_texts.domain.models import RawDailyText, Watchword

_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_DAYS_CSV = _PACKAGE_ROOT / "inputs" / "dataset" / "days_2026_q4.csv"
_LECTIONARY_CSV = _PACKAGE_ROOT / "inputs" / "dataset" / "lectionary_2026_q4.csv"
_SOURCES_CSV = _PACKAGE_ROOT / "inputs" / "third_text" / "sources.csv"
_CJK = re.compile(r"[\u4e00-\u9fff]")
_CJK_RUN = re.compile(r"[\u4e00-\u9fff]+")
_PAREN = re.compile(r"\s*\([^)]*\)")


class DatasetProvider:
    source_name = "dataset"

    def __init__(
        self,
        days_path: Path | None = None,
        sources_path: Path | None = None,
        lectionary_path: Path | None = None,
    ) -> None:
        self._days = _load_csv(days_path or _DAYS_CSV, "date")
        self._sources = _load_csv(sources_path or _SOURCES_CSV, "id")
        self._lectionary = _load_csv(lectionary_path or _LECTIONARY_CSV, "date")

    async def fetch(self, target_date: date | None = None) -> RawDailyText:
        day = target_date or date.today()
        row = self._days.get(day.isoformat())
        if row is None:
            raise ProviderError(f"No dataset row for {day.isoformat()}")

        source_id = (row.get("third_text_id") or "").strip()
        source = self._sources.get(source_id) if source_id else None
        if source_id and source is None:
            raise ProviderError(f"Unknown third_text_id {source_id!r} for {day.isoformat()}")

        prayer, prayer_lang = _prayer_text(source_id, source)
        psalm, readings = _lectionary_refs(self._lectionary.get(day.isoformat()))
        metadata: dict[str, str] = {
            "provider": self.source_name,
            "plan_year": row.get("plan_year", ""),
            "track": row.get("track", ""),
            "church_day": row.get("church_day", ""),
            "church_year_label": church_day_label_zh(row.get("church_day", "")),
            "third_text_id": source_id,
            "prayer_lang": prayer_lang,
        }
        if source is not None:
            metadata["third_text_work"] = source.get("work", "")
        citation = _prayer_citation(source)
        if citation:
            metadata["prayer_citation"] = citation

        return RawDailyText(
            date=day,
            date_display=day.strftime("%A, %B %-d, %Y"),
            psalm=psalm,
            readings=readings,
            ot=Watchword(reference=row["ot_ref"].strip(), text_en=""),
            nt=Watchword(reference=row["nt_ref"].strip(), text_en=""),
            week_watchword=None,
            prayer_en=prayer,
            source_url=f"dataset://days_2026_q4/{day.isoformat()}",
            metadata=metadata,
        )


def _lectionary_refs(row: dict[str, str] | None) -> tuple[str | None, list[str]]:
    if not row:
        return None, []
    psalm = (row.get("psalm") or "").strip() or None
    epistle = (row.get("epistle") or "").strip()
    ordered = [row.get("ot_reading", ""), epistle, row.get("nt_reading", "")]
    return psalm, [part.strip() for part in ordered if part.strip()]


def _prayer_citation(source: dict[str, str] | None) -> str:
    if not source:
        return ""
    work = source.get("work", "").strip()
    author = _PAREN.sub("", source.get("author", "")).split("；")[0].strip()
    if not work:
        return author
    if not author or author in {"—", "-"} or any(token in author for token in ("傳統", "禮儀", "早期")):
        return work
    names = _CJK_RUN.findall(author)
    if names:
        author = max(names, key=len)
    return f"{author}〈{work}〉"


def _prayer_text(source_id: str, source: dict[str, str] | None) -> tuple[str, str]:
    excerpt = (source or {}).get("text_zh_excerpt", "").strip()
    if excerpt and _CJK.search(excerpt):
        return excerpt, "zh"
    if excerpt:
        return excerpt, "en"
    label = source_id or "未配對"
    return f"（第三段待補原文：{label}）", "zh"


@lru_cache(maxsize=8)
def _load_csv(path: Path, key: str) -> dict[str, dict[str, str]]:
    if not path.is_file():
        raise ProviderError(f"Dataset file not found: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    indexed: dict[str, dict[str, str]] = {}
    for row in rows:
        row_key = (row.get(key) or "").strip()
        if row_key:
            indexed[row_key] = row
    return indexed
