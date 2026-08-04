from __future__ import annotations

import logging
import re
from datetime import date
from html import escape
from pathlib import Path

from daily_texts.application.dto import FormattedOutput, PublishResult
from daily_texts.domain.models import LocalizedDailyText
from daily_texts.infrastructure.formatters._common import format_date_zh
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

    def __init__(
        self,
        site_dir: Path | None = None,
        *,
        include_source_link: bool = False,
    ) -> None:
        self._site_dir = Path(site_dir) if site_dir is not None else Path("./site")
        self._html = HtmlFormatter()
        self._include_source_link = include_source_link

    async def publish(
        self,
        outputs: list[FormattedOutput],
        content: LocalizedDailyText,
    ) -> PublishResult:
        self._site_dir.mkdir(parents=True, exist_ok=True)
        self._write_stylesheet()
        self._write_version_js()
        self._write_about_page()

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
        index_path = self._site_dir / "index.html"
        index_path.write_text(self._build_index(days), encoding="utf-8")
        archive_path = self._site_dir / "archive.html"
        archive_path.write_text(self._build_archive(days), encoding="utf-8")

        message = f"Wrote {day_path}, about.html, archive.html, and updated {index_path}"
        logger.info(message)
        return PublishResult(channel=self.channel, success=True, message=message)

    def _write_stylesheet(self) -> None:
        css_path = self._site_dir / "styles.css"
        css_path.write_text(load_devotional_css() + "\n", encoding="utf-8")

    def _write_version_js(self) -> None:
        (self._site_dir / "version.js").write_text(_VERSION_JS, encoding="utf-8")

    def _write_about_page(self) -> None:
        (self._site_dir / "about.html").write_text(_ABOUT_HTML, encoding="utf-8")

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
                f'    <a class="today-card" href="{latest.isoformat()}.html">'
                f'<span class="today-card__label">今日經文</span>'
                f'<span class="today-card__date">{latest_label}</span>'
                "</a>\n"
                '    <h2 class="archive-title">最近三天</h2>\n'
                f'    <ul class="archive-list">\n{items}\n    </ul>\n'
                '    <p class="archive-more"><a href="archive.html">歷日檔案</a></p>\n'
            )

        return _shell_page(
            title="摩拉維亞每日經文",
            body=body,
            extra_class="site-index",
            foot_links=(
                ('archive.html', "歷日檔案"),
                ('about.html', "關於"),
            ),
        )

    def _build_archive(self, days: list[date] | None = None) -> str:
        days = days if days is not None else self._list_day_pages()
        if not days:
            body = '    <p class="empty">尚無每日經文。</p>\n'
        else:
            items = "\n".join(_day_list_item(d) for d in days)
            body = (
                '    <h1 class="archive-page-title">歷日檔案</h1>\n'
                f'    <ul class="archive-list">\n{items}\n    </ul>\n'
            )

        return _shell_page(
            title="歷日檔案 · 摩拉維亞每日經文",
            body=body,
            extra_class="site-index archive-page",
            top_nav=True,
            foot_links=(
                ('index.html', "首頁"),
                ('about.html', "關於"),
            ),
        )


def _day_list_item(day: date) -> str:
    return (
        "      <li>"
        f'<a href="{day.isoformat()}.html">'
        f"<span>{escape(format_date_zh(day))}</span>"
        f'<span class="iso">{day.isoformat()}</span>'
        "</a></li>"
    )


def _shell_page(
    *,
    title: str,
    body: str,
    extra_class: str,
    foot_links: tuple[tuple[str, str], ...],
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
        brand = """    <h1 class="brand">摩拉維亞每日經文</h1>
    <p class="subtitle">Moravian Daily Texts • 中文版</p>
    <p class="lede">以神的話開始每一天</p>
"""
    foot = "\n".join(
        f'        <a href="{href}">{label}</a>' for href, label in foot_links
    )
    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="color-scheme" content="light dark" />
  <meta name="description" content="摩拉維亞每日經文 · Moravian Daily Texts 中文版" />
  <title>{escape(title)}</title>
{_FONT_LINKS}  <link rel="stylesheet" href="styles.css" />
</head>
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
      <nav class="foot-nav" aria-label="頁尾導覽">
{foot}
      </nav>
      <p class="foot-credit">摩拉維亞每日經文 · 非官方中文整理</p>
    </footer>
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
    prev_href = f"{prev_day.isoformat()}.html" if prev_day else None
    next_href = f"{next_day.isoformat()}.html" if next_day else None
    return prev_href, next_href


_NAV_BLOCK = re.compile(
    r'<nav class="day-nav(?:\s+day-nav--bottom)?"[^>]*>.*?</nav>\s*',
    re.DOTALL,
)


def _replace_day_nav(html: str, prev_href: str | None, next_href: str | None) -> str:
    from daily_texts.infrastructure.formatters.html import _day_nav

    top = _day_nav(prev_href=prev_href, next_href=next_href, home_href="index.html")
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
    for i, match in enumerate(matches):
        parts.append(html[last : match.start()])
        if i == 0:
            parts.append(top.lstrip() if match.start() > 0 else top)
        else:
            parts.append(bottom.lstrip())
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
    return GATEWAY[siteCode] || GATEWAY.RCUV || siteCode;
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
    var links = document.querySelectorAll("a.reading__open");
    Array.prototype.forEach.call(links, function (link) {
      var ref = link.getAttribute("data-ref");
      if (!ref) return;
      link.href =
        "https://www.biblegateway.com/passage/?search=" +
        encodeURIComponent(ref) +
        "&version=" +
        encodeURIComponent(gatewayCode(siteCode));
    });
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

_ABOUT_HTML = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="color-scheme" content="light dark" />
  <meta name="description" content="關於 Moravian Daily Texts 與本站中文版" />
  <title>關於 · 摩拉維亞每日經文</title>
{_FONT_LINKS}  <link rel="stylesheet" href="styles.css" />
</head>
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
      <p>Moravian Daily Texts（摩拉維亞每日經文）自 1731 年開始出版，是歷史最悠久、持續出版的每日靈修讀本之一。數百年來，它陪伴全球信徒以神的話開始每一天。</p>

      <h2>每日內容</h2>
      <p>每一天通常包含：</p>
      <ul>
        <li>一段舊約守望經文（Watchword）</li>
        <li>一段新約經文</li>
        <li>一段簡短禱告</li>
        <li>讀經進度（詩篇、舊約、新約）</li>
      </ul>
      <p>舊約與新約並陳，提醒我們整本聖經彼此呼應：神的應許與成全、律法與福音，都在每日閱讀中相遇。</p>

      <h2>讀經計畫</h2>
      <p>除了當日兩段守望經文，Daily Texts 也提供當日讀經進度，通常包括詩篇（Psalm）、一段舊約經文，以及一段新約經文，幫助讀者按著節奏走完更廣的經卷。</p>

      <h2>關於本站中文版</h2>
      <p class="meta">本站依據官方每日內容整理，經文引用中文聖經版本（如和合本相關版本），禱告另行翻譯為繁體中文。本站為個人靈修整理用途，<strong>非官方出版物</strong>。</p>

      <h2>版權與來源</h2>
      <p class="meta">英文原文來自 <a href="https://www.moravian.org/the-daily-texts/" rel="noopener noreferrer">Moravian Church in America — The Daily Texts</a>。中文經文文字另依公開聖經資源引用；使用前請自行確認相關授權與使用規範。</p>
      <p class="meta">若需正式出版、轉載或商業用途，請聯繫原文出版單位，並遵守各聖經譯本之版權規定。</p>
    </main>
    <footer class="site-foot">
      <nav class="foot-nav" aria-label="頁尾導覽">
        <a href="index.html">首頁</a>
        <a href="archive.html">歷日檔案</a>
      </nav>
      <p class="foot-credit">摩拉維亞每日經文 · 非官方中文整理</p>
    </footer>
  </div>
</body>
</html>
"""
