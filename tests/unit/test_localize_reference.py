from __future__ import annotations

from daily_texts.domain.references import localize_reference


def test_localize_reference_simple() -> None:
    assert localize_reference("Jeremiah 9:7") == "耶利米書 9:7"
    assert localize_reference("Luke 22:40") == "路加福音 22:40"


def test_localize_reference_range() -> None:
    assert localize_reference("Luke 12:35–48") == "路加福音 12:35–48"
    assert localize_reference("Luke 12:35-48") == "路加福音 12:35–48"


def test_localize_reference_cross_chapter() -> None:
    assert localize_reference("Joshua 8:30–9:27") == "約書亞記 8:30–9:27"


def test_localize_reference_psalm() -> None:
    assert localize_reference("Psalm 90") == "詩篇 90"
    assert localize_reference("Psalm 91:1–8") == "詩篇 91:1–8"


def test_localize_reference_comma_verses() -> None:
    assert localize_reference("Galatians 5:16,17") == "加拉太書 5:16–17"
    assert localize_reference("Galatians 5:16, 17") == "加拉太書 5:16–17"
