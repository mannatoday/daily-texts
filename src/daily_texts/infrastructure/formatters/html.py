from __future__ import annotations

import json
from functools import lru_cache
from html import escape
from pathlib import Path

from daily_texts.application.dto import FormattedOutput
from daily_texts.domain.bible_versions import (
    DEFAULT_ENGLISH_VERSION,
    DEFAULT_VERSION,
    ENGLISH_VERSIONS,
    SITE_VERSIONS,
    VERSION_NOTICES,
    gateway_version,
)
from daily_texts.domain.models import LocalizedDailyText, LocalizedWatchword
from daily_texts.infrastructure.formatters._common import (
    _MONTHS_EN,
    biblegateway_url,
    date_title_en,
    date_title_zh,
    lectionary_entries,
    prayer_citation,
    prayer_media_url,
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
# GitHub Pages subpath (…/daily-texts/). English pages live in /en/ and pass
# prefix="../". The manifest stays at the site root, so start_url remains today.html.
def pwa_head_tags(prefix: str = "", *, lang: str = "zh") -> str:
    title = "Daily Texts" if lang == "en" else "每日箴言"
    return f"""\
  <link rel="manifest" href="{prefix}site.webmanifest" />
  <link rel="icon" href="{prefix}icon.png?v={ICON_VERSION}" sizes="any" />
  <link rel="apple-touch-icon" href="{prefix}apple-touch-icon.png?v={ICON_VERSION}" />
  <meta name="theme-color" content="#f7f6f2" />
  <meta name="mobile-web-app-capable" content="yes" />
  <meta name="apple-mobile-web-app-capable" content="yes" />
  <meta name="apple-mobile-web-app-status-bar-style" content="default" />
  <meta name="apple-mobile-web-app-title" content="{title}" />
"""


def deferred_script(prefix: str, name: str) -> str:
    return f'  <script src="{prefix}{name}" defer></script>\n'


# Kept for callers that still want the Chinese-root script tags.
INSTALL_SCRIPT_TAG = deferred_script("", "install.js")
SHARE_SCRIPT_TAG = deferred_script("", "share.js")
VERSION_SCRIPT_TAG = deferred_script("", "version.js")

# GA4. One tag per page, immediately after <head>.
GOOGLE_TAG = """\
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-KK8K4PQW21"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());

  gtag('config', 'G-KK8K4PQW21');
</script>
"""

# Old bookmarks use ?lang= and ?version= on the Chinese URL. GitHub Pages cannot
# redirect on a query string, so this runs before paint and sends the browser
# to the other language's static page (data-href-zh / data-href-en).
LANG_BOOT_SCRIPT = """\
  <script>
  (function () {
    try {
      var root = document.documentElement;
      var page = root.getAttribute("data-page-lang") === "en" ? "en" : "zh";
      var params = new URLSearchParams(window.location.search);
      var qLang = params.get("lang");
      var version = params.get("version");
      var english = { NIV: 1, KJV: 1 };
      var chinese = { CUV: 1, RCUV: 1, CNVT: 1, CSBT: 1, WCB: 1 };
      var target = null;
      if (qLang === "en" || qLang === "zh") target = qLang;
      else if (version && english[version]) target = "en";
      else if (version && chinese[version]) target = "zh";
      else {
        try {
          var saved = window.localStorage.getItem("dailyTexts.lang");
          if (saved === "en" || saved === "zh") target = saved;
        } catch (err) {}
      }
      var explicit = qLang === "en" || qLang === "zh" ||
        !!(version && (english[version] || chinese[version]));
      if (explicit && target) {
        try { window.localStorage.setItem("dailyTexts.lang", target); } catch (err) {}
      }
      if (!target || target === page) return;
      var href = root.getAttribute(target === "en" ? "data-href-en" : "data-href-zh");
      if (!href) return;
      var url = new URL(href, window.location.href);
      if (version && ((target === "en" && english[version]) || (target === "zh" && chinese[version]))) {
        url.searchParams.set("version", version);
      }
      window.__dailyTextsRedirect = true;
      window.location.replace(url.toString());
    } catch (err) {}
  })();
  </script>
"""


def pick(lang: str, zh: str, en: str) -> str:
    """UI copy for one language. Pages are static; nothing is swapped later."""
    return en if lang == "en" else zh


def ui(lang: str, zh: str, en: str) -> str:
    return escape(pick(lang, zh, en))


def bilingual(zh: str, en: str) -> str:
    """Chinese text with an English alternate. Kept for non-site callers."""
    return (
        f'<span class="i18n-zh">{escape(zh)}</span>'
        f'<span class="i18n-en">{escape(en)}</span>'
    )


def html_root_tag(lang: str, href_zh: str, href_en: str) -> str:
    if lang == "en":
        return (
            '<html lang="en" data-page-lang="en" '
            f'data-href-zh="{escape(href_zh, quote=True)}" '
            f'data-href-en="{escape(href_en, quote=True)}">'
        )
    return (
        '<html lang="zh-Hant" data-page-lang="zh" '
        f'data-href-zh="{escape(href_zh, quote=True)}" '
        f'data-href-en="{escape(href_en, quote=True)}">'
    )


def seo_links(*, canonical: str, alternate_zh: str, alternate_en: str) -> str:
    """Self-referencing canonical plus hreflang. x-default follows Chinese."""
    zh = escape(alternate_zh, quote=True)
    en = escape(alternate_en, quote=True)
    canon = escape(canonical, quote=True)
    return (
        f'  <link rel="canonical" href="{canon}" />\n'
        f'  <link rel="alternate" hreflang="zh-Hant" href="{zh}" />\n'
        f'  <link rel="alternate" hreflang="en" href="{en}" />\n'
        f'  <link rel="alternate" hreflang="x-default" href="{zh}" />\n'
    )


def lang_toggle_html(lang: str, href_zh: str, href_en: str) -> str:
    zh_current = ' aria-current="page"' if lang != "en" else ""
    en_current = ' aria-current="page"' if lang == "en" else ""
    return (
        '    <div class="lang-toggle" role="group" aria-label="Language">\n'
        f'      <a class="lang-toggle__btn" href="{escape(href_zh, quote=True)}" '
        f'hreflang="zh-Hant" lang="zh-Hant" data-set-lang="zh"{zh_current}>中文</a>\n'
        f'      <a class="lang-toggle__btn" href="{escape(href_en, quote=True)}" '
        f'hreflang="en" lang="en" data-set-lang="en"{en_current}>EN</a>\n'
        "    </div>\n"
    )


# Forward/share: a stroke arrow that curves out to the right (轉寄), not the
# iOS tray-upload glyph. Stroke matches the tab bar.
_SHARE_ICON = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<path d="M4 19c0-7 5-11 11-11h5"/>'
    '<polyline points="16 4 21 8 16 12"/>'
    "</svg>"
)

def share_bar_html(lang: str) -> str:
    """Day-level share control under the reading, not part of the prayer."""
    label = ui(lang, "分享今日經文", "Share today’s reading")
    return (
        '    <div class="share-bar">\n'
        '      <button type="button" class="share-btn" id="share-day">\n'
        f'        <span class="share-btn__icon">{_SHARE_ICON}</span>\n'
        f'        <span class="share-btn__label">{label}</span>\n'
        "      </button>\n"
        '      <span id="share-status" class="share-status" hidden></span>\n'
        "    </div>\n"
    )

# Bottom tab bar shared by every site page. Fixed on phones (icon over label),
# a plain centered row on desktop. Three equal items: today, home, about.
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
def _tab(href: str, lang: str, zh: str, en: str, icon: str) -> str:
    return (
        f'    <a class="tab" href="{href}">'
        f'<span class="tab__icon" aria-hidden="true">{icon}</span>'
        f'<span class="tab__label">{ui(lang, zh, en)}</span></a>\n'
    )


def tabbar_html(lang: str) -> str:
    """Bottom tab bar. Relative hrefs stay inside the current language directory."""
    label = ui(lang, "主要導覽", "Main")
    return (
        f'  <nav class="tabbar" aria-label="{label}">\n'
        + _tab("today.html", lang, "今日", "Today", _ICON_TODAY)
        + _tab("index.html", lang, "首頁", "Home", _ICON_HOME)
        + _tab("about.html", lang, "關於", "About", _ICON_ABOUT)
        + "  </nav>\n"
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


def day_meta_description(content: LocalizedDailyText, *, lang: str = "zh") -> str:
    """Search snippet for one day: the date plus that day's two references."""
    day = content.date
    if lang == "en":
        ot = content.ot.reference.strip() or content.ot.reference_zh.strip()
        nt = content.nt.reference.strip() or content.nt.reference_zh.strip()
        month = _MONTHS_EN[day.month - 1]
        return f"{month} {day.day} daily reading. Old Testament {ot}, New Testament {nt}."
    ot = content.ot.reference_zh.strip() or content.ot.reference.strip()
    nt = content.nt.reference_zh.strip() or content.nt.reference.strip()
    return f"{day.month} 月 {day.day} 日每日靈修經文。舊約{ot}，新約{nt}。"


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
        lang: str = "zh",
        asset_prefix: str = "",
        href_zh: str | None = None,
        href_en: str | None = None,
        canonical_href: str | None = None,
        alternate_zh: str | None = None,
        alternate_en: str | None = None,
    ) -> FormattedOutput:
        if lang not in ("zh", "en"):
            lang = "zh"
        title_zh = date_title_zh(content)
        title_en = date_title_en(content)
        description = escape(day_meta_description(content, lang=lang), quote=True)
        entries = lectionary_entries(content)
        site_mode = stylesheet_href is not None
        page_lang = lang if site_mode else "zh"
        if href_zh is None:
            href_zh = "../index.html" if page_lang == "en" else "index.html"
        if href_en is None:
            href_en = "index.html" if page_lang == "en" else "en/index.html"

        lectionary_block = ""
        if entries:
            refs = "\n".join(
                _reading_row(zh, en, with_link=site_mode, lang=page_lang) for zh, en in entries
            )
            heading = _heading("經文選讀", "Readings", lang=page_lang, site_mode=site_mode)
            lectionary_block = f"{heading}{refs}\n"

        source_block = ""
        if include_source_link:
            source_heading = _heading("原文連結", "Source", lang=page_lang, site_mode=site_mode)
            source_block = (
                f"{source_heading}"
                f'    <p class="source"><a href="{escape(content.source_url, quote=True)}" '
                'rel="noopener noreferrer">'
                "Moravian Daily Texts</a></p>\n"
            )

        if stylesheet_href:
            style_href = f"{asset_prefix}{stylesheet_href}"
            style_block = (
                f'  <link rel="stylesheet" href="{escape(style_href, quote=True)}" />\n'
                f"{deferred_script(asset_prefix, 'version.js')}"
            )
            boot = LANG_BOOT_SCRIPT
            if page_lang == "en":
                title_tag = f"<title>{escape(title_en)} · Moravian Daily Texts</title>"
                heading_html = escape(title_en)
            else:
                title_tag = f"<title>{escape(title_zh)} · 摩拉維亞每日箴言</title>"
                heading_html = escape(title_zh)
            skip = ui(page_lang, "跳至內容", "Skip to content")
            root = html_root_tag(page_lang, href_zh, href_en)
            seo = ""
            if canonical_href and alternate_zh and alternate_en:
                seo = seo_links(
                    canonical=canonical_href,
                    alternate_zh=alternate_zh,
                    alternate_en=alternate_en,
                )
        else:
            css = load_devotional_css()
            style_block = f"  <style>\n{css}\n  </style>\n"
            boot = ""
            seo = ""
            title_tag = f"<title>{escape(title_zh)} · 摩拉維亞每日箴言</title>"
            heading_html = escape(title_zh)
            skip = "跳至內容"
            root = '<html lang="zh-Hant">'

        version_picker = (
            _version_picker(page_lang, href_zh, href_en) if site_mode else ""
        )
        if site_mode or prev_href or next_href:
            heading_block = _date_nav(
                heading_html,
                prev_href=prev_href,
                next_href=next_href,
                lang=page_lang if site_mode else "zh",
            )
        else:
            heading_block = f"    <h1>{heading_html}</h1>\n"
        footer = _site_footer(site_mode=site_mode, lang=page_lang if site_mode else "zh")
        data_block = _day_data_script(content) if site_mode else ""
        pwa_head = pwa_head_tags(asset_prefix, lang=page_lang) if site_mode else ""
        google_tag = GOOGLE_TAG if site_mode else ""
        install_script = deferred_script(asset_prefix, "install.js") if site_mode else ""
        share_script = deferred_script(asset_prefix, "share.js") if site_mode else ""
        share_bar = share_bar_html(page_lang) if site_mode else ""

        week_block = ""
        if content.week_watchword is not None:
            week_block = (
                f"{_heading('本週守望經文', 'Watchword for the Week', lang=page_lang, site_mode=site_mode)}"
                f"    {_verse_line(content.week_watchword, 'week', lang=page_lang)}\n"
                f"    {_ref_line(content.week_watchword, lang=page_lang, site_mode=site_mode)}\n"
            )

        # English has no separate prayer text. The Chinese page shows the prayer;
        # the English page leaves it out, matching the previous client-side hide.
        show_prayer = page_lang != "en"
        prayer_block = ""
        if show_prayer:
            citation = prayer_citation(content)
            media_url = prayer_media_url(content)
            listen_link = ""
            if media_url:
                listen_link = (
                    f' <a class="prayer-listen" href="{escape(media_url, quote=True)}"'
                    ' target="_blank" rel="noopener noreferrer"'
                    ' aria-label="在 YouTube 聆聽這首詩歌">&#9834; 聆聽詩歌</a>'
                )
            citation_block = (
                f'    <p class="prayer-source">— {escape(citation)}{listen_link}</p>\n'
                if citation
                else ""
            )
            prayer_inner = (
                f"{_heading('今日禱文', 'Prayer', lang=page_lang, site_mode=site_mode)}"
                f'    <p class="prayer">{escape(content.prayer_zh)}</p>\n'
                f"{citation_block}"
            )
            if site_mode:
                prayer_block = f'    <div class="prayer-block">\n{prayer_inner}    </div>\n'
            else:
                prayer_block = prayer_inner

        texts = (
            f"{_heading('舊約', 'Old Testament', lang=page_lang, site_mode=site_mode)}"
            f"    {_verse_line(content.ot, 'ot', lang=page_lang)}\n"
            f"    {_ref_line(content.ot, lang=page_lang, site_mode=site_mode)}\n"
            f"{_heading('新約', 'New Testament', lang=page_lang, site_mode=site_mode)}"
            f"    {_verse_line(content.nt, 'nt', lang=page_lang)}\n"
            f"    {_ref_line(content.nt, lang=page_lang, site_mode=site_mode)}\n"
            f"{prayer_block}"
        )
        if site_mode:
            texts = f'    <div class="day-share">\n{texts}{share_bar}    </div>\n'
        else:
            texts = f"{texts}{share_bar}"

        body = f"""<!DOCTYPE html>
{root}
<head>
{google_tag}  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="color-scheme" content="light dark" />
  <meta name="description" content="{description}" />
  {title_tag}
{boot}{seo}{pwa_head}{_FONT_LINKS}{style_block}{install_script}{share_script}</head>
<body>
  <a class="skip-link" href="#main">{skip}</a>
  <div class="site-shell">
{version_picker}  <main id="main">
    <article>
{heading_block}{week_block}{texts}{lectionary_block}{source_block}    </article>
  </main>
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


def baked_verse(watchword: LocalizedWatchword, lang: str) -> str:
    """Verse text written into the HTML so crawlers do not depend on JavaScript."""
    translations = watchword.translations or {}
    if lang == "en":
        text = (translations.get(DEFAULT_ENGLISH_VERSION) or "").strip()
        return text or watchword.text_en
    text = (translations.get(DEFAULT_VERSION) or "").strip()
    return text or watchword.text_zh


def _verse_line(watchword: LocalizedWatchword, role: str, *, lang: str = "zh") -> str:
    return (
        f'<p class="verse" data-verse="{escape(role, quote=True)}">'
        f"{escape(baked_verse(watchword, lang))}</p>"
    )


def _heading(zh: str, en: str, *, site_mode: bool, lang: str = "zh") -> str:
    inner = ui(lang, zh, en) if site_mode else escape(zh)
    return f"    <h2>{inner}</h2>\n"


def _version_picker(lang: str, href_zh: str, href_en: str) -> str:
    if lang == "en":
        versions = ENGLISH_VERSIONS
        default = DEFAULT_ENGLISH_VERSION
        label = "Version"
    else:
        versions = SITE_VERSIONS
        default = DEFAULT_VERSION
        label = "閱讀譯本"
    options = "\n".join(
        f'      <option value="{code}"'
        f'{" selected" if code == default else ""}>{option_label}</option>'
        for code, option_label in versions
    )
    toggle = lang_toggle_html(lang, href_zh, href_en)
    return f"""  <div class="version-picker">
{toggle}    <label class="version-picker__label" for="bible-version">{escape(label)}</label>
    <select id="bible-version" class="version-picker__select" autocomplete="off">
{options}
    </select>
  </div>
"""


def _ref_line(watchword: LocalizedWatchword, *, lang: str = "zh", site_mode: bool = False) -> str:
    if site_mode and lang == "en":
        ref = watchword.reference.strip() or watchword.reference_zh
    else:
        ref = watchword.reference_zh
    return f'<p class="ref">— {escape(ref)}</p>'


def _reading_row(zh_label: str, english_ref: str, *, with_link: bool, lang: str = "zh") -> str:
    if not with_link:
        return f'    <p class="reading"><span class="reading__ref">{escape(zh_label)}</span></p>'

    cleaned = english_ref.strip().replace("–", "-").replace("—", "-")
    version_code = DEFAULT_ENGLISH_VERSION if lang == "en" else DEFAULT_VERSION
    gw = gateway_version(version_code)
    url = biblegateway_url(cleaned, version=gw)
    ref = escape(cleaned if lang == "en" else zh_label)
    if lang == "en":
        link_label = "[Read]"
        title = "Read on Bible Gateway"
        aria = f"Read {cleaned}"
    else:
        link_label = "[閱讀]"
        title = "在 Bible Gateway 閱讀"
        aria = f"閱讀 {zh_label}"
    return (
        f'    <p class="reading">'
        f'<span class="reading__ref">{ref}</span>'
        f'<a class="reading__open" href="{escape(url, quote=True)}" '
        f'data-ref="{escape(cleaned, quote=True)}" '
        f'data-label-zh="{escape(zh_label, quote=True)}" '
        f'target="_blank" rel="noopener noreferrer" '
        f'title="{escape(title, quote=True)}" '
        f'aria-label="{escape(aria, quote=True)}">{escape(link_label)}</a></p>'
    )


def _nav_label(zh: str, en: str, *, lang: str, prefix: str = "", suffix: str = "") -> str:
    return f"{prefix}{ui(lang, zh, en)}{suffix}"


def day_nav_control(
    href: str | None,
    css: str,
    label: str,
) -> str:
    """One previous/next control. A missing day stays in the row so the date stays centered."""
    if href:
        return f'    <a class="{css}" href="{escape(href, quote=True)}">{label}</a>\n'
    return f'    <span class="{css}" aria-disabled="true">{label}</span>\n'


def _date_nav(
    heading_html: str,
    *,
    prev_href: str | None,
    next_href: str | None,
    lang: str,
) -> str:
    prev = day_nav_control(
        prev_href,
        "day-nav__prev",
        _nav_label("前一日", "Previous", lang=lang, prefix="← "),
    )
    nxt = day_nav_control(
        next_href,
        "day-nav__next",
        _nav_label("後一日", "Next", lang=lang, suffix=" →"),
    )
    label = ui(lang, "日期導覽", "Date")
    return (
        f'    <nav class="day-nav day-nav--date" aria-label="{label}">\n'
        f"{prev}"
        f"    <h1>{heading_html}</h1>\n"
        f"{nxt}"
        "    </nav>\n"
    )


def _site_footer(*, site_mode: bool, lang: str = "zh") -> str:
    if not site_mode:
        return (
            '  <footer class="site-foot">\n'
            '    <p class="foot-credit">摩拉維亞每日箴言 · Daily Texts</p>\n'
            f"    {LOSUNGEN_ATTRIBUTION_HTML}\n"
            "  </footer>\n"
        )
    notice = escape(VERSION_NOTICES["NIV"] if lang == "en" else VERSION_NOTICES["WCB"])
    credit = ui(lang, "摩拉維亞每日箴言 · 中文整理", "Moravian Daily Texts")
    return f"""  <footer class="site-foot">
    <p class="foot-credit">{credit}</p>
    {LOSUNGEN_ATTRIBUTION_HTML}
    <p id="version-notice" class="version-notice" hidden>{notice}</p>
  </footer>
{tabbar_html(lang)}"""
