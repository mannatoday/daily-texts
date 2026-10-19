from __future__ import annotations

import json
from functools import lru_cache
from html import escape
from pathlib import Path

from daily_texts.application.dto import FormattedOutput
from daily_texts.domain.bible_versions import (
    DEFAULT_VERSION,
    SITE_VERSIONS,
    VERSION_NOTICES,
    gateway_version,
)
from daily_texts.domain.models import LocalizedDailyText, LocalizedWatchword
from daily_texts.infrastructure.formatters._common import (
    biblegateway_url,
    date_title_en,
    date_title_zh,
    lectionary_entries,
    prayer_citation,
)
from daily_texts.infrastructure.formatters.day_payload import day_payload

_FONT_LINKS = """\
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500&family=Noto+Serif+TC:wght@400;500&display=swap" rel="stylesheet" />
"""

# Bump when icon.png changes so browsers refetch the favicon / app icon.
ICON_VERSION = "4"

# "Add to Home Screen" (PWA) support. Paths are relative so they work under the
# GitHub Pages subpath (…/daily-texts/). Shared by every site page.
PWA_HEAD_TAGS = f"""\
  <link rel="manifest" href="site.webmanifest" />
  <link rel="icon" href="icon.png?v={ICON_VERSION}" sizes="any" />
  <link rel="apple-touch-icon" href="apple-touch-icon.png?v={ICON_VERSION}" />
  <meta name="theme-color" content="#f7f6f2" />
  <meta name="mobile-web-app-capable" content="yes" />
  <meta name="apple-mobile-web-app-capable" content="yes" />
  <meta name="apple-mobile-web-app-status-bar-style" content="default" />
  <meta name="apple-mobile-web-app-title" content="每日箴言" />
"""

INSTALL_SCRIPT_TAG = '  <script src="install.js" defer></script>\n'
VERSION_SCRIPT_TAG = '  <script src="version.js" defer></script>\n'

# Runs before the stylesheet so an English preference hides the prayer before paint.
LANG_BOOT_SCRIPT = """\
  <script>
  (function () {
    try {
      var params = new URLSearchParams(window.location.search);
      var lang = params.get("lang");
      if (lang !== "en" && lang !== "zh") {
        var version = params.get("version");
        if (version === "KJV" || version === "NIV" || version === "NLT" || version === "NIRV") lang = "en";
        else if (version) lang = "zh";
        else lang = window.localStorage.getItem("dailyTexts.lang");
      }
      if (lang === "en") {
        document.documentElement.setAttribute("data-lang", "en");
        document.documentElement.lang = "en";
        var title = document.querySelector("title");
        var english = title && title.getAttribute("data-en");
        if (english) title.textContent = english;
      }
    } catch (err) {}
  })();
  </script>
"""


def bilingual(zh: str, en: str) -> str:
    """Chinese text with an English alternate, swapped via html[data-lang]."""
    return (
        f'<span class="i18n-zh">{escape(zh)}</span>'
        f'<span class="i18n-en">{escape(en)}</span>'
    )

# Bottom tab bar shared by every site page. Fixed on phones (icon over label),
# a plain centered row on desktop. The last tab (加到主畫面) is revealed by
# install.js when the page is not already running as an installed app.
_ICON_TODAY = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
    'stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3.6"/>'
    '<path d="M12 2.5v2.2M12 19.3v2.2M4.4 4.4l1.6 1.6M18 18l1.6 1.6M2.5 12h2.2'
    'M19.3 12h2.2M4.4 19.6l1.6-1.6M18 6l1.6-1.6"/></svg>'
)
_ICON_HOME = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
    'stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M4 11.2 12 4.5l8 6.7"/>'
    '<path d="M7 10.2V19.5h10V10.2"/></svg>'
)
_ICON_ABOUT = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
    'stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/>'
    '<path d="M12 11v5"/><circle cx="12" cy="7.6" r="1" fill="currentColor" stroke="none"/></svg>'
)
_ICON_ADD = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
    'stroke-linecap="round" stroke-linejoin="round">'
    '<rect x="4" y="4" width="16" height="16" rx="3.5"/><path d="M12 9v6M9 12h6"/></svg>'
)


def _tab(href: str, zh: str, en: str, icon: str) -> str:
    return (
        f'    <a class="tab" href="{href}">'
        f'<span class="tab__icon" aria-hidden="true">{icon}</span>'
        f'<span class="tab__label">{bilingual(zh, en)}</span></a>\n'
    )


TABBAR_HTML = (
    '  <p id="install-hint" class="install-hint" hidden></p>\n'
    '  <nav class="tabbar" aria-label="主要導覽">\n'
    + _tab("today.html", "今日", "Today", _ICON_TODAY)
    + _tab("index.html", "首頁", "Home", _ICON_HOME)
    + _tab("about.html", "關於", "About", _ICON_ABOUT)
    + '    <button type="button" class="tab install-trigger" hidden>'
    '<span class="tab__icon" aria-hidden="true">' + _ICON_ADD + "</span>"
    f'<span class="tab__label">{bilingual("加到主畫面", "Add to Home")}</span></button>\n'
    "  </nav>\n"
)

# Required by Losungen Nutzungsbedingungen (Herrnhuter Brüdergemeine, Nov 2023).
LOSUNGEN_ATTRIBUTION_HTML = (
    '<p class="foot-attribution" lang="de">'
    "© "
    '<a href="https://www.herrnhuter.de/" rel="noopener noreferrer">'
    "Evangelische Brüder-Unität – Herrnhuter Brüdergemeine"
    "</a>"
    " · "
    '<a href="https://www.losungen.de/" rel="noopener noreferrer">'
    "Weitere Informationen finden Sie hier."
    "</a>"
    "</p>"
)


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
        title_zh = date_title_zh(content)
        title_en = date_title_en(content)
        entries = lectionary_entries(content)
        site_mode = stylesheet_href is not None

        lectionary_block = ""
        if entries:
            refs = "\n".join(
                _reading_row(zh, en, with_link=site_mode) for zh, en in entries
            )
            heading = _heading("經文選讀", "Readings", site_mode=site_mode)
            lectionary_block = f"{heading}{refs}\n"

        source_block = ""
        if include_source_link:
            source_heading = _heading("原文連結", "Source", site_mode=site_mode)
            source_block = (
                f"{source_heading}"
                f'    <p class="source"><a href="{escape(content.source_url, quote=True)}" '
                'rel="noopener noreferrer">'
                "Moravian Daily Texts</a></p>\n"
            )

        if stylesheet_href:
            style_block = (
                f'  <link rel="stylesheet" href="{escape(stylesheet_href, quote=True)}" />\n'
                f"{VERSION_SCRIPT_TAG}"
            )
            boot = LANG_BOOT_SCRIPT
            title_tag = (
                f'<title data-zh="{escape(title_zh, quote=True)} · 摩拉維亞每日箴言" '
                f'data-en="{escape(title_en, quote=True)} · Moravian Daily Texts">'
                f"{escape(title_zh)} · 摩拉維亞每日箴言</title>"
            )
            heading_html = bilingual(title_zh, title_en)
            skip = bilingual("跳至內容", "Skip to content")
        else:
            css = load_devotional_css()
            style_block = f"  <style>\n{css}\n  </style>\n"
            boot = ""
            title_tag = f"<title>{escape(title_zh)} · 摩拉維亞每日箴言</title>"
            heading_html = escape(title_zh)
            skip = "跳至內容"

        version_picker = _version_picker() if site_mode else ""
        bottom_nav = _day_nav(
            prev_href=prev_href,
            next_href=next_href,
            home_href=home_href,
            css_extra="day-nav--bottom",
            bilingual_labels=site_mode,
        )
        footer = _site_footer(site_mode=site_mode)
        data_block = _day_data_script(content) if site_mode else ""
        pwa_head = PWA_HEAD_TAGS if site_mode else ""
        install_script = INSTALL_SCRIPT_TAG if site_mode else ""

        week_block = ""
        if content.week_watchword is not None:
            week_block = (
                f"{_heading('本週守望經文', 'Watchword for the Week', site_mode=site_mode)}"
                f"    {_verse_line(content.week_watchword, 'week')}\n"
                f"    {_ref_line(content.week_watchword, site_mode=site_mode)}\n"
            )

        citation = prayer_citation(content)
        citation_block = (
            f'    <p class="prayer-source">— {escape(citation)}</p>\n' if citation else ""
        )
        prayer_inner = (
            f"{_heading('今日禱告', 'Prayer', site_mode=site_mode)}"
            f'    <p class="prayer">{escape(content.prayer_zh)}</p>\n'
            f"{citation_block}"
        )
        if site_mode:
            prayer_block = f'    <div class="prayer-block">\n{prayer_inner}    </div>\n'
        else:
            prayer_block = prayer_inner

        body = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="color-scheme" content="light dark" />
  <meta name="description" content="摩拉維亞每日箴言 · Moravian Daily Texts 中文版" />
  {title_tag}
{boot}{pwa_head}{_FONT_LINKS}{style_block}{install_script}</head>
<body>
  <a class="skip-link" href="#main">{skip}</a>
  <div class="site-shell">
{version_picker}  <main id="main">
    <article>
    <h1>{heading_html}</h1>
{week_block}{_heading("舊約", "Old Testament", site_mode=site_mode)}    {_verse_line(content.ot, "ot")}
    {_ref_line(content.ot, site_mode=site_mode)}
{_heading("新約", "New Testament", site_mode=site_mode)}    {_verse_line(content.nt, "nt")}
    {_ref_line(content.nt, site_mode=site_mode)}
{prayer_block}{lectionary_block}{source_block}    </article>
{bottom_nav}  </main>
{footer}  </div>
{data_block}</body>
</html>
"""
        return FormattedOutput(
            format="html",
            content=body,
            filename="daily-text.html",
        )


def _day_data_script(content: LocalizedDailyText) -> str:
    payload = day_payload(content)
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # Prevent </script> breakouts in rare edge cases.
    encoded = encoded.replace("<", "\\u003c")
    return f'  <script type="application/json" id="day-data">{encoded}</script>\n'


def _verse_line(watchword: LocalizedWatchword, role: str) -> str:
    return (
        f'<p class="verse" data-verse="{escape(role, quote=True)}">'
        f"{escape(watchword.text_zh)}</p>"
    )


def _heading(zh: str, en: str, *, site_mode: bool) -> str:
    inner = bilingual(zh, en) if site_mode else escape(zh)
    return f"    <h2>{inner}</h2>\n"


def _lang_toggle() -> str:
    return """    <div class="lang-toggle" role="group" aria-label="Language">
      <button type="button" class="lang-toggle__btn" data-set-lang="zh" aria-pressed="true">中文</button>
      <button type="button" class="lang-toggle__btn" data-set-lang="en" aria-pressed="false">EN</button>
    </div>
"""


def _version_picker() -> str:
    options = "\n".join(
        f'      <option value="{code}"'
        f'{" selected" if code == DEFAULT_VERSION else ""}>{label}</option>'
        for code, label in SITE_VERSIONS
    )
    return f"""  <div class="version-picker">
{_lang_toggle()}    <label class="version-picker__label" for="bible-version">{bilingual("閱讀譯本", "Version")}</label>
    <select id="bible-version" class="version-picker__select" autocomplete="off">
{options}
    </select>
  </div>
"""


def _ref_line(watchword: LocalizedWatchword, *, site_mode: bool = False) -> str:
    if site_mode:
        return f"<p class=\"ref\">— {bilingual(watchword.reference_zh, watchword.reference)}</p>"
    return f"<p class=\"ref\">— {escape(watchword.reference_zh)}</p>"


def _reading_row(zh_label: str, english_ref: str, *, with_link: bool) -> str:
    if not with_link:
        return f'    <p class="reading"><span class="reading__ref">{escape(zh_label)}</span></p>'

    cleaned = english_ref.strip().replace("–", "-").replace("—", "-")
    gw = gateway_version(DEFAULT_VERSION)
    url = biblegateway_url(cleaned, version=gw)
    ref = bilingual(zh_label, cleaned)
    link_label = bilingual("[閱讀]", "[Read]")
    return (
        f'    <p class="reading">'
        f'<span class="reading__ref">{ref}</span>'
        f'<a class="reading__open" href="{escape(url, quote=True)}" '
        f'data-ref="{escape(cleaned, quote=True)}" '
        f'data-label-zh="{escape(zh_label, quote=True)}" '
        f'target="_blank" rel="noopener noreferrer" '
        f'title="在 Bible Gateway 閱讀" '
        f'aria-label="閱讀 {escape(zh_label)}">{link_label}</a></p>'
    )


def _day_nav(
    *,
    prev_href: str | None,
    next_href: str | None,
    home_href: str | None,
    css_extra: str = "",
    bilingual_labels: bool = False,
) -> str:
    if prev_href is None and next_href is None and home_href is None:
        return ""

    classes = "day-nav" + (f" {css_extra}" if css_extra else "")

    def _label(zh: str, en: str, *, prefix: str = "", suffix: str = "") -> str:
        text = bilingual(zh, en) if bilingual_labels else escape(zh)
        return f"{prefix}{text}{suffix}"

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
            f"{_label('首頁', 'Home')}</a>\n"
        )
    return (
        f'  <nav class="{classes}" aria-label="日期導覽">\n'
        + _link(prev_href, _label("前一日", "Previous", prefix="← "), "day-nav__prev")
        + home
        + _link(next_href, _label("後一日", "Next", suffix=" →"), "day-nav__next")
        + "  </nav>\n"
    )


def _site_footer(*, site_mode: bool) -> str:
    if not site_mode:
        return (
            '  <footer class="site-foot">\n'
            '    <p class="foot-credit">摩拉維亞每日箴言 · Daily Texts</p>\n'
            f"    {LOSUNGEN_ATTRIBUTION_HTML}\n"
            "  </footer>\n"
        )
    notice = escape(VERSION_NOTICES["WCB"])
    credit = bilingual("摩拉維亞每日箴言 · 中文整理", "Moravian Daily Texts")
    return f"""  <footer class="site-foot">
    <p class="foot-credit">{credit}</p>
    {LOSUNGEN_ATTRIBUTION_HTML}
    <p id="version-notice" class="version-notice" hidden>{notice}</p>
  </footer>
{TABBAR_HTML}"""
