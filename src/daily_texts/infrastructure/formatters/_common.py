from __future__ import annotations

from daily_texts.domain.models import LocalizedDailyText


def date_title(content: LocalizedDailyText) -> str:
    church = content.metadata.get("church_year_label")
    if church:
        return f"{content.date_display}（{church}）"
    return content.date_display
