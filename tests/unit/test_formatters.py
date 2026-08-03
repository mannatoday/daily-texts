from __future__ import annotations

from datetime import date

from daily_texts.domain.models import LocalizedDailyText, LocalizedWatchword
from daily_texts.infrastructure.formatters.html import HtmlFormatter
from daily_texts.infrastructure.formatters.markdown import MarkdownFormatter
from daily_texts.infrastructure.formatters.plain_text import PlainTextFormatter


def _sample() -> LocalizedDailyText:
    return LocalizedDailyText(
        date=date(2026, 8, 1),
        date_display="Saturday, August 1, 2026",
        psalm="Psalm 91:1–8",
        readings=["Joshua 8:30–9:27", "Luke 12:49–59"],
        ot=LocalizedWatchword(
            reference="Jeremiah 9:7",
            reference_zh="耶利米書 9:7",
            text_en="I will now refine and test them.",
            text_zh="看哪，我要熬煉他們，試驗他們。",
        ),
        nt=LocalizedWatchword(
            reference="Luke 22:40",
            reference_zh="路加福音 22:40",
            text_en="Pray that you may not come into the time of trial.",
            text_zh="你們要禱告，免得陷入試探。",
        ),
        prayer_en="Great I Am... Amen.",
        prayer_zh="偉大的自有永有者……阿們。",
        source_url="https://www.moravian.org/the-daily-texts/",
    )


def test_markdown_formatter_includes_sections() -> None:
    out = MarkdownFormatter().format(_sample(), include_source_link=True)
    assert out.filename == "daily-text.md"
    assert out.content.startswith("# 2026 年 8 月 1 日（星期六）\n")
    assert "## 舊約" in out.content
    assert "## 新約" in out.content
    assert "## 今日禱告" in out.content
    assert "## 經文選讀" in out.content
    assert "詩篇 91:1–8" in out.content
    assert "約書亞記 8:30–9:27" in out.content
    assert "路加福音 12:49–59" in out.content
    assert "耶利米書 9:7" in out.content
    assert "moravian.org" in out.content
    prayer_idx = out.content.index("## 今日禱告")
    lectionary_idx = out.content.index("## 經文選讀")
    source_idx = out.content.index("## 原文連結")
    assert prayer_idx < lectionary_idx < source_idx


def test_html_formatter() -> None:
    out = HtmlFormatter().format(_sample(), include_source_link=False)
    assert out.filename == "daily-text.html"
    assert "<title>2026 年 8 月 1 日（星期六） · 摩拉維亞每日經文</title>" in out.content
    assert "<h1>2026 年 8 月 1 日（星期六）</h1>" in out.content
    assert "<h2>舊約</h2>" in out.content
    assert "<h2>經文選讀</h2>" in out.content
    assert 'class="verse"' in out.content
    assert "詩篇 91:1–8" in out.content
    assert "約書亞記 8:30–9:27" in out.content
    assert "路加福音 12:49–59" in out.content
    # Standalone HTML (no site stylesheet) keeps plain refs without the picker.
    assert "bible-version" not in out.content
    assert "version.js" not in out.content
    assert "原文連結" not in out.content
    assert "color-scheme" in out.content
    assert "複製經文" not in out.content
    assert "data-copy-scripture" not in out.content
    prayer_idx = out.content.index("<h2>今日禱告</h2>")
    lectionary_idx = out.content.index("<h2>經文選讀</h2>")
    assert prayer_idx < lectionary_idx


def test_html_formatter_site_mode_has_version_aware_links() -> None:
    out = HtmlFormatter().format(
        _sample(),
        include_source_link=False,
        stylesheet_href="styles.css",
    )
    assert 'id="bible-version"' in out.content
    assert "version.js" in out.content
    assert 'data-ref="Psalm 91:1-8"' in out.content or 'data-ref="Psalm 91:1–8"' in out.content
    assert "[閱讀 · 和合本]" in out.content
    assert "version=CUV" in out.content
    assert 'data-ref="Jeremiah 9:7"' in out.content
    assert 'data-ref="Luke 22:40"' in out.content


def test_plain_text_formatter() -> None:
    out = PlainTextFormatter().format(_sample(), include_source_link=True)
    assert out.filename == "daily-text.txt"
    assert out.content.startswith("2026 年 8 月 1 日（星期六）\n")
    assert "【舊約】" in out.content
    assert "【今日禱告】" in out.content
    assert "【經文選讀】" in out.content
    assert "詩篇 91:1–8" in out.content
    assert "約書亞記 8:30–9:27" in out.content
    assert "路加福音 12:49–59" in out.content
    # Lectionary comes after prayer, before source link
    prayer_idx = out.content.index("【今日禱告】")
    lectionary_idx = out.content.index("【經文選讀】")
    source_idx = out.content.index("【原文連結】")
    assert prayer_idx < lectionary_idx < source_idx
