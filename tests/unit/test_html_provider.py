from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from daily_texts.domain.exceptions import ProviderError
from daily_texts.infrastructure.providers.moravian_html_sidebar import (
    parse_moravian_sidebar_html,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
FIXTURE = FIXTURES / "moravian_sidebar.html"
SUNDAY_FIXTURE = FIXTURES / "moravian_sidebar_sunday.html"
SPLIT_DASH_FIXTURE = FIXTURES / "moravian_sidebar_split_dash.html"



def test_parse_moravian_sidebar_html() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    result = parse_moravian_sidebar_html(
        html,
        source_url="https://www.moravian.org/the-daily-texts/",
    )

    assert result.date == date(2026, 7, 31)
    assert result.date_display == "Friday, July 31, 2026"
    assert result.psalm == "Psalm 90:1–17"
    assert result.readings == ["Joshua 8:1–29", "Luke 12:35–48"]
    assert result.ot.reference == "Jeremiah 9:7"
    assert result.ot.text_en == "I will now refine and test them."
    assert result.ot.bible_url is not None
    assert "biblegateway.com" in result.ot.bible_url
    assert result.nt.reference == "Luke 22:40"
    assert "time of trial" in result.nt.text_en
    assert result.prayer_en.endswith("Amen.")
    assert result.metadata.get("day_label") == "Friday, July 31"


def test_parse_moravian_sunday_layout() -> None:
    html = SUNDAY_FIXTURE.read_text(encoding="utf-8")
    result = parse_moravian_sidebar_html(
        html,
        source_url="https://www.moravian.org/the-daily-texts/",
    )

    assert result.date == date(2026, 8, 2)
    assert result.metadata.get("church_year_label") == "Tenth Sunday after Pentecost"
    assert "Watchword for the week" in (result.metadata.get("watchword_for_week") or "")
    assert result.psalm == "Psalm 145:8-9,14-21"
    assert "Isaiah 55:1-5" in result.readings
    assert "Romans 9:1-5" in result.readings
    assert "Matthew 14:13-21" in result.readings
    assert result.ot.reference == "Deuteronomy 18:14"
    assert "soothsayers" in result.ot.text_en
    assert result.nt.reference == "Galatians 4:9"
    assert result.prayer_en.endswith("Amen.")
    assert result.metadata.get("day_label") == "Sunday, August 2"
    assert result.week_watchword is not None
    assert result.week_watchword.reference == "Psalm 145:9"
    assert result.week_watchword.text_en == (
        "The LORD is good to all, and his compassion is over all that he has made."
    )


def test_parse_lone_dash_splits_psalm_and_cross_book_reading() -> None:
    """Moravian sometimes puts '—' on its own line before mashed Psalm + OT."""
    html = SPLIT_DASH_FIXTURE.read_text(encoding="utf-8")
    result = parse_moravian_sidebar_html(
        html,
        source_url="https://www.moravian.org/the-daily-texts/",
    )

    assert result.date == date(2026, 8, 18)
    assert result.psalm == "Psalm 100"
    assert result.readings == ["Joshua 24:14–Judges 1:16", "Luke 18:1–17"]
    assert result.ot.reference == "Isaiah 50:5"
    assert result.nt.reference == "Luke 10:39"


def test_weekday_layout_has_no_week_watchword() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    result = parse_moravian_sidebar_html(
        html,
        source_url="https://www.moravian.org/the-daily-texts/",
    )
    assert result.week_watchword is None


def test_parse_rejects_mismatched_target_date() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    with pytest.raises(ProviderError, match="does not match"):
        parse_moravian_sidebar_html(
            html,
            source_url="https://www.moravian.org/the-daily-texts/",
            target_date=date(2026, 1, 1),
        )


def test_parse_missing_widget() -> None:
    with pytest.raises(ProviderError, match="not found"):
        parse_moravian_sidebar_html("<html><body></body></html>", source_url="http://x")
