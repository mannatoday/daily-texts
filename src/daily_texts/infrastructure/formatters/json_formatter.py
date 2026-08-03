from __future__ import annotations

import json

from daily_texts.application.dto import FormattedOutput
from daily_texts.domain.models import LocalizedDailyText
from daily_texts.infrastructure.formatters._common import lectionary_lines


class JsonFormatter:
    format_name = "json"

    def format(
        self,
        content: LocalizedDailyText,
        *,
        include_source_link: bool = True,
    ) -> FormattedOutput:
        payload: dict[str, object] = {
            "date": content.date.isoformat(),
            "ot": content.ot.text_zh,
            "ot_reference": content.ot.reference_zh,
            "nt": content.nt.text_zh,
            "nt_reference": content.nt.reference_zh,
            "prayer": content.prayer_zh,
            "readings": lectionary_lines(content),
        }
        if content.week_watchword is not None:
            payload["week_watchword"] = content.week_watchword.text_zh
            payload["week_watchword_reference"] = content.week_watchword.reference_zh
        if include_source_link:
            payload["source_url"] = content.source_url

        return FormattedOutput(
            format="json",
            content=json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            filename="daily-text.json",
        )
