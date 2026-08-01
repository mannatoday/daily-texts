from __future__ import annotations

import logging
import re
from datetime import date
from html import escape
from pathlib import Path

from daily_texts.application.dto import FormattedOutput, PublishResult
from daily_texts.domain.models import LocalizedDailyText
from daily_texts.infrastructure.formatters.html import HtmlFormatter

logger = logging.getLogger(__name__)

_DAY_PAGE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.html$")


class StaticSitePublisher:
    """Write dated HTML pages under SITE_DIR for GitHub Pages deploy."""

    channel = "static_site"

    def __init__(self, site_dir: Path | None = None) -> None:
        self._site_dir = Path(site_dir) if site_dir is not None else Path("./site")
        self._html = HtmlFormatter()

    async def publish(
        self,
        outputs: list[FormattedOutput],
        content: LocalizedDailyText,
    ) -> PublishResult:
        self._site_dir.mkdir(parents=True, exist_ok=True)
        day_name = f"{content.date.isoformat()}.html"
        day_path = self._site_dir / day_name

        page = self._html.format(content, include_source_link=True)
        day_path.write_text(page.content, encoding="utf-8")

        index_path = self._site_dir / "index.html"
        index_path.write_text(self._build_index(), encoding="utf-8")

        message = f"Wrote {day_path} and updated {index_path}"
        logger.info(message)
        return PublishResult(channel=self.channel, success=True, message=message)

    def _list_day_pages(self) -> list[date]:
        days: list[date] = []
        if not self._site_dir.is_dir():
            return days
        for path in self._site_dir.iterdir():
            match = _DAY_PAGE.match(path.name)
            if match and path.is_file():
                days.append(date.fromisoformat(match.group(1)))
        days.sort(reverse=True)
        return days

    def _build_index(self) -> str:
        days = self._list_day_pages()
        if not days:
            body = "    <p>尚無每日經文。</p>\n"
        else:
            latest = days[0]
            items = "\n".join(
                f'      <li><a href="{d.isoformat()}.html">{escape(d.isoformat())}</a></li>'
                for d in days
            )
            body = (
                f'    <p class="latest">最新：'
                f'<a href="{latest.isoformat()}.html">{escape(latest.isoformat())}</a></p>\n'
                f"    <ul>\n{items}\n    </ul>\n"
            )

        return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>每日經文</title>
</head>
<body>
  <main>
    <h1>每日經文</h1>
{body}  </main>
</body>
</html>
"""
