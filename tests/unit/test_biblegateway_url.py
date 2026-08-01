from __future__ import annotations

from daily_texts.infrastructure.formatters._common import biblegateway_cuv_url


def test_biblegateway_cuv_url_simple() -> None:
    url = biblegateway_cuv_url("Psalm 91:1–8")
    assert url.startswith("https://www.biblegateway.com/passage/?search=")
    assert "version=CUV" in url
    assert "Psalm" in url
    assert "91" in url


def test_biblegateway_cuv_url_cross_chapter() -> None:
    url = biblegateway_cuv_url("Joshua 8:30–9:27")
    assert "Joshua" in url
    assert "8%3A30-9%3A27" in url or "8:30-9:27" in url
