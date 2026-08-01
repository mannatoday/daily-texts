from __future__ import annotations

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
    lines: list[str] = []
    if content.psalm:
        lines.append(localize_reference(content.psalm))
    lines.extend(localize_reference(reading) for reading in content.readings)
    return lines
