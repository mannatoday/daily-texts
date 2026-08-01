from __future__ import annotations

import logging
import re
from datetime import date
from html import escape
from pathlib import Path

from daily_texts.application.dto import FormattedOutput, PublishResult
from daily_texts.domain.models import LocalizedDailyText
from daily_texts.infrastructure.formatters.html import HtmlFormatter, load_devotional_css

logger = logging.getLogger(__name__)

_DAY_PAGE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.html$")
_FONT_LINKS = """\
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500&family=Noto+Serif+TC:wght@400;500&display=swap" rel="stylesheet" />
"""


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
        self._write_stylesheet()

        days_before = self._list_day_pages()
        # Include today so nav neighbors resolve even on first write.
        days = sorted(set(days_before) | {content.date}, reverse=True)

        prev_href, next_href = _neighbors(content.date, days)
        page = self._html.format(
            content,
            include_source_link=True,
            stylesheet_href="styles.css",
            prev_href=prev_href,
            next_href=next_href,
            home_href="index.html",
        )
        day_path = self._site_dir / f"{content.date.isoformat()}.html"
        day_path.write_text(page.content, encoding="utf-8")

        self._refresh_neighbor_nav(content.date, days)
        index_path = self._site_dir / "index.html"
        index_path.write_text(self._build_index(days), encoding="utf-8")

        message = f"Wrote {day_path} and updated {index_path}"
        logger.info(message)
        return PublishResult(channel=self.channel, success=True, message=message)

    def _write_stylesheet(self) -> None:
        css_path = self._site_dir / "styles.css"
        css_path.write_text(load_devotional_css() + "\n", encoding="utf-8")

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

    def _refresh_neighbor_nav(self, current: date, days: list[date]) -> None:
        """Update prev/next links on adjacent day pages after insert/overwrite."""
        chronological = sorted(days)
        if current not in chronological:
            return
        idx = chronological.index(current)
        for neighbor_idx in (idx - 1, idx + 1):
            if neighbor_idx < 0 or neighbor_idx >= len(chronological):
                continue
            neighbor = chronological[neighbor_idx]
            path = self._site_dir / f"{neighbor.isoformat()}.html"
            if not path.is_file():
                continue
            prev_href, next_href = _neighbors(neighbor, days)
            html = path.read_text(encoding="utf-8")
            updated = _replace_day_nav(html, prev_href, next_href)
            if updated != html:
                path.write_text(updated, encoding="utf-8")

    def _build_index(self, days: list[date] | None = None) -> str:
        days = days if days is not None else self._list_day_pages()
        if not days:
            body = '    <p class="empty">尚無每日經文。</p>\n'
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
  <meta name="color-scheme" content="light dark" />
  <title>每日經文</title>
{_FONT_LINKS}  <link rel="stylesheet" href="styles.css" />
</head>
<body>
  <div class="site-shell site-index">
    <h1>每日經文</h1>
    <p class="lede">安靜閱讀 · 每日一句</p>
{body}    <footer class="site-foot">Daily Texts</footer>
  </div>
</body>
</html>
"""


def _neighbors(day: date, days_newest_first: list[date]) -> tuple[str | None, str | None]:
    chronological = sorted(days_newest_first)
    if day not in chronological:
        return None, None
    idx = chronological.index(day)
    prev_day = chronological[idx - 1] if idx > 0 else None
    next_day = chronological[idx + 1] if idx + 1 < len(chronological) else None
    # Reading order: 前一日 = older, 後一日 = newer
    prev_href = f"{prev_day.isoformat()}.html" if prev_day else None
    next_href = f"{next_day.isoformat()}.html" if next_day else None
    return prev_href, next_href


_NAV_BLOCK = re.compile(
    r'<nav class="day-nav"[^>]*>.*?</nav>\s*',
    re.DOTALL,
)


def _replace_day_nav(html: str, prev_href: str | None, next_href: str | None) -> str:
    from daily_texts.infrastructure.formatters.html import _day_nav

    nav = _day_nav(prev_href=prev_href, next_href=next_href, home_href="index.html")
    if _NAV_BLOCK.search(html):
        return _NAV_BLOCK.sub(nav.lstrip(), html, count=1)
    return html.replace(
        '<div class="site-shell">',
        f'<div class="site-shell">\n{nav.rstrip()}',
        1,
    )
