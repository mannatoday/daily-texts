from __future__ import annotations

from daily_texts.application.dto import FormattedOutput
from daily_texts.domain.models import LocalizedDailyText
from daily_texts.infrastructure.formatters._common import date_title


class HtmlFormatter:
    format_name = "html"

    def format(
        self,
        content: LocalizedDailyText,
        *,
        include_source_link: bool = True,
    ) -> FormattedOutput:
        source_block = ""
        if include_source_link:
            source_block = (
                "<h2>原文連結</h2>\n"
                f'<p><a href="{content.source_url}">Moravian Daily Texts</a></p>\n'
            )

        body = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <title>{date_title(content)}</title>
</head>
<body>
  <article>
    <h1>{date_title(content)}</h1>
    <h2>舊約</h2>
    <p>{content.ot.text_zh}</p>
    <p>— {content.ot.reference_zh}</p>
    <h2>新約</h2>
    <p>{content.nt.text_zh}</p>
    <p>— {content.nt.reference_zh}</p>
    <h2>今日禱告</h2>
    <p>{content.prayer_zh}</p>
    {source_block}
  </article>
</body>
</html>
"""
        return FormattedOutput(
            format="html",
            content=body,
            filename="daily-text.html",
        )
