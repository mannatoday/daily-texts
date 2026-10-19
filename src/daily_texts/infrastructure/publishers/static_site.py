from __future__ import annotations

import calendar
import logging
import re
from datetime import date
from html import escape
from pathlib import Path

from daily_texts.application.dto import FormattedOutput, PublishResult
from daily_texts.domain.models import LocalizedDailyText
from daily_texts.infrastructure.formatters._common import format_date_zh
from daily_texts.infrastructure.formatters.html import (
    ICON_VERSION,
    INSTALL_SCRIPT_TAG,
    LOSUNGEN_ATTRIBUTION_HTML,
    PWA_HEAD_TAGS,
    TABBAR_HTML,
    HtmlFormatter,
    load_devotional_css,
)

logger = logging.getLogger(__name__)

_DAY_PAGE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.html$")
# App icon shipped with the package (src/daily_texts/inputs/icon.png).
_ICON_SOURCE = Path(__file__).resolve().parents[2] / "inputs" / "icon.png"
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
        self._write_service_worker()
        self._write_about_page()

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

        message = (
            f"Wrote {day_path}, about.html, today.html, archive.html, "
            f"and updated {index_path}"
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

    def _write_service_worker(self) -> None:
        (self._site_dir / "sw.js").write_text(_SW_JS, encoding="utf-8")

    def _write_about_page(self) -> None:
        (self._site_dir / "about.html").write_text(_ABOUT_HTML, encoding="utf-8")

    def _write_today_page(self, latest: date | None = None) -> None:
        """Copy the newest day page to today.html so the URL stays stable."""
        if latest is None:
            days = self._list_day_pages()
            latest = days[0] if days else None
        today_path = self._site_dir / "today.html"
        if latest is None:
            today_path.write_text(
                _shell_page(
                    title="今日經文 · 摩拉維亞每日箴言",
                    body='    <p class="empty">尚無每日經文。</p>\n'
                    '    <p class="archive-more"><a href="index.html">回首頁</a></p>\n',
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
            body = '    <p class="empty">尚無每日經文。</p>\n'
        else:
            latest = days[0]
            latest_label = escape(format_date_zh(latest))
            recent = days[:3]
            items = "\n".join(_day_list_item(d) for d in recent)
            body = (
                f'    <a class="today-card" href="today.html">'
                f'<span class="today-card__label">閱讀今日經文</span>'
                f'<span class="today-card__date">{latest_label}</span>'
                "</a>\n"
                '    <h2 class="archive-title">最近三天</h2>\n'
                f'    <ul class="archive-list">\n{items}\n    </ul>\n'
                '    <p class="archive-more"><a href="archive.html">歷日檔案</a></p>\n'
            )

        return _shell_page(
            title="摩拉維亞每日箴言",
            body=body,
            extra_class="site-index",
        )

    def _build_archive(self, days: list[date] | None = None) -> str:
        days = days if days is not None else self._list_day_pages()
        if not days:
            body = '    <p class="empty">尚無每日經文。</p>\n'
        else:
            body = _archive_markup(days)

        return _shell_page(
            title="歷日檔案 · 摩拉維亞每日箴言",
            body=body,
            extra_class="site-index archive-page",
            top_nav=True,
        )


def _day_list_item(day: date) -> str:
    return (
        "      <li>"
        f'<a href="{day.isoformat()}.html">'
        f"<span>{escape(format_date_zh(day))}</span>"
        f'<span class="iso">{day.isoformat()}</span>'
        "</a></li>"
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
        '    <h1 class="archive-page-title">歷日檔案</h1>\n'
        f'    <div class="cal">\n{panels}\n    </div>\n'
        '    <h2 class="archive-months-title">依月份</h2>\n'
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
    if with_year:
        return f"{year} 年 {month} 月"
    return f"{month} 月"


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
    title = f"{year} 年 {month} 月"
    heads = "".join(f'<span class="cal-dow">{label}</span>' for label in ("日", "一", "二", "三", "四", "五", "六"))
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
        f'          <div class="cal-grid" aria-label="{title}">\n'
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


def _shell_page(
    *,
    title: str,
    body: str,
    extra_class: str,
    top_nav: bool = False,
) -> str:
    nav = ""
    if top_nav:
        nav = """    <nav class="day-nav" aria-label="網站導覽">
      <a class="day-nav__prev" href="index.html">← 首頁</a>
      <span class="day-nav__home" aria-current="page">歷日檔案</span>
      <span class="day-nav__next" aria-disabled="true">後一日 →</span>
    </nav>
"""
    brand = ""
    if not top_nav:
        brand = """    <h1 class="brand">摩拉維亞每日箴言</h1>
    <p class="subtitle">Moravian Daily Texts • 中文版</p>
    <p class="lede">以神的話開始每一天</p>
"""
    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="color-scheme" content="light dark" />
  <meta name="description" content="摩拉維亞每日箴言 · Moravian Daily Texts 中文版" />
  <title>{escape(title)}</title>
{PWA_HEAD_TAGS}{_FONT_LINKS}  <link rel="stylesheet" href="styles.css" />
{INSTALL_SCRIPT_TAG}</head>
<body>
  <a class="skip-link" href="#main">跳至內容</a>
  <div class="site-shell {extra_class}">
{nav}    <main id="main">
{brand}{body}    </main>
    <footer class="site-foot">
      <section class="about-blurb" aria-labelledby="about-blurb-title">
        <h2 id="about-blurb-title">關於 Moravian Daily Texts</h2>
        <p>Moravian Daily Texts 自 1731 年開始出版，是歷史最悠久、持續出版的每日靈修讀本之一。每天包含一段舊約經文、一段新約經文、禱告及讀經進度，陪伴全球信徒以神的話開始每一天。</p>
      </section>
      <p class="foot-credit">摩拉維亞每日箴言 · 中文整理</p>
      {LOSUNGEN_ATTRIBUTION_HTML}
    </footer>
{TABBAR_HTML}  </div>
</body>
</html>
"""


def _as_today_page(day_html: str) -> str:
    """Stable today.html: retitle, and drop the about blurb.

    The homepage already introduces Moravian Daily Texts, and the tab bar
    links to the about page, so the daily reading page stays on the texts.
    """
    html = _TITLE_TAG.sub(
        "<title>今日經文 · 摩拉維亞每日箴言</title>",
        day_html,
        count=1,
    )
    return _ABOUT_BLURB_SECTION.sub("", html, count=1)


_ABOUT_BLURB_SECTION = re.compile(
    r'[ \t]*<section class="about-blurb"[^>]*>.*?</section>\n',
    re.DOTALL,
)


_TITLE_TAG = re.compile(r"<title>.*?</title>", re.DOTALL)


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
// Multi-version watchword renderer + lectionary Bible Gateway links.
// Priority: ?version= → localStorage → embedded default (RCUV).
(function () {
  "use strict";
  var KEY = "dailyTexts.bibleVersion";
  var GATEWAY = {
    CUV: "CUV",
    RCUV: "RCU17TS",
    CNVT: "CNVT",
    CSBT: "CSBT"
  };
  var NOTICE_VERSION = "WCB";

  var select = document.getElementById("bible-version");
  if (!select) return;

  var dataEl = document.getElementById("day-data");
  var day = null;
  if (dataEl) {
    try {
      day = JSON.parse(dataEl.textContent || "{}");
    } catch (err) {
      day = null;
    }
  }

  var validCodes = Array.prototype.map.call(select.options, function (opt) {
    return opt.value;
  });
  var defaultVersion =
    (day && day.default_version) || select.value || "RCUV";

  function fromQuery() {
    try {
      return new URLSearchParams(window.location.search).get("version");
    } catch (err) {
      return null;
    }
  }

  function fromStorage() {
    try {
      return window.localStorage.getItem(KEY);
    } catch (err) {
      return null;
    }
  }

  function resolveVersion() {
    var q = fromQuery();
    if (q && validCodes.indexOf(q) >= 0) return q;
    var s = fromStorage();
    if (s && validCodes.indexOf(s) >= 0) return s;
    if (validCodes.indexOf(defaultVersion) >= 0) return defaultVersion;
    return validCodes[0];
  }

  function gatewayCode(siteCode) {
    return Object.prototype.hasOwnProperty.call(GATEWAY, siteCode)
      ? GATEWAY[siteCode]
      : null;
  }

  function textFor(block, siteCode) {
    if (!block || !block.translations) return null;
    return (
      block.translations[siteCode] ||
      block.translations[defaultVersion] ||
      null
    );
  }

  function applyVerses(siteCode) {
    if (!day) return;
    var map = { week: day.week_watchword, ot: day.ot, nt: day.nt };
    Object.keys(map).forEach(function (role) {
      var el = document.querySelector('[data-verse="' + role + '"]');
      if (!el) return;
      var text = textFor(map[role], siteCode);
      if (text) el.textContent = text;
    });
  }

  function applyReadingLinks(siteCode) {
    var code = gatewayCode(siteCode);
    var links = document.querySelectorAll("a.reading__open");
    Array.prototype.forEach.call(links, function (link) {
      var ref = link.getAttribute("data-ref");
      if (!ref) return;
      if (!code) {
        link.hidden = true;
        return;
      }
      link.hidden = false;
      link.href =
        "https://www.biblegateway.com/passage/?search=" +
        encodeURIComponent(ref) +
        "&version=" +
        encodeURIComponent(code);
    });
  }

  function applyNotice(siteCode) {
    var note = document.getElementById("version-notice");
    if (!note) return;
    note.hidden = siteCode !== NOTICE_VERSION;
  }

  function syncUrl(siteCode) {
    try {
      var url = new URL(window.location.href);
      url.searchParams.set("version", siteCode);
      window.history.replaceState({}, "", url.toString());
    } catch (err) {
      /* file:// or unsupported */
    }
  }

  function apply(siteCode) {
    select.value = siteCode;
    applyVerses(siteCode);
    applyReadingLinks(siteCode);
    applyNotice(siteCode);
    try {
      window.localStorage.setItem(KEY, siteCode);
    } catch (err) {
      /* ignore */
    }
    syncUrl(siteCode);
  }

  apply(resolveVersion());

  select.addEventListener("change", function () {
    apply(select.value);
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

# "Add to Home Screen" sits in the footer nav, same weight as the other links.
# The 加到主畫面 tab lives in the shared bottom tab bar but stays hidden until
# this script confirms the page is not already running as an installed app.
# Chromium uses the native install prompt when the browser offers one; other
# browsers get a short platform-specific hint above the bar.
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
    if (isStandalone()) return;

    var triggers = document.querySelectorAll(".install-trigger");
    if (!triggers.length) return;

    var hint = document.getElementById("install-hint");
    var ua = window.navigator.userAgent || "";
    var isIOS =
      /iphone|ipad|ipod/i.test(ua) ||
      (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1);
    var isAndroid = /android/i.test(ua);
    var deferredPrompt = null;

    for (var i = 0; i < triggers.length; i++) {
      triggers[i].hidden = false;
    }

    function hintText() {
      if (isIOS) {
        return "請用 Safari 開啟這個網站。點畫面最下方的「分享」，再選「加入主畫面」。";
      }
      if (isAndroid) {
        return "請先刪掉主畫面上舊的捷徑。再到 Chrome 選單選「安裝應用程式」。裝好後圖示不會再有 Chrome 小標。";
      }
      return "在瀏覽器選單選擇「安裝」或「加到主畫面」。";
    }

    function onClick() {
      if (deferredPrompt) {
        deferredPrompt.prompt();
        deferredPrompt.userChoice.then(function () {
          deferredPrompt = null;
        });
        return;
      }
      if (!hint) return;
      hint.hidden = !hint.hidden;
      if (!hint.hidden) hint.textContent = hintText();
    }

    for (var j = 0; j < triggers.length; j++) {
      triggers[j].addEventListener("click", onClick);
    }

    window.addEventListener("beforeinstallprompt", function (e) {
      e.preventDefault();
      deferredPrompt = e;
    });

    window.addEventListener("appinstalled", function () {
      deferredPrompt = null;
      for (var k = 0; k < triggers.length; k++) {
        triggers[k].hidden = true;
      }
      if (hint) hint.hidden = true;
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
  <meta name="description" content="關於 Moravian Daily Texts 與本站中文版" />
  <title>關於 · 摩拉維亞每日箴言</title>
{PWA_HEAD_TAGS}{_FONT_LINKS}  <link rel="stylesheet" href="styles.css" />
{INSTALL_SCRIPT_TAG}</head>
<body>
  <a class="skip-link" href="#main">跳至內容</a>
  <div class="site-shell about-page">
    <nav class="day-nav" aria-label="網站導覽">
      <a class="day-nav__prev" href="index.html">← 首頁</a>
      <span class="day-nav__home" aria-current="page">關於</span>
      <span class="day-nav__next" aria-disabled="true">後一日 →</span>
    </nav>
    <main id="main">
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
      <p>這段禱文按當天兩節挑選，並加入華人文化裡的聖詩、禮文與靈修文字，例如趙紫宸、吳經熊、賈玉銘、王明道、宋尚節的作品，以及歷代中文聖詩與公禱文。</p>

      <h2>讀經進度</h2>
      <p>頁面上稱為「經文選讀」。詩篇、舊約、新約各自按順序往下讀，與當天兩節守望經文各走各的。</p>
      <p>平日（星期一至六）三條一起推進。長詩篇拆成幾天；舊約大約一天一到兩章，新約大約半章到一章，切在段落結束的地方。</p>
      <p>主日和教會年的特別日改讀當天經課：詩篇、舊約、書信、福音。連續讀先停一下，下一個平日再從停下來的地方接回去。</p>
      <p>照這個進度，詩篇大約一年讀完一遍；詩篇以外的舊約與新約大約兩年讀完。一年大約讀完整本聖經的一半。跟著每天的選讀走，大約兩年可以讀完聖經一遍。</p>

      <h2>關於本站中文版</h2>
      <p class="meta">本站中文版依官方每日經文章節編排，目前不是翻譯版。經文正文引自已獲全世界使用授權的中文譯本，可在頁首切換。今日禱告依當天兩節挑選，並加入華人文化中的聖詩與禱文。本站供個人靈修使用，<strong>非官方出版物</strong>。</p>

      <h2>版權與來源</h2>
      <p class="meta">每日舊約守望經文與新約經文的章節，出自官方德文《Die Losungen》，由 <a href="https://www.herrnhuter.de/" rel="noopener noreferrer">Evangelische Brüder-Unität – Herrnhuter Brüdergemeine</a> 出版。更多資訊見 <a href="https://www.losungen.de/" rel="noopener noreferrer">www.losungen.de</a>。</p>
      <p class="meta" lang="de">© <a href="https://www.herrnhuter.de/" rel="noopener noreferrer">Evangelische Brüder-Unität – Herrnhuter Brüdergemeine</a>. <a href="https://www.losungen.de/" rel="noopener noreferrer">Weitere Informationen finden Sie hier.</a></p>
      <p class="meta">英文版每日內容見 <a href="https://www.moravian.org/the-daily-texts/" rel="noopener noreferrer">Moravian Church in America — The Daily Texts</a>。讀經進度依北美摩拉維亞教會的讀經安排，說明見 <a href="https://www.moravian.org/2018/07/using-the-moravian-daily-texts/" rel="noopener noreferrer">Using the Moravian Daily Texts</a>。</p>
      <p class="meta">中文經文正文引自已獲全世界使用授權的譯本：和合本、和合本修訂版、新譯本、中文標準譯本、環球聖經譯本。各譯本版權仍屬原出版機構。選用《環球聖經譯本》時，頁腳另標環球聖經公會的版權。</p>
      <p class="meta">今日禱告的出處是當天頁面句末的署名（作者與作品）。聖詩與禱文的版權依各作品而定。</p>
      <p class="meta">若需正式出版、轉載或商業用途，請另洽原文出版單位，並遵守各譯本與作品的版權規定。</p>
    </main>
    <footer class="site-foot">
      <p class="foot-credit">摩拉維亞每日箴言 · 中文整理</p>
      {LOSUNGEN_ATTRIBUTION_HTML}
    </footer>
{TABBAR_HTML}  </div>
</body>
</html>
"""
