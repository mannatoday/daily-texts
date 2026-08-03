from __future__ import annotations

import json

from daily_texts.application.dto import FormattedOutput
from daily_texts.domain.models import LocalizedDailyText
from daily_texts.infrastructure.formatters.day_payload import day_payload


class JsonFormatter:
    format_name = "json"

    def format(
        self,
        content: LocalizedDailyText,
        *,
        include_source_link: bool = True,
    ) -> FormattedOutput:
        payload = day_payload(content)
        if not include_source_link:
            payload.pop("source_url", None)

        return FormattedOutput(
            format="json",
            content=json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            filename="daily-text.json",
        )
