from __future__ import annotations

from daily_texts.application.dto import FormattedOutput
from daily_texts.domain.models import LocalizedDailyText
from daily_texts.infrastructure.formatters._common import date_title_zh, lectionary_lines


class PlainTextFormatter:
    format_name = "text"

    def format(
        self,
        content: LocalizedDailyText,
        *,
        include_source_link: bool = True,
    ) -> FormattedOutput:
        lines = [date_title_zh(content), ""]
        if content.week_watchword is not None:
            lines.extend(
                [
                    "【本週守望經文】",
                    content.week_watchword.text_zh,
                    f"— {content.week_watchword.reference_zh}",
                    "",
                ]
            )
        lines += [
            "【舊約】",
            content.ot.text_zh,
            f"— {content.ot.reference_zh}",
            "",
            "【新約】",
            content.nt.text_zh,
            f"— {content.nt.reference_zh}",
            "",
            "【今日禱告】",
            content.prayer_zh,
            "",
        ]
        lectionary = lectionary_lines(content)
        if lectionary:
            lines.extend(["【經文選讀】", *lectionary, ""])
        if include_source_link:
            lines.extend(["【原文連結】", content.source_url, ""])

        return FormattedOutput(
            format="text",
            content="\n".join(lines).rstrip() + "\n",
            filename="daily-text.txt",
        )
