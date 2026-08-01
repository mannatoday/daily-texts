from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from daily_texts.domain.exceptions import ProviderError
from daily_texts.infrastructure.providers.moravian_html_sidebar import (
    parse_moravian_sidebar_html,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "moravian_sidebar.html"


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
