from __future__ import annotations

import pytest

from daily_texts.domain.exceptions import BibleLookupError
from daily_texts.infrastructure.bible.fhl_rcuv import parse_reference


def test_parse_simple_reference() -> None:
    parsed = parse_reference("Jeremiah 9:7")
    assert parsed.book == "Jeremiah"
    assert parsed.chineses == "耶"
    assert parsed.chapter == 9
    assert parsed.verse == "7"


def test_parse_range_and_en_dash() -> None:
    parsed = parse_reference("Luke 12:35–48")
    assert parsed.chineses == "路"
    assert parsed.chapter == 12
    assert parsed.verse == "35-48"


def test_parse_numbered_book() -> None:
    parsed = parse_reference("1 John 3:16")
    assert parsed.chineses == "約一"
    assert parsed.chapter == 3
    assert parsed.verse == "16"


def test_parse_unknown_book() -> None:
    with pytest.raises(BibleLookupError, match="Unknown"):
        parse_reference("NotABook 1:1")
