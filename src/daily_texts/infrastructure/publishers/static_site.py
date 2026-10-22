from __future__ import annotations

import calendar
import logging
import re
from datetime import date
from html import escape
from pathlib import Path

from daily_texts.application.dto import FormattedOutput, PublishResult
from daily_texts.domain.models import LocalizedDailyText
from daily_texts.infrastructure.formatters._common import format_date_en, format_date_zh
from daily_texts.infrastructure.formatters.html import (
    ICON_VERSION,
    INSTALL_SCRIPT_TAG,
    LANG_BOOT_SCRIPT,
    LOSUNGEN_ATTRIBUTION_HTML,
    PWA_HEAD_TAGS,
    TABBAR_HTML,
    VERSION_SCRIPT_TAG,
    HtmlFormatter,
    bilingual,
    load_devotional_css,
)

logger = logging.getLogger(__name__)

_DAY_PAGE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.html$")
# Public GitHub Pages base (project site). Used for sitemap.xml and robots.txt.
_SITE_BASE_URL = "https://mannatoday.github.io/daily-texts"
# App icon shipped with the package (src/daily_texts/inputs/icon.png).
_ICON_SOURCE = Path(__file__).resolve().parents[2] / "inputs" / "icon.png"
# Phone screenshots for the add-to-home guide (repo install/*.jpg).
_INSTALL_SHOTS = Path(__file__).resolve().parents[4] / "install"
_INSTALL_SHOT_NAMES = (
    "step1.jpg",
    "step2.jpg",
    "step3.jpg",
    "almostdone.jpg",
    "installed.jpg",
)
_FONT_LINKS = """\
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500&family=Noto+Serif+TC:wght@400;500&display=swap" rel="stylesheet" />
"""


class StaticSitePublisher:
    """Write dated HTML pages under SITE_DIR for GitHub Pages deploy."""

    channel = "static_site"

    def __init__(
        self,
        site_dir: Path | None = None,
        *,
        include_source_link: bool = False,
        earliest_date: date | None = None,
    ) -> None:
        self._site_dir = Path(site_dir) if site_dir is not None else Path("./site")
        self._html = HtmlFormatter()
        self._include_source_link = include_source_link
        # Days before this stay off the site (English-translated prayers).
        self._earliest_date = earliest_date

    async def publish(
        self,
        outputs: list[FormattedOutput],
        content: LocalizedDailyText,
    ) -> PublishResult:
        self._site_dir.mkdir(parents=True, exist_ok=True)
        self._write_stylesheet()
        self._write_version_js()
        self._write_icons()
        self._write_manifest()
        self._write_install_js()
        self._write_share_js()
        self._write_service_worker()
        self._write_about_page()
        self._write_install_page()

        if self._earliest_date is not None and content.date < self._earliest_date:
            day_path = self._site_dir / f"{content.date.isoformat()}.html"
            if day_path.is_file():
                day_path.unlink()
            days = self._list_day_pages()
            self._write_today_page(days[0] if days else None)
            index_path = self._site_dir / "index.html"
            index_path.write_text(self._build_index(days), encoding="utf-8")
            archive_path = self._site_dir / "archive.html"
            archive_path.write_text(self._build_archive(days), encoding="utf-8")
            self._write_sitemap(days)
            self._write_robots_txt()
            message = (
                f"Skipped {content.date.isoformat()} (before "
                f"{self._earliest_date.isoformat()}); updated {index_path}"
            )
            logger.info(message)
            return PublishResult(channel=self.channel, success=True, message=message)

        days_before = self._list_day_pages()
        days = sorted(set(days_before) | {content.date}, reverse=True)

        prev_href, next_href = _neighbors(content.date, days)
        page = self._html.format(
            content,
            include_source_link=self._include_source_link,
            stylesheet_href="styles.css",
            prev_href=prev_href,
            next_href=next_href,
            home_href="index.html",
        )
        day_path = self._site_dir / f"{content.date.isoformat()}.html"
        day_path.write_text(page.content, encoding="utf-8")

        self._refresh_neighbor_nav(content.date, days)
        self._write_today_page(days[0] if days else None)
        index_path = self._site_dir / "index.html"
        index_path.write_text(self._build_index(days), encoding="utf-8")
        archive_path = self._site_dir / "archive.html"
        archive_path.write_text(self._build_archive(days), encoding="utf-8")
        self._write_sitemap(days)
        self._write_robots_txt()

        message = (
            f"Wrote {day_path}, about.html, install.html, today.html, archive.html, "
            f"sitemap.xml, and updated {index_path}"
        )
        logger.info(message)
        return PublishResult(channel=self.channel, success=True, message=message)

    def _write_stylesheet(self) -> None:
        css_path = self._site_dir / "styles.css"
        css_path.write_text(load_devotional_css() + "\n", encoding="utf-8")

    def _write_version_js(self) -> None:
        (self._site_dir / "version.js").write_text(_VERSION_JS, encoding="utf-8")

    def _write_icons(self) -> None:
        """Copy the app icon used by the manifest and iOS home-screen shortcut."""
        if not _ICON_SOURCE.is_file():
            logger.warning("App icon not found at %s; skipping icon copy.", _ICON_SOURCE)
            return
        data = _ICON_SOURCE.read_bytes()
        (self._site_dir / "icon.png").write_bytes(data)
        (self._site_dir / "apple-touch-icon.png").write_bytes(data)

    def _write_manifest(self) -> None:
        (self._site_dir / "site.webmanifest").write_text(_MANIFEST_JSON, encoding="utf-8")

    def _write_install_js(self) -> None:
        (self._site_dir / "install.js").write_text(_INSTALL_JS, encoding="utf-8")

    def _write_share_js(self) -> None:
        (self._site_dir / "share.js").write_text(_SHARE_JS, encoding="utf-8")

    def _write_service_worker(self) -> None:
        (self._site_dir / "sw.js").write_text(_SW_JS, encoding="utf-8")

    def _write_about_page(self) -> None:
        (self._site_dir / "about.html").write_text(_ABOUT_HTML, encoding="utf-8")

    def _write_install_page(self) -> None:
        self._write_install_shots()
        (self._site_dir / "install.html").write_text(_INSTALL_HTML, encoding="utf-8")

    def _write_sitemap(self, days: list[date] | None = None) -> None:
        """Write sitemap.xml for Search Console (home, about, archive, dated days)."""
        days = days if days is not None else self._list_day_pages()
        (self._site_dir / "sitemap.xml").write_text(
            _build_sitemap(days),
            encoding="utf-8",
        )

    def _write_robots_txt(self) -> None:
        (self._site_dir / "robots.txt").write_text(
            "User-agent: *\n"
            "Allow: /\n"
            f"\nSitemap: {_SITE_BASE_URL}/sitemap.xml\n",
            encoding="utf-8",
        )

    def _write_install_shots(self) -> None:
        """Copy the illustrated install steps into the site so Pages can serve them."""
        dest = self._site_dir / "install"
        dest.mkdir(parents=True, exist_ok=True)
        if not _INSTALL_SHOTS.is_dir():
            logger.warning("Install screenshots not found at %s", _INSTALL_SHOTS)
            return
        for name in _INSTALL_SHOT_NAMES:
            src = _INSTALL_SHOTS / name
            if not src.is_file():
                logger.warning("Install screenshot missing: %s", src)
                continue
            (dest / name).write_bytes(src.read_bytes())

    def _write_today_page(self, latest: date | None = None) -> None:
        """Copy the newest day page to today.html so the URL stays stable."""
        if latest is None:
            days = self._list_day_pages()
            latest = days[0] if days else None
        today_path = self._site_dir / "today.html"
        if latest is None:
            today_path.write_text(
                _shell_page(
                    title_zh="今日經文 · 摩拉維亞每日箴言",
                    title_en="Today · Moravian Daily Texts",
                    description="今天的摩拉維亞每日箴言：舊約與新約每日靈修經文。",
                    body=f'    <p class="empty">{bilingual("尚無每日經文。", "No readings yet.")}</p>\n'
                    f'    <p class="archive-more"><a href="index.html">{bilingual("回首頁", "Home")}</a></p>\n',
                    extra_class="site-index",
                ),
                encoding="utf-8",
            )
            return
        day_path = self._site_dir / f"{latest.isoformat()}.html"
        html = day_path.read_text(encoding="utf-8")
        today_path.write_text(_as_today_page(html), encoding="utf-8")

    def _list_day_pages(self) -> list[date]:
        days: list[date] = []
        if not self._site_dir.is_dir():
            return days
        for path in self._site_dir.iterdir():
            match = _DAY_PAGE.match(path.name)
            if match and path.is_file():
                day = date.fromisoformat(match.group(1))
                if self._earliest_date is not None and day < self._earliest_date:
                    continue
                days.append(day)
        days.sort(reverse=True)
        return days

    def _refresh_neighbor_nav(self, current: date, days: list[date]) -> None:
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
            body = f'    <p class="empty">{bilingual("尚無每日經文。", "No readings yet.")}</p>\n'
        else:
            latest = days[0]
            latest_label = bilingual(format_date_zh(latest), format_date_en(latest))
            recent = days[:3]
            items = "\n".join(_day_list_item(d) for d in recent)
            body = (
                f'    <a class="today-card" href="today.html">'
                f'<span class="today-card__label">{bilingual("閱讀今日經文", "Today’s reading")}</span>'
                f'<span class="today-card__date">{latest_label}</span>'
                "</a>\n"
                f'    <h2 class="archive-title">{bilingual("最近三天", "Recent days")}</h2>\n'
                f'    <ul class="archive-list">\n{items}\n    </ul>\n'
                f'    <p class="archive-more"><a href="archive.html">{bilingual("歷日檔案", "Archive")}</a></p>\n'
            )

        return _shell_page(
            title_zh=_HOME_TITLE_ZH,
            title_en="Moravian Daily Texts",
            description=_HOME_DESCRIPTION,
            body=body,
            extra_class="site-index",
        )

    def _build_archive(self, days: list[date] | None = None) -> str:
        days = days if days is not None else self._list_day_pages()
        if not days:
            body = f'    <p class="empty">{bilingual("尚無每日經文。", "No readings yet.")}</p>\n'
        else:
            body = _archive_markup(days)

        return _shell_page(
            title_zh="歷日檔案 · 摩拉維亞每日箴言",
            title_en="Archive · Moravian Daily Texts",
            description=_ARCHIVE_DESCRIPTION,
            body=body,
            extra_class="site-index archive-page",
            top_nav=True,
        )


def _day_list_item(day: date) -> str:
    label = bilingual(format_date_zh(day), format_date_en(day))
    return (
        "      <li>"
        f'<a href="{day.isoformat()}.html">'
        f"<span>{label}</span>"
        f'<span class="iso">{day.isoformat()}</span>'
        "</a></li>"
    )


def _sitemap_url(loc: str, lastmod: date | None = None) -> str:
    lines = ["  <url>", f"    <loc>{escape(loc)}</loc>"]
    if lastmod is not None:
        lines.append(f"    <lastmod>{lastmod.isoformat()}</lastmod>")
    lines.append("  </url>")
    return "\n".join(lines)


def _build_sitemap(days: list[date]) -> str:
    """Sitemap for Google: home, about, archive, and each dated day page.

    Omits today.html (same content as the newest day), install.html, and
    the Search Console verification file.
    """
    newest = days[0] if days else None
    entries = [
        _sitemap_url(f"{_SITE_BASE_URL}/", newest),
        _sitemap_url(f"{_SITE_BASE_URL}/about.html", newest),
        _sitemap_url(f"{_SITE_BASE_URL}/archive.html", newest),
    ]
    for day in days:
        entries.append(
            _sitemap_url(f"{_SITE_BASE_URL}/{day.isoformat()}.html", day)
        )
    body = "\n".join(entries)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n"
        "</urlset>\n"
    )


def _archive_markup(days: list[date], *, today: date | None = None) -> str:
    """Month calendar plus a collapsed list, newest month first in the list."""
    published = set(days)
    today = date.today() if today is None else today
    months = _months_between(min(published), max(published))
    focus = (today.year, today.month)
    if focus not in months:
        focus = months[-1]

    panels = "\n".join(
        _calendar_month(
            year,
            month,
            published,
            today=today,
            checked=(year, month) == focus,
            prev_month=months[i - 1] if i > 0 else None,
            next_month=months[i + 1] if i + 1 < len(months) else None,
        )
        for i, (year, month) in enumerate(months)
    )
    lists = "\n".join(
        _month_list(year, month, days, open_month=(year, month) == focus)
        for year, month in reversed(months)
    )
    return (
        f'    <h1 class="archive-page-title">{bilingual("歷日檔案", "Archive")}</h1>\n'
        f'    <div class="cal">\n{panels}\n    </div>\n'
        f'    <h2 class="archive-months-title">{bilingual("依月份", "By month")}</h2>\n'
        f'    <div class="archive-months">\n{lists}\n    </div>\n'
    )


def _months_between(start: date, end: date) -> list[tuple[int, int]]:
    months: list[tuple[int, int]] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append((year, month))
        month += 1
        if month == 13:
            month = 1
            year += 1
    return months


def _month_id(year: int, month: int) -> str:
    return f"cal-{year}-{month:02d}"


def _month_label(year: int, month: int, *, with_year: bool) -> str:
    zh = f"{year} 年 {month} 月" if with_year else f"{month} 月"
    en_month = (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    )[month - 1]
    en = f"{en_month} {year}" if with_year else en_month
    return bilingual(zh, en)


def _calendar_month(
    year: int,
    month: int,
    published: set[date],
    *,
    today: date,
    checked: bool,
    prev_month: tuple[int, int] | None,
    next_month: tuple[int, int] | None,
) -> str:
    checked_attr = " checked" if checked else ""
    prev = _month_edge(prev_month, year, side="prev")
    nxt = _month_edge(next_month, year, side="next")
    title_zh = f"{year} 年 {month} 月"
    title_en = (
        "January February March April May June July August September October November December".split()
    )[month - 1] + f" {year}"
    title = bilingual(title_zh, title_en)
    heads = "".join(
        f'<span class="cal-dow">{bilingual(zh, en)}</span>'
        for zh, en in zip(
            ("日", "一", "二", "三", "四", "五", "六"),
            ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"),
            strict=True,
        )
    )
    cells = _calendar_cells(year, month, published, today)
    return (
        '      <div class="cal-month">\n'
        f'        <input class="cal-pick" type="radio" name="cal-month" id="{_month_id(year, month)}"{checked_attr}>\n'
        '        <div class="cal-sheet">\n'
        '          <div class="cal-nav">\n'
        f"            {prev}\n"
        f'            <h2 class="cal-nav__title">{title}</h2>\n'
        f"            {nxt}\n"
        "          </div>\n"
        f'          <div class="cal-grid" aria-label="{escape(title_zh)}">\n'
        f"            {heads}\n"
        f"{cells}\n"
        "          </div>\n"
        "        </div>\n"
        "      </div>"
    )


def _month_edge(target: tuple[int, int] | None, current_year: int, *, side: str) -> str:
    css = "cal-nav__prev" if side == "prev" else "cal-nav__next"
    if target is None:
        return f'<span class="{css}"></span>'
    year, month = target
    mark = "‹ " if side == "prev" else " ›"
    text = _month_label(year, month, with_year=year != current_year)
    if side == "next":
        text = f"{text}{mark}"
    else:
        text = f"{mark}{text}"
    return f'<label class="{css}" for="{_month_id(year, month)}">{text}</label>'


def _calendar_cells(year: int, month: int, published: set[date], today: date) -> str:
    weeks = calendar.Calendar(firstweekday=calendar.SUNDAY).monthdayscalendar(year, month)
    lines: list[str] = []
    for week in weeks:
        for day_num in week:
            if day_num == 0:
                lines.append('            <span class="cal-day cal-day--pad"></span>')
                continue
            day = date(year, month, day_num)
            label = escape(format_date_zh(day))
            if day not in published:
                lines.append(f'            <span class="cal-day cal-day--empty">{day_num}</span>')
                continue
            classes = "cal-day"
            current = ""
            if day == today:
                classes += " cal-day--today"
                current = ' aria-current="date"'
            lines.append(
                f'            <a class="{classes}" href="{day.isoformat()}.html"'
                f'{current} aria-label="{label}">{day_num}</a>'
            )
    return "\n".join(lines)


def _month_list(year: int, month: int, days: list[date], *, open_month: bool) -> str:
    in_month = [day for day in days if day.year == year and day.month == month]
    items = "\n".join(_day_list_item(day) for day in in_month)
    opened = " open" if open_month else ""
    title = f"{year} 年 {month} 月"
    return (
        f'      <details class="archive-month"{opened}>\n'
        f"        <summary>{title}</summary>\n"
        f'        <ul class="archive-list">\n{items}\n        </ul>\n'
        "      </details>"
    )


_HOME_TITLE_ZH = "摩拉維亞每日箴言｜每日靈修經文"
_HOME_DESCRIPTION = (
    "摩拉維亞每日箴言（每日箴文）：每天一段舊約、一段新約金句，"
    "供基督徒每日讀經、家庭靈修與家庭祭壇使用。"
)
_ABOUT_DESCRIPTION = (
    "摩拉維亞每日箴言的由來，以及本站的每日靈修經文、讀經進度，如何用於家庭靈修。"
)
_ARCHIVE_DESCRIPTION = "摩拉維亞每日箴言歷日檔案，按日期回看每日靈修經文。"


def _shell_page(
    *,
    title_zh: str,
    title_en: str,
    description: str,
    body: str,
    extra_class: str,
    top_nav: bool = False,
) -> str:
    nav = ""
    if top_nav:
        nav = f"""    <nav class="day-nav" aria-label="網站導覽">
      <a class="day-nav__prev" href="index.html">← {bilingual("首頁", "Home")}</a>
      <span class="day-nav__home" aria-current="page">{bilingual("歷日檔案", "Archive")}</span>
      <span class="day-nav__next" aria-disabled="true">{bilingual("後一日", "Next")} →</span>
    </nav>
"""
    brand = ""
    if not top_nav:
        brand = f"""    <h1 class="brand">{bilingual("摩拉維亞每日箴言", "Moravian Daily Texts")}</h1>
    <p class="subtitle">{bilingual("Moravian Daily Texts • 中文版", "Moravian Daily Texts")}</p>
    <p class="lede">{bilingual("以神的話開始每一天", "Begin each day with the Word of God")}</p>
"""
    blurb_zh = (
        "Moravian Daily Texts 自 1731 年開始出版，是歷史最悠久、持續出版的每日靈修讀本之一。"
        "每天包含一段舊約經文、一段新約經文、禱告及讀經進度，陪伴全球信徒以神的話開始每一天。"
    )
    blurb_en = (
        "Moravian Daily Texts has been published since 1731. Each day offers an Old Testament "
        "watchword, a New Testament text, and a plan for reading Scripture."
    )
    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="color-scheme" content="light dark" />
  <meta name="description" content="{escape(description, quote=True)}" />
  <title data-zh="{escape(title_zh, quote=True)}" data-en="{escape(title_en, quote=True)}">{escape(title_zh)}</title>
{LANG_BOOT_SCRIPT}{PWA_HEAD_TAGS}{_FONT_LINKS}  <link rel="stylesheet" href="styles.css" />
{VERSION_SCRIPT_TAG}{INSTALL_SCRIPT_TAG}</head>
<body>
  <a class="skip-link" href="#main">{bilingual("跳至內容", "Skip to content")}</a>
  <div class="site-shell {extra_class}">
  <div class="version-picker">
{_lang_toggle_markup()}  </div>
{nav}    <main id="main">
{brand}{body}    </main>
    <footer class="site-foot">
      <section class="about-blurb" aria-labelledby="about-blurb-title">
        <h2 id="about-blurb-title">{bilingual("關於 Moravian Daily Texts", "About Moravian Daily Texts")}</h2>
        <p class="i18n-zh">{blurb_zh}</p>
        <p class="i18n-en">{blurb_en}</p>
      </section>
      <p class="foot-credit">{bilingual("摩拉維亞每日箴言 · 中文整理", "Moravian Daily Texts")}</p>
      {LOSUNGEN_ATTRIBUTION_HTML}
    </footer>
{TABBAR_HTML}  </div>
</body>
</html>
"""


def _lang_toggle_markup() -> str:
    return """    <div class="lang-toggle" role="group" aria-label="Language">
      <button type="button" class="lang-toggle__btn" data-set-lang="zh" aria-pressed="true">中文</button>
      <button type="button" class="lang-toggle__btn" data-set-lang="en" aria-pressed="false">EN</button>
    </div>
"""


def _as_today_page(day_html: str) -> str:
    """Stable today.html: retitle, and drop the about blurb.

    The homepage already introduces Moravian Daily Texts, and the tab bar
    links to the about page, so the daily reading page stays on the texts.
    """
    html = _TITLE_TAG.sub(
        '<title data-zh="今日經文 · 摩拉維亞每日箴言" '
        'data-en="Today · Moravian Daily Texts">'
        "今日經文 · 摩拉維亞每日箴言</title>",
        day_html,
        count=1,
    )
    return _ABOUT_BLURB_SECTION.sub("", html, count=1)


_ABOUT_BLURB_SECTION = re.compile(
    r'[ \t]*<section class="about-blurb"[^>]*>.*?</section>\n',
    re.DOTALL,
)


_TITLE_TAG = re.compile(r"<title\b[^>]*>.*?</title>", re.DOTALL)


def _neighbors(day: date, days_newest_first: list[date]) -> tuple[str | None, str | None]:
    chronological = sorted(days_newest_first)
    if day not in chronological:
        return None, None
    idx = chronological.index(day)
    prev_day = chronological[idx - 1] if idx > 0 else None
    next_day = chronological[idx + 1] if idx + 1 < len(chronological) else None
    prev_href = f"{prev_day.isoformat()}.html" if prev_day else None
    next_href = f"{next_day.isoformat()}.html" if next_day else None
    return prev_href, next_href


_NAV_BLOCK = re.compile(
    r'<nav class="day-nav(?:\s+day-nav--bottom)?"[^>]*>.*?</nav>\s*',
    re.DOTALL,
)


def _replace_day_nav(html: str, prev_href: str | None, next_href: str | None) -> str:
    from daily_texts.infrastructure.formatters.html import _day_nav

    bottom = _day_nav(
        prev_href=prev_href,
        next_href=next_href,
        home_href="index.html",
        css_extra="day-nav--bottom",
        bilingual_labels=True,
    )
    matches = list(_NAV_BLOCK.finditer(html))
    if not matches:
        return html

    parts: list[str] = []
    last = 0
    for match in matches:
        parts.append(html[last : match.start()])
        if "day-nav--bottom" in match.group(0):
            parts.append(bottom.lstrip() if match.start() > 0 else bottom)
        last = match.end()
    parts.append(html[last:])
    return "".join(parts)


_VERSION_JS = """\
// Language toggle plus multi-version watchword renderer.
// Language: ?lang= → version hint → localStorage → Chinese.
// Version: ?version= (if it belongs to that language) → per-language localStorage → default.
(function () {
  "use strict";
  var LANG_KEY = "dailyTexts.lang";
  var VERSION_KEY = "dailyTexts.bibleVersion";
  var ENGLISH = [
    { code: "NIV", label: "NIV" },
    { code: "NLT", label: "NLT" },
    { code: "NIRV", label: "NIrV" },
    { code: "KJV", label: "KJV" }
  ];
  var CHINESE = ["CUV", "RCUV", "CNVT", "CSBT", "WCB"];
  var DEFAULTS = { zh: "RCUV", en: "NIV" };

  var select = document.getElementById("bible-version");
  var dataEl = document.getElementById("day-data");
  var day = null;
  if (dataEl) {
    try {
      day = JSON.parse(dataEl.textContent || "{}");
    } catch (err) {
      day = null;
    }
  }

  function queryParam(name) {
    try {
      return new URLSearchParams(window.location.search).get(name);
    } catch (err) {
      return null;
    }
  }

  function stored(key) {
    try {
      return window.localStorage.getItem(key);
    } catch (err) {
      return null;
    }
  }

  function remember(key, value) {
    try {
      window.localStorage.setItem(key, value);
    } catch (err) {
      /* ignore */
    }
  }

  function listFor(lang) {
    var fallback = lang === "en"
      ? ENGLISH
      : CHINESE.map(function (code) { return { code: code, label: code }; });
    var fromDay = day && (lang === "en" ? day.english_versions : day.versions);
    if (!fromDay || !fromDay.length) return fallback;
    if (lang !== "en") return fromDay;
    var allowed = {};
    ENGLISH.forEach(function (item) { allowed[item.code] = true; });
    var merged = fromDay.filter(function (item) { return allowed[item.code]; });
    var seen = {};
    merged.forEach(function (item) { seen[item.code] = true; });
    fallback.forEach(function (item) {
      if (!seen[item.code]) merged.push(item);
    });
    return merged;
  }

  function codesFor(lang) {
    return listFor(lang).map(function (item) {
      return item.code;
    });
  }

  function resolveLang() {
    var q = queryParam("lang");
    if (q === "en" || q === "zh") return q;
    var version = queryParam("version");
    if (version && ENGLISH.some(function (item) { return item.code === version; })) return "en";
    if (version && CHINESE.indexOf(version) >= 0) return "zh";
    var saved = stored(LANG_KEY);
    if (saved === "en" || saved === "zh") return saved;
    if (document.documentElement.getAttribute("data-lang") === "en") return "en";
    return "zh";
  }

  function storedVersion(lang, codes) {
    var saved = stored(VERSION_KEY + "." + lang);
    if (saved && codes.indexOf(saved) >= 0) return saved;
    if (lang === "zh") {
      var legacy = stored(VERSION_KEY);
      if (legacy && codes.indexOf(legacy) >= 0) return legacy;
    }
    var fallback = (day && (lang === "en" ? day.default_english_version : day.default_version)) || DEFAULTS[lang];
    if (codes.indexOf(fallback) >= 0) return fallback;
    return codes[0];
  }

  function resolveVersion(lang, codes) {
    var q = queryParam("version");
    if (q && codes.indexOf(q) >= 0) return q;
    return storedVersion(lang, codes);
  }

  function gatewayMap() {
    var map = {
      CUV: "CUV",
      RCUV: "RCU17TS",
      CNVT: "CNVT",
      CSBT: "CSBT",
      KJV: "KJV",
      NIV: "NIV",
      NLT: "NLT",
      NIRV: "NIRV"
    };
    var extra = (day && day.gateway) || {};
    Object.keys(extra).forEach(function (key) { map[key] = extra[key]; });
    return map;
  }

  function gatewayCode(siteCode) {
    var map = gatewayMap();
    return Object.prototype.hasOwnProperty.call(map, siteCode) ? map[siteCode] : null;
  }

  function gatewayUrl(ref, siteCode) {
    var code = gatewayCode(siteCode);
    if (!code || !ref) return "";
    return (
      "https://www.biblegateway.com/passage/?search=" +
      encodeURIComponent(ref) +
      "&version=" +
      encodeURIComponent(code)
    );
  }

  function setLangChrome(lang) {
    var root = document.documentElement;
    if (lang === "en") {
      root.setAttribute("data-lang", "en");
      root.lang = "en";
    } else {
      root.removeAttribute("data-lang");
      root.lang = "zh-Hant";
    }
    var title = document.querySelector("title");
    if (title) {
      var next = title.getAttribute(lang === "en" ? "data-en" : "data-zh");
      if (next) title.textContent = next;
    }
    var buttons = document.querySelectorAll("[data-set-lang]");
    Array.prototype.forEach.call(buttons, function (btn) {
      btn.setAttribute(
        "aria-pressed",
        btn.getAttribute("data-set-lang") === lang ? "true" : "false"
      );
    });
  }

  function fillSelect(lang, version) {
    if (!select) return;
    var list = listFor(lang);
    select.innerHTML = "";
    list.forEach(function (item) {
      var opt = document.createElement("option");
      opt.value = item.code;
      opt.textContent = item.label;
      if (item.code === version) opt.selected = true;
      select.appendChild(opt);
    });
    select.value = version;
  }

  function textFor(block, siteCode) {
    if (!block || !block.translations) return "";
    if (Object.prototype.hasOwnProperty.call(block.translations, siteCode)) {
      return block.translations[siteCode] || "";
    }
    return "";
  }

  function applyVerses(siteCode, lang) {
    if (!day) return;
    var map = { week: day.week_watchword, ot: day.ot, nt: day.nt };
    Object.keys(map).forEach(function (role) {
      var el = document.querySelector('[data-verse="' + role + '"]');
      var block = map[role];
      if (!el || !block) return;
      var text = textFor(block, siteCode);
      el.textContent = "";
      if (text) {
        el.textContent = text;
        reportFums(block, siteCode);
        return;
      }
      var href = gatewayUrl(block.reference, siteCode);
      if (!href) return;
      var link = document.createElement("a");
      link.className = "verse__fallback";
      link.href = href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = lang === "en" ? "Read on Bible Gateway" : "在 Bible Gateway 閱讀";
      el.appendChild(link);
    });
  }

  function applyReadingLinks(siteCode, lang) {
    var links = document.querySelectorAll("a.reading__open");
    Array.prototype.forEach.call(links, function (link) {
      var ref = link.getAttribute("data-ref");
      if (!ref) return;
      var href = gatewayUrl(ref, siteCode);
      if (!href) {
        link.hidden = true;
        return;
      }
      link.hidden = false;
      link.href = href;
      var zh = link.getAttribute("data-label-zh") || ref;
      if (lang === "en") {
        link.title = "Read on Bible Gateway";
        link.setAttribute("aria-label", "Read " + ref);
      } else {
        link.title = "在 Bible Gateway 閱讀";
        link.setAttribute("aria-label", "閱讀 " + zh);
      }
    });
  }

  var EXTRA_NOTICES = {
    NIV: "Scripture quotations taken from The Holy Bible, New International Version®, NIV®. Copyright © 1973, 1978, 1984, 2011 by Biblica, Inc.™ Used by permission. All rights reserved worldwide.",
    NLT: "Scripture quotations are taken from the Holy Bible, New Living Translation, copyright © 1996, 2004, 2015 by Tyndale House Foundation. Used by permission of Tyndale House Publishers, Carol Stream, Illinois 60188. All rights reserved.",
    NIRV: "Scripture quotations are taken from the Holy Bible, New International Reader’s Version®, NIrV®. Copyright © 1995, 1996, 1998, 2014 by Biblica, Inc.™ Used by permission. All rights reserved worldwide."
  };

  function reportFums(block, siteCode) {
    var raw = block && block.fums && block.fums[siteCode];
    if (!raw) return;
    raw.split(/\\s+/).forEach(function (token) {
      if (!token || reportFums.seen[token]) return;
      reportFums.seen[token] = true;
      var ping = new Image();
      ping.referrerPolicy = "no-referrer";
      ping.src = "https://fums.api.bible/fums/?t=" + encodeURIComponent(token);
    });
  }
  reportFums.seen = {};

  function applyNotice(siteCode) {
    var note = document.getElementById("version-notice");
    if (!note) return;
    var notices = (day && day.notices) || {};
    var text = notices[siteCode] || EXTRA_NOTICES[siteCode] || "";
    note.hidden = !text;
    if (text) note.textContent = text;
  }

  function syncUrl(lang, version) {
    try {
      var url = new URL(window.location.href);
      url.searchParams.set("lang", lang);
      if (select) url.searchParams.set("version", version);
      window.history.replaceState({}, "", url.toString());
    } catch (err) {
      /* file:// or unsupported */
    }
  }

  function apply(lang, version) {
    setLangChrome(lang);
    fillSelect(lang, version);
    applyVerses(version, lang);
    applyReadingLinks(version, lang);
    applyNotice(version);
    remember(LANG_KEY, lang);
    remember(VERSION_KEY + "." + lang, version);
    syncUrl(lang, version);
  }

  var lang = resolveLang();
  var version = resolveVersion(lang, codesFor(lang));
  apply(lang, version);

  if (select) {
    select.addEventListener("change", function () {
      version = select.value;
      apply(lang, version);
    });
  }

  var buttons = document.querySelectorAll("[data-set-lang]");
  Array.prototype.forEach.call(buttons, function (btn) {
    btn.addEventListener("click", function () {
      var next = btn.getAttribute("data-set-lang");
      if (next !== "en" && next !== "zh") return;
      if (next === lang) return;
      lang = next;
      version = storedVersion(lang, codesFor(lang));
      apply(lang, version);
    });
  });
})();
"""
# Web app manifest. Relative URLs resolve against the manifest's own location,
# so start_url/scope stay correct under the GitHub Pages subpath (…/daily-texts/).
# start_url points at today.html so the installed shortcut always opens the latest day.
_MANIFEST_JSON = f"""\
{{
  "name": "摩拉維亞每日箴言",
  "short_name": "每日箴言",
  "lang": "zh-Hant",
  "description": "摩拉維亞每日箴言 · Moravian Daily Texts 中文版",
  "start_url": "today.html",
  "scope": "./",
  "id": "./",
  "display": "standalone",
  "orientation": "portrait",
  "background_color": "#f7f6f2",
  "theme_color": "#f7f6f2",
  "icons": [
    {{ "src": "icon.png?v={ICON_VERSION}", "sizes": "192x192", "type": "image/png", "purpose": "any" }},
    {{ "src": "icon.png?v={ICON_VERSION}", "sizes": "512x512", "type": "image/png", "purpose": "any" }},
    {{ "src": "icon.png?v={ICON_VERSION}", "sizes": "512x512", "type": "image/png", "purpose": "maskable" }}
  ]
}}
"""

# Registers the service worker so the site can be installed from the browser
# menu. On the guide page, a direct Install button appears only when the
# browser offers one. The about-page note is hidden once the site is already
# open from the home-screen icon.
# A fetch handler is what lets Android Chrome install a real app (WebAPK).
# Without it, "Add to Home Screen" is only a shortcut: Chrome badge on the
# icon, and the app switcher stays inside Chrome. This worker does not cache.
_SW_JS = """\
self.addEventListener("install", function () {
  self.skipWaiting();
});

self.addEventListener("activate", function (event) {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", function () {});
"""

# Opens the system share sheet (LINE, Messages, WhatsApp, Mail, …) with the
# day's two watchwords, the Chinese prayer when showing Chinese, and a dated URL.
# Desktop browsers without Web Share copy the same text instead.
_SHARE_JS = """\
(function () {
  "use strict";

  function dayData() {
    var el = document.getElementById("day-data");
    if (!el) return null;
    try {
      return JSON.parse(el.textContent || "{}");
    } catch (err) {
      return null;
    }
  }

  function isEnglish() {
    return document.documentElement.getAttribute("data-lang") === "en";
  }

  function verseText(role) {
    var el = document.querySelector('[data-verse="' + role + '"]');
    if (!el) return "";
    return (el.textContent || "").replace(/\\s+/g, " ").trim();
  }

  function refFor(block, english) {
    if (!block) return "";
    if (english) return block.reference || block.reference_zh || "";
    return block.reference_zh || block.reference || "";
  }

  function pageUrl(day) {
    try {
      var path = window.location.pathname || "";
      var base = path.replace(/[^/]+$/, "");
      var file = (day && day.date ? day.date : "today") + ".html";
      return window.location.origin + base + file + window.location.search;
    } catch (err) {
      return window.location.href;
    }
  }

  function shareTitle(day, english) {
    if (!day) return english ? "Moravian Daily Texts" : "摩拉維亞每日箴言";
    if (english) {
      return (day.date_title_en || day.date || "") + " · Moravian Daily Texts";
    }
    return (day.date_title_zh || day.date || "") + " · 摩拉維亞每日箴言";
  }

  function shareText(day, english) {
    var lines = [];
    var ot = day && day.ot;
    var nt = day && day.nt;
    var otRef = refFor(ot, english);
    var ntRef = refFor(nt, english);
    var otText = verseText("ot");
    var ntText = verseText("nt");

    if (english) {
      if (otText) {
        lines.push("Old Testament" + (otRef ? " (" + otRef + ")" : ""));
        lines.push(otText);
      }
      if (ntText) {
        if (lines.length) lines.push("");
        lines.push("New Testament" + (ntRef ? " (" + ntRef + ")" : ""));
        lines.push(ntText);
      }
    } else {
      if (otText) {
        lines.push("舊約" + (otRef ? "（" + otRef + "）" : ""));
        lines.push(otText);
      }
      if (ntText) {
        if (lines.length) lines.push("");
        lines.push("新約" + (ntRef ? "（" + ntRef + "）" : ""));
        lines.push(ntText);
      }
      var prayer = ((day && day.prayer) || "").trim();
      if (prayer) {
        if (lines.length) lines.push("");
        lines.push("今日禱告");
        lines.push(prayer);
        var source = document.querySelector(".prayer-source");
        var cite = source && (source.textContent || "").trim();
        if (cite) lines.push(cite);
      }
    }
    return lines.join("\\n");
  }

  function showStatus(message) {
    var status = document.getElementById("share-status");
    if (!status) return;
    status.hidden = false;
    status.textContent = message;
    window.setTimeout(function () {
      status.hidden = true;
      status.textContent = "";
    }, 2200);
  }

  function copyFallback(text, english) {
    var done = english ? "Copied" : "已複製";
    var fail = english ? "Could not copy" : "無法複製";
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(
        function () { showStatus(done); },
        function () { showStatus(fail); }
      );
      return;
    }
    try {
      var area = document.createElement("textarea");
      area.value = text;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.left = "-9999px";
      document.body.appendChild(area);
      area.select();
      document.execCommand("copy");
      document.body.removeChild(area);
      showStatus(done);
    } catch (err) {
      showStatus(fail);
    }
  }

  function start() {
    var btn = document.getElementById("share-day");
    if (!btn) return;

    btn.addEventListener("click", function () {
      var day = dayData();
      var english = isEnglish();
      var url = pageUrl(day);
      var title = shareTitle(day, english);
      var body = shareText(day, english);
      var text = body ? body + "\\n\\n" + url : url;
      var payload = { title: title, text: body, url: url };

      if (typeof navigator.share === "function") {
        navigator.share(payload).catch(function (err) {
          if (err && err.name === "AbortError") return;
          copyFallback(text, english);
        });
        return;
      }
      copyFallback(text, english);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
"""

_INSTALL_JS = """\
(function () {
  "use strict";

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("sw.js").catch(function () {});
  }

  function isStandalone() {
    try {
      return (
        window.matchMedia("(display-mode: standalone)").matches ||
        window.navigator.standalone === true
      );
    } catch (err) {
      return false;
    }
  }

  function start() {
    var done = document.getElementById("install-done");
    var note = document.querySelector(".home-screen-note");
    if (isStandalone()) {
      if (done) done.hidden = false;
      if (note) note.hidden = true;
      return;
    }

    var deferredPrompt = null;
    var nowWrap = document.getElementById("install-now-wrap");
    var now = document.getElementById("install-now");

    window.addEventListener("beforeinstallprompt", function (e) {
      e.preventDefault();
      deferredPrompt = e;
      if (nowWrap) nowWrap.hidden = false;
    });

    if (now) {
      now.addEventListener("click", function () {
        if (!deferredPrompt) return;
        var prompt = deferredPrompt;
        deferredPrompt = null;
        prompt.prompt();
        prompt.userChoice.then(function () {
          if (nowWrap) nowWrap.hidden = true;
        });
      });
    }

    window.addEventListener("appinstalled", function () {
      deferredPrompt = null;
      if (nowWrap) nowWrap.hidden = true;
      if (done) done.hidden = false;
      if (note) note.hidden = true;
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
"""

_ABOUT_HTML = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="color-scheme" content="light dark" />
  <meta name="description" content="{_ABOUT_DESCRIPTION}" />
  <title data-zh="關於 · 摩拉維亞每日箴言" data-en="About · Moravian Daily Texts">關於 · 摩拉維亞每日箴言</title>
{LANG_BOOT_SCRIPT}{PWA_HEAD_TAGS}{_FONT_LINKS}  <link rel="stylesheet" href="styles.css" />
{VERSION_SCRIPT_TAG}{INSTALL_SCRIPT_TAG}</head>
<body>
  <a class="skip-link" href="#main">{bilingual("跳至內容", "Skip to content")}</a>
  <div class="site-shell about-page">
  <div class="version-picker">
{_lang_toggle_markup()}  </div>
    <nav class="day-nav" aria-label="網站導覽">
      <a class="day-nav__prev" href="index.html">← {bilingual("首頁", "Home")}</a>
      <span class="day-nav__home" aria-current="page">{bilingual("關於", "About")}</span>
      <span class="day-nav__next" aria-disabled="true">{bilingual("後一日", "Next")} →</span>
    </nav>
    <main id="main">
      <div class="i18n-zh">
      <h1>關於 Moravian Daily Texts</h1>

      <h2>起源</h2>
      <p>《Die Losungen》（摩拉維亞每日箴言，英文 Moravian Daily Texts）自 1731 年印行以來每年出版，是持續最久的每日靈修讀本之一。</p>
      <p>1722 年，波希米亞與摩拉維亞的信仰難民來到親岑多夫伯爵（Nikolaus Ludwig von Zinzendorf，1700–1760）的領地，建立赫恩胡特（Herrnhut，「主的守望」）。1727 年 8 月 13 日，弟兄合一會在那裡經歷屬靈更新。1728 年 5 月 3 日晚間聚會，親岑多夫把一句聖經交給會眾，作為第二天整天的口令。他稱這句話為 Losung，意思是守望的口令。此後每天有人把這句話送到村裡三十二戶，並一起談論。</p>
      <p>親岑多夫為一整年編了 365 則守望經文，1731 年在赫恩胡特印出第一本。封面引用耶利米哀歌：主的慈愛每早晨都是新的。早期版本就把經文和一節聖詩放在一起：經文是神對人說的話，詩節是會眾的回應。1732 年弟兄會開始海外宣教，箴言也跟著傳到各地。今天以六十多種語言出版。每天的聖經章節仍在德國赫恩胡特選定，再分送到各地的語言版本。</p>

      <h2>Losung 與 Lehrtext</h2>
      <p>現在每一天有兩節，選法不同。</p>
      <p>舊約的 Losung（守望經文，Watchword）是抽籤得出的。自 1788 年起，從一批適合日常的舊約經文中抽籤；到 1812 年確定，守望經文一律出自舊約。它多半是應許、鼓勵、勸勉或安慰，陪伴人過這一天。親岑多夫說，這些箴言是救主與教會持續的對話。</p>
      <p>新約的 Lehrtext（教訓經文）不是抽籤，而是按當天的守望經文挑選。這個做法從親岑多夫為小組編的經文匯編長出來。1760 年他過世後，同工把守望經文和教訓經文分開保存，1762 年在巴爾比印成四卷。1801 年的說明是：守望經文是應許、鼓勵、勸戒或安慰；教訓經文則點出一項已經啟示的道理。十九世紀末起，兩節在主題上彼此呼應。</p>

      <h2>每日內容</h2>
      <p>每一天通常包含：</p>
      <ul>
        <li>一段舊約守望經文（Watchword）</li>
        <li>一段新約經文</li>
        <li>一段簡短禱告</li>
        <li>讀經進度（詩篇、舊約、新約）</li>
      </ul>
      <p>舊約與新約並陳，提醒我們整本聖經彼此呼應：神的應許與成全、律法與福音，都在每日閱讀中相遇。</p>

      <h2>今日禱告</h2>
      <p>頁面上的「今日禱告」就是這一段簡短禱告。它回應當天的舊約與新約，把人帶到向神說話。篇幅只取一節聖詩，或一小段禱文，句末署名作者與作品。</p>
      <p>這段禱文按當天兩節挑選，並加入華人文化裡的聖詩、禮文與靈修文字，以及歷代中文聖詩與公禱文。</p>

      <h2>讀經進度</h2>
      <p>頁面上稱為「經文選讀」。詩篇、舊約、新約各自按順序往下讀，與當天兩節守望經文各走各的。</p>
      <p>平日（星期一至六）三條一起推進。長詩篇拆成幾天；舊約大約一天一到兩章，新約大約半章到一章，切在段落結束的地方。</p>
      <p>照這進度，詩篇大約一年讀完一遍；詩篇以外的舊約與新約大約兩年讀完。一年大約讀完整本聖經的一半。跟著每天的選讀走，大約兩年可以讀完聖經一遍。</p>

      <h2>關於本站中文版</h2>
      <p class="meta">本站中文版依官方每日經文章節編排，目前不是翻譯版。經文正文引自已獲全世界使用授權的中文譯本，可在頁首切換。今日禱告依當天兩節挑選，並加入華人文化中的聖詩與禱文。本站供個人與家庭靈修使用，非官方出版物。</p>

      <h2>版權與來源</h2>
      <p class="meta">每日舊約守望經文與新約經文的章節，出自官方德文《Die Losungen》，由 <a href="https://www.herrnhuter.de/" rel="noopener noreferrer">Evangelische Brüder-Unität – Herrnhuter Brüdergemeine</a> 出版。更多資訊見 <a href="https://www.losungen.de/" rel="noopener noreferrer">www.losungen.de</a>。</p>
      <p class="meta">英文版每日內容見 <a href="https://www.moravian.org/the-daily-texts/" rel="noopener noreferrer">Moravian Church in America — The Daily Texts</a>。讀經進度依北美摩拉維亞教會的讀經安排，說明見 <a href="https://www.moravian.org/2018/07/using-the-moravian-daily-texts/" rel="noopener noreferrer">Using the Moravian Daily Texts</a>。</p>
      <p class="meta">中文經文正文引自已獲全世界使用授權的譯本：和合本、和合本修訂版、新譯本、中文標準譯本、環球聖經譯本。英文可在頁首切換 NIV、NLT、NIrV 與 KJV。NIV 與 NIrV 版權屬於 Biblica；NLT 版權屬於 Tyndale House；KJV 為公有領域。各譯本版權仍屬原出版機構。選用《環球聖經譯本》、NIV、NLT 或 NIrV 時，頁腳另標版權。</p>
      <p class="meta">今日禱告的出處是當天頁面句末的署名（作者與作品）。聖詩與禱文的版權依各作品而定。</p>
      <p class="meta">若需正式出版、轉載或商業用途，請另洽各原文出版單位，並遵守各譯本與作品的版權規定。</p>
      </div>

      <div class="i18n-en">
      <h1>About Moravian Daily Texts</h1>

      <h2>Beginnings</h2>
      <p><em>Die Losungen</em> (Moravian Daily Texts) has been published every year since 1731. It is one of the longest-running daily devotionals.</p>
      <p>In 1722, refugees from Bohemia and Moravia settled on the estate of Count Nikolaus Ludwig von Zinzendorf (1700–1760) and founded Herrnhut, “the Lord’s watch.” On 13 August 1727 the Moravian Church experienced a spiritual renewal there. On the evening of 3 May 1728, Zinzendorf gave the congregation a Bible verse to carry through the next day. He called it a <em>Losung</em>, a watchword. The verse was then carried to the village’s thirty-two households, and they talked about it together.</p>
      <p>Zinzendorf prepared 365 watchwords for a full year, and the first book was printed at Herrnhut in 1731. The cover quoted Lamentations: the steadfast love of the Lord is new every morning. Early editions already set a Bible text beside a hymn verse. The text is God speaking; the verse is the congregation’s reply. In 1732 the Moravians began mission overseas, and the texts traveled with them. They are now published in more than sixty languages. The verses for each day are still chosen in Herrnhut, Germany, and then sent to the different language editions.</p>

      <h2>Watchword and doctrinal text</h2>
      <p>Each day now has two texts, chosen in different ways.</p>
      <p>The Old Testament <em>Losung</em> (Watchword) is drawn by lot. From 1788 it was drawn from Old Testament verses suited to daily life; by 1812 the watchword was always from the Old Testament. It is usually a promise, an encouragement, an admonition, or a comfort for the day. Zinzendorf said these texts were an ongoing conversation between the Savior and the church.</p>
      <p>The New Testament <em>Lehrtext</em> (Doctrinal Text) is not drawn by lot. It is chosen to go with that day’s watchword. The practice grew out of the collections Zinzendorf prepared for small groups. After his death in 1760, his colleagues kept the two texts separately, and in 1762 they were printed in four volumes at Barby. An explanation from 1801 said that the watchword is a promise, encouragement, warning, or comfort, and the doctrinal text names a truth already revealed. Since the late nineteenth century the two texts have answered each other.</p>

      <h2>What each day contains</h2>
      <p>A day usually includes:</p>
      <ul>
        <li>an Old Testament watchword</li>
        <li>a New Testament text</li>
        <li>a short prayer</li>
        <li>a reading plan: Psalms, Old Testament, and New Testament</li>
      </ul>
      <p>The Old and New Testaments are set side by side, so promise and fulfillment, law and gospel, meet in the day’s reading.</p>

      <h2>The prayer</h2>
      <p>In Chinese, “今日禱告” is that short prayer. It answers the day’s two texts and turns the reader toward speaking to God. It is one hymn stanza or a short prayer, with the author and the work named at the end.</p>
      <p>The prayer is chosen for those two texts and draws on Chinese hymns, liturgy, and devotional writing, together with historic Chinese hymnals and books of common prayer.</p>

      <h2>Readings</h2>
      <p>On the page these are the Readings. The Psalms, the Old Testament, and the New Testament each continue in their own order, apart from the two daily texts.</p>
      <p>From Monday through Saturday the three tracks move forward together. A long psalm may take several days. The Old Testament is about one or two chapters a day, and the New Testament about half a chapter to a chapter, broken where a passage ends.</p>
      <p>At this pace the Psalms are read through about once a year, and the rest of the Bible about once in two years. One year covers about half of the Bible. Following the daily readings, the Bible is read through in about two years.</p>

      <h2>This site</h2>
      <p class="meta">The Chinese edition follows the official daily verses. It is not a translation. Scripture is quoted from Chinese versions licensed for worldwide use, and the version can be changed at the top of the page. The prayer is chosen for the day’s two texts and draws on Chinese hymns and prayers. The site is for personal and family devotion and is not an official publication.</p>

      <h2>Copyright and sources</h2>
      <p class="meta">The daily Old Testament watchword and New Testament text are taken from the official German <em>Die Losungen</em>, published by the <a href="https://www.herrnhuter.de/" rel="noopener noreferrer">Evangelische Brüder-Unität – Herrnhuter Brüdergemeine</a>. More information is at <a href="https://www.losungen.de/" rel="noopener noreferrer">www.losungen.de</a>.</p>
      <p class="meta">The English Daily Texts are published by the <a href="https://www.moravian.org/the-daily-texts/" rel="noopener noreferrer">Moravian Church in America</a>. The reading plan follows the North American Moravian arrangement, described in <a href="https://www.moravian.org/2018/07/using-the-moravian-daily-texts/" rel="noopener noreferrer">Using the Moravian Daily Texts</a>.</p>
      <p class="meta">Chinese scripture is quoted from the Chinese Union Version, its revised edition, the New Chinese Version, the Chinese Standard Bible, and the Worldwide Chinese Bible. English scripture can be switched at the top of the page among the NIV, NLT, NIrV, and KJV. The NIV and NIrV are copyright Biblica; the NLT is copyright Tyndale House; the KJV is in the public domain. Copyright for each version remains with its publisher. When the Worldwide Chinese Bible, NIV, NLT, or NIrV is selected, a copyright line appears in the footer.</p>
      <p class="meta">The source of the prayer is the name printed at the end of that day’s prayer. Copyright in the hymns and prayers depends on each work.</p>
      <p class="meta">For formal publication, reprinting, or commercial use, contact each original publisher and follow the terms of each Bible version and each quoted work.</p>
      </div>
      <p class="home-screen-note"><span class="i18n-zh">想從手機主頁打開，見<a href="install.html">加到主畫面</a>。</span><span class="i18n-en">To open this from the phone’s home screen, see <a href="install.html">how to add it</a>.</span></p>
    </main>
    <footer class="site-foot">
      <p class="foot-credit">{bilingual("摩拉維亞每日箴言 · 中文整理", "Moravian Daily Texts")}</p>
      {LOSUNGEN_ATTRIBUTION_HTML}
    </footer>
{TABBAR_HTML}  </div>
</body>
</html>
"""

_INSTALL_HTML = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="color-scheme" content="light dark" />
  <meta name="description" content="把摩拉維亞每日箴言加到手機主頁" />
  <title data-zh="加到手機主頁 · 摩拉維亞每日箴言" data-en="Add to Phone · Moravian Daily Texts">加到手機主頁 · 摩拉維亞每日箴言</title>
{LANG_BOOT_SCRIPT}{PWA_HEAD_TAGS}{_FONT_LINKS}  <link rel="stylesheet" href="styles.css" />
{VERSION_SCRIPT_TAG}{INSTALL_SCRIPT_TAG}</head>
<body>
  <a class="skip-link" href="#main">{bilingual("跳至內容", "Skip to content")}</a>
  <div class="site-shell install-page">
  <div class="version-picker">
{_lang_toggle_markup()}  </div>
    <nav class="day-nav" aria-label="網站導覽">
      <a class="day-nav__prev" href="index.html">← {bilingual("首頁", "Home")}</a>
      <span class="day-nav__home" aria-current="page">{bilingual("加到手機主頁", "Add to Phone")}</span>
      <span class="day-nav__next" aria-disabled="true">{bilingual("後一日", "Next")} →</span>
    </nav>
    <main id="main">
      <h1>{bilingual("加到手機主頁", "Add to Phone")}</h1>
      <p class="lede">{bilingual("加到手機主頁之後，會出現「每日箴言」圖示。點圖示就打開。", "After you add it, a 每日箴言 icon appears. Tap the icon to open the reading.")}</p>
      <p id="install-done" class="install-done" hidden>{bilingual("你已經從主頁的圖示打開。", "You already opened this from the home-screen icon.")}</p>
      <p id="install-now-wrap" class="install-now-wrap" hidden>{bilingual("這個瀏覽器可以直接安裝，按下面的按鈕即可。", "This browser can install it directly.")}<br /><button type="button" class="install-now" id="install-now">{bilingual("安裝", "Install")}</button></p>
      <p class="install-intro">{bilingual("下面以 Android 手機的 Chrome 為例。選單若是英文，對照圖裡紅圈標出的那一項。", "The pictures below are Android Chrome. If the menu is in English, tap the item circled in red.")}</p>
      <ol class="install-steps">
        <li class="install-step">
          <h2>{bilingual("打開「安裝或建立捷徑」", "Choose Install and create shortcut")}</h2>
          <p>{bilingual("用 Chrome 打開這個網站，點右上角的選單，選「安裝或建立捷徑」。圖中英文是 Install and create shortcut。", "Open this site in Chrome, then open the menu and tap “Install and create shortcut”.")}</p>
          <figure>
            <img src="install/step2.jpg" width="1080" height="2085" alt="瀏覽器選單裡，Install and create shortcut 被紅圈標出" />
          </figure>
        </li>
        <li class="install-step">
          <h2>{bilingual("按「安裝」", "Tap Install")}</h2>
          <p>{bilingual("跳出視窗後，按「安裝」。圖中英文是 Install。裝好時手機會提示已安裝。", "When the window appears, tap Install. The phone then says the app is installed.")}</p>
          <figure>
            <img src="install/step3.jpg" width="1075" height="2108" alt="安裝視窗，Install 按鈕被紅圈標出" />
          </figure>
          <figure>
            <img class="install-shot--banner" src="install/almostdone.jpg" width="1077" height="281" alt="通知寫著每日箴言，App installed" />
          </figure>
        </li>
        <li class="install-step">
          <h2>{bilingual("主頁出現圖示", "The icon appears")}</h2>
          <p>{bilingual("回到手機主頁，會看到「每日箴言」。之後從這個圖示打開即可。", "On the home screen, look for 每日箴言 and open the reading from that icon.")}</p>
          <figure>
            <img src="install/installed.jpg" width="1079" height="1539" alt="手機主頁上的每日箴言圖示，紅圈標出" />
          </figure>
        </li>
      </ol>
      <section class="install-aside" aria-labelledby="install-iphone">
        <h2 id="install-iphone">{bilingual("iPhone", "iPhone")}</h2>
        <p>{bilingual("請用 Safari 打開這個網站。點畫面下方的分享按鈕，再選「加入主畫面」。", "Open this site in Safari. Tap the Share button at the bottom, then “Add to Home Screen”.")}</p>
      </section>
    </main>
    <footer class="site-foot">
      <p class="foot-credit">{bilingual("摩拉維亞每日箴言 · 中文整理", "Moravian Daily Texts")}</p>
      {LOSUNGEN_ATTRIBUTION_HTML}
    </footer>
{TABBAR_HTML}  </div>
</body>
</html>
"""
