from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Watchword(BaseModel):
    reference: str
    text_en: str
    bible_url: str | None = None


class RawDailyText(BaseModel):
    date: date
    date_display: str
    psalm: str | None = None
    readings: list[str] = Field(default_factory=list)
    ot: Watchword
    nt: Watchword
    # Sunday layouts add a weekly watchword above the daily ones.
    week_watchword: Watchword | None = None
    prayer_en: str
    source_url: str
    fetched_at: datetime = Field(default_factory=_utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LocalizedWatchword(BaseModel):
    reference: str
    reference_zh: str
    text_en: str
    text_zh: str
    # site version code → Chinese (or English fallback) text
    translations: dict[str, str] = Field(default_factory=dict)
    bible_url: str | None = None


class LocalizedDailyText(BaseModel):
    date: date
    date_display: str
    psalm: str | None = None
    readings: list[str] = Field(default_factory=list)
    ot: LocalizedWatchword
    nt: LocalizedWatchword
    week_watchword: LocalizedWatchword | None = None
    prayer_en: str
    prayer_zh: str
    source_url: str
    metadata: dict[str, Any] = Field(default_factory=dict)
