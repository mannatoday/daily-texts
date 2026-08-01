from __future__ import annotations

from daily_texts.application.dto import FormattedOutput
from daily_texts.domain.models import LocalizedDailyText
from daily_texts.infrastructure.formatters._common import date_title


class MarkdownFormatter:
    format_name = "markdown"

    def format(
        self,
        content: LocalizedDailyText,
        *,
        include_source_link: bool = True,
    ) -> FormattedOutput:
        lines = [
            f"# {date_title(content)}",
            "",
            "## 舊約",
            "",
            f"{content.ot.text_zh}",
            "",
            f"— {content.ot.reference_zh}",
            "",
            "## 新約",
            "",
            f"{content.nt.text_zh}",
            "",
            f"— {content.nt.reference_zh}",
            "",
            "## 今日禱告",
            "",
            content.prayer_zh,
            "",
        ]
        if include_source_link:
            lines.extend(["## 原文連結", "", f"[Moravian Daily Texts]({content.source_url})", ""])

        return FormattedOutput(
            format="markdown",
            content="\n".join(lines).rstrip() + "\n",
            filename="daily-text.md",
        )
