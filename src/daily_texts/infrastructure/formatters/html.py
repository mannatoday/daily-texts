from __future__ import annotations

from html import escape

from daily_texts.application.dto import FormattedOutput
from daily_texts.domain.models import LocalizedDailyText
from daily_texts.infrastructure.formatters._common import date_title_zh, lectionary_lines


class HtmlFormatter:
    format_name = "html"

    def format(
        self,
        content: LocalizedDailyText,
        *,
        include_source_link: bool = True,
    ) -> FormattedOutput:
        title = escape(date_title_zh(content))
        lectionary = lectionary_lines(content)
        lectionary_block = ""
        if lectionary:
            refs = "\n".join(f"    <p>{escape(ref)}</p>" for ref in lectionary)
            lectionary_block = f"    <h2>經文選讀</h2>\n{refs}\n"

        source_block = ""
        if include_source_link:
            source_block = (
                "    <h2>原文連結</h2>\n"
                f'    <p><a href="{escape(content.source_url, quote=True)}">'
                "Moravian Daily Texts</a></p>\n"
            )

        body = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <title>{title}</title>
</head>
<body>
  <article>
    <h1>{title}</h1>
    <h2>舊約</h2>
    <p>{escape(content.ot.text_zh)}</p>
    <p>— {escape(content.ot.reference_zh)}</p>
    <h2>新約</h2>
    <p>{escape(content.nt.text_zh)}</p>
    <p>— {escape(content.nt.reference_zh)}</p>
    <h2>今日禱告</h2>
    <p>{escape(content.prayer_zh)}</p>
{lectionary_block}{source_block}  </article>
</body>
</html>
"""
        return FormattedOutput(
            format="html",
            content=body,
            filename="daily-text.html",
        )
