from __future__ import annotations

from functools import lru_cache
from html import escape
from pathlib import Path

from daily_texts.application.dto import FormattedOutput
from daily_texts.domain.models import LocalizedDailyText
from daily_texts.infrastructure.formatters._common import (
    biblegateway_url,
    date_title_zh,
    lectionary_entries,
)

_FONT_LINKS = """\
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500&family=Noto+Serif+TC:wght@400;500&display=swap" rel="stylesheet" />
"""

_ABOUT_BLURB = (
    "Moravian Daily Texts 自 1731 年開始出版，是歷史最悠久、持續出版的每日靈修讀本之一。"
    "每天包含一段舊約經文、一段新約經文、禱告及讀經進度，陪伴全球信徒以神的話開始每一天。"
)

# Traditional Chinese versions available on Bible Gateway for the reading links.
BIBLE_VERSIONS: list[tuple[str, str]] = [
    ("CUV", "和合本"),
    ("RCU17TS", "和合本修訂版"),
    ("CNVT", "新譯本"),
    ("CCBT", "當代譯本"),
    ("CSBT", "中文標準譯本"),
]
DEFAULT_BIBLE_VERSION = "CUV"


@lru_cache(maxsize=1)
def load_devotional_css() -> str:
    path = Path(__file__).with_name("devotional.css")
    return path.read_text(encoding="utf-8")


class HtmlFormatter:
    format_name = "html"

    def format(
        self,
        content: LocalizedDailyText,
        *,
        include_source_link: bool = True,
        stylesheet_href: str | None = None,
        prev_href: str | None = None,
        next_href: str | None = None,
        home_href: str | None = None,
    ) -> FormattedOutput:
        title = escape(date_title_zh(content))
        entries = lectionary_entries(content)
        site_mode = stylesheet_href is not None

        lectionary_block = ""
        if entries:
            refs = "\n".join(_reading_row(zh, en) for zh, en in entries)
            lectionary_block = f"    <h2>經文選讀</h2>\n{refs}\n"

        source_block = ""
        if include_source_link:
            source_block = (
                "    <h2>原文連結</h2>\n"
                f'    <p class="source"><a href="{escape(content.source_url, quote=True)}" '
                'rel="noopener noreferrer">'
                "Moravian Daily Texts</a></p>\n"
            )

        if stylesheet_href:
            style_block = (
                f'  <link rel="stylesheet" href="{escape(stylesheet_href, quote=True)}" />\n'
                '  <script src="version.js" defer></script>\n'
            )
        else:
            css = load_devotional_css()
            style_block = f"  <style>\n{css}\n  </style>\n"

        version_picker = _version_picker() if site_mode else ""
        nav = _day_nav(prev_href=prev_href, next_href=next_href, home_href=home_href)
        bottom_nav = ""
        if nav:
            bottom_nav = _day_nav(
                prev_href=prev_href,
                next_href=next_href,
                home_href=home_href,
                css_extra="day-nav--bottom",
            )
        footer = _site_footer(site_mode=site_mode)

        week_block = ""
        if content.week_watchword is not None:
            week_block = (
                "    <h2>本週守望經文</h2>\n"
                f'    <p class="verse">{escape(content.week_watchword.text_zh)}</p>\n'
                f"    {_ref_line(content.week_watchword.reference_zh, content.week_watchword.reference, site_mode)}\n"
            )

        ot_ref = _ref_line(content.ot.reference_zh, content.ot.reference, site_mode)
        nt_ref = _ref_line(content.nt.reference_zh, content.nt.reference, site_mode)

        body = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="color-scheme" content="light dark" />
  <meta name="description" content="摩拉維亞每日經文 · Moravian Daily Texts 中文版" />
  <title>{title} · 摩拉維亞每日經文</title>
{_FONT_LINKS}{style_block}</head>
<body>
  <a class="skip-link" href="#main">跳至內容</a>
  <div class="site-shell">
{version_picker}{nav}  <main id="main">
    <article>
    <h1>{title}</h1>
{week_block}    <h2>舊約</h2>
    <p class="verse">{escape(content.ot.text_zh)}</p>
    {ot_ref}
    <h2>新約</h2>
    <p class="verse">{escape(content.nt.text_zh)}</p>
    {nt_ref}
    <h2>今日禱告</h2>
    <p class="prayer">{escape(content.prayer_zh)}</p>
{lectionary_block}{source_block}    </article>
{bottom_nav}  </main>
{footer}  </div>
</body>
</html>
"""
        return FormattedOutput(
            format="html",
            content=body,
            filename="daily-text.html",
        )


def _version_picker() -> str:
    options = "\n".join(
        f'      <option value="{code}">{label}</option>'
        for code, label in BIBLE_VERSIONS
    )
    return f"""  <div class="version-picker">
    <label class="version-picker__label" for="bible-version">閱讀譯本</label>
    <select id="bible-version" class="version-picker__select" autocomplete="off">
{options}
    </select>
    <span class="version-picker__hint" id="bible-version-hint" aria-live="polite">用於下方［閱讀］連結</span>
  </div>
"""


def _gateway_link(zh_label: str, english_ref: str) -> str:
    cleaned = english_ref.strip().replace("–", "-").replace("—", "-")
    url = biblegateway_url(cleaned, version=DEFAULT_BIBLE_VERSION)
    return (
        f'<a class="reading__open" href="{escape(url, quote=True)}" '
        f'data-ref="{escape(cleaned, quote=True)}" '
        f'target="_blank" rel="noopener noreferrer" '
        f'title="在 Bible Gateway 閱讀和合本" '
        f'aria-label="閱讀 {escape(zh_label)}（和合本）">'
        f'<span class="reading__open-label">[閱讀 · 和合本]</span></a>'
    )


def _ref_line(zh_label: str, english_ref: str, site_mode: bool) -> str:
    if site_mode:
        return (
            f'<p class="ref">— {escape(zh_label)} '
            f"{_gateway_link(zh_label, english_ref)}</p>"
        )
    return f'<p class="ref">— {escape(zh_label)}</p>'


def _reading_row(zh_label: str, english_ref: str) -> str:
    return (
        f'    <p class="reading">'
        f'<span class="reading__ref">{escape(zh_label)}</span>'
        f"{_gateway_link(zh_label, english_ref)}</p>"
    )


def _day_nav(
    *,
    prev_href: str | None,
    next_href: str | None,
    home_href: str | None,
    css_extra: str = "",
) -> str:
    if prev_href is None and next_href is None and home_href is None:
        return ""

    classes = "day-nav" + (f" {css_extra}" if css_extra else "")

    def _link(href: str | None, label: str, css: str) -> str:
        if href:
            return (
                f'    <a class="{css}" href="{escape(href, quote=True)}">{label}</a>\n'
            )
        return f'    <span class="{css}" aria-disabled="true">{label}</span>\n'

    home = ""
    if home_href:
        home = (
            f'    <a class="day-nav__home" href="{escape(home_href, quote=True)}">'
            "歷日檔案</a>\n"
        )
    return (
        f'  <nav class="{classes}" aria-label="日期導覽">\n'
        + _link(prev_href, "← 前一日", "day-nav__prev")
        + home
        + _link(next_href, "後一日 →", "day-nav__next")
        + "  </nav>\n"
    )


def _site_footer(*, site_mode: bool) -> str:
    if not site_mode:
        return (
            '  <footer class="site-foot">\n'
            '    <p class="foot-credit">摩拉維亞每日經文 · Daily Texts</p>\n'
            "  </footer>\n"
        )
    return f"""  <footer class="site-foot">
    <section class="about-blurb" aria-labelledby="about-blurb-title">
      <h2 id="about-blurb-title">關於 Moravian Daily Texts</h2>
      <p>{_ABOUT_BLURB}</p>
      <p class="more"><a href="about.html">了解更多</a></p>
    </section>
    <nav class="foot-nav" aria-label="頁尾導覽">
      <a href="index.html">歷日檔案</a>
      <a href="about.html">關於</a>
    </nav>
    <p class="foot-credit">摩拉維亞每日經文 · 非官方中文整理</p>
  </footer>
"""
