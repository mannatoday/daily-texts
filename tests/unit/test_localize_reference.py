from __future__ import annotations

from daily_texts.domain.references import localize_reference


def test_localize_reference_simple() -> None:
    assert localize_reference("Jeremiah 9:7") == "耶利米書 9:7"
    assert localize_reference("Luke 22:40") == "路加福音 22:40"


def test_localize_reference_range() -> None:
    assert localize_reference("Luke 12:35–48") == "路加福音 12:35–48"


def test_localize_reference_unknown_passthrough() -> None:
    assert localize_reference("NotABook 1:1") == "NotABook 1:1"
