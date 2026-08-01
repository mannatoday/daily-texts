from __future__ import annotations

from datetime import date

from daily_texts.domain.models import LocalizedDailyText, LocalizedWatchword
from daily_texts.infrastructure.formatters.html import HtmlFormatter
from daily_texts.infrastructure.formatters.markdown import MarkdownFormatter
from daily_texts.infrastructure.formatters.plain_text import PlainTextFormatter


def _sample() -> LocalizedDailyText:
    return LocalizedDailyText(
        date=date(2026, 7, 31),
        date_display="Friday, July 31, 2026",
        psalm="Psalm 90",
        readings=["Joshua 8:1–29", "Luke 12:35–48"],
        ot=LocalizedWatchword(
            reference="Jeremiah 9:7",
            text_en="I will now refine and test them.",
            text_zh="看哪，我要熬煉他們，試驗他們。",
        ),
        nt=LocalizedWatchword(
            reference="Luke 22:40",
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
    assert "## 舊約" in out.content
    assert "## 新約" in out.content
    assert "## 今日禱告" in out.content
    assert "Jeremiah 9:7" in out.content
    assert "moravian.org" in out.content


def test_html_formatter() -> None:
    out = HtmlFormatter().format(_sample(), include_source_link=False)
    assert out.filename == "daily-text.html"
    assert "<h2>舊約</h2>" in out.content
    assert "原文連結" not in out.content


def test_plain_text_formatter() -> None:
    out = PlainTextFormatter().format(_sample(), include_source_link=True)
    assert out.filename == "daily-text.txt"
    assert "【舊約】" in out.content
    assert "【今日禱告】" in out.content
