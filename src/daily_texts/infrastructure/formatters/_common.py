from __future__ import annotations

from urllib.parse import quote

from daily_texts.domain.models import LocalizedDailyText
from daily_texts.domain.references import localize_reference

_WEEKDAYS_ZH = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")


def date_title_zh(content: LocalizedDailyText) -> str:
    """Chinese date like ``2026 年 8 月 1 日（星期六）``."""
    day = content.date
    title = f"{day.year} 年 {day.month} 月 {day.day} 日（{_WEEKDAYS_ZH[day.weekday()]}）"
    church = content.metadata.get("church_year_label")
    if church:
        return f"{title}（{church}）"
    return title


def lectionary_lines(content: LocalizedDailyText) -> list[str]:
    return [zh for zh, _en in lectionary_entries(content)]


def lectionary_entries(content: LocalizedDailyText) -> list[tuple[str, str]]:
    """Return ``(zh_label, english_reference)`` pairs for lectionary readings."""
    entries: list[tuple[str, str]] = []
    if content.psalm:
        entries.append((localize_reference(content.psalm), content.psalm))
    for reading in content.readings:
        entries.append((localize_reference(reading), reading))
    return entries


def biblegateway_cuv_url(reference: str) -> str:
    """Bible Gateway link for Traditional Chinese Union Version (和合本)."""
    cleaned = reference.strip().replace("–", "-").replace("—", "-")
    return (
        "https://www.biblegateway.com/passage/"
        f"?search={quote(cleaned)}&version=CUV"
    )
