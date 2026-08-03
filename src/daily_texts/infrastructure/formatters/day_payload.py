from __future__ import annotations

from daily_texts.domain.bible_versions import DEFAULT_VERSION, SITE_VERSIONS
from daily_texts.domain.models import LocalizedDailyText, LocalizedWatchword
from daily_texts.infrastructure.formatters._common import lectionary_entries


def watchword_payload(watchword: LocalizedWatchword | None) -> dict | None:
    if watchword is None:
        return None
    translations = dict(watchword.translations)
    if not translations and watchword.text_zh:
        translations = {DEFAULT_VERSION: watchword.text_zh}
    return {
        "reference": watchword.reference,
        "reference_zh": watchword.reference_zh,
        "translations": translations,
    }


def day_payload(content: LocalizedDailyText) -> dict:
    """JSON-serializable payload embedded in site HTML for client-side version switching."""
    return {
        "date": content.date.isoformat(),
        "default_version": DEFAULT_VERSION,
        "versions": [{"code": code, "label": label} for code, label in SITE_VERSIONS],
        "week_watchword": watchword_payload(content.week_watchword),
        "ot": watchword_payload(content.ot),
        "nt": watchword_payload(content.nt),
        "prayer": content.prayer_zh,
        "readings": [
            {"reference": en, "reference_zh": zh} for zh, en in lectionary_entries(content)
        ],
        "source_url": content.source_url,
    }
