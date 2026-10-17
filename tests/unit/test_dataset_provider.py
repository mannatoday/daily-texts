from __future__ import annotations

from datetime import date

import pytest

from daily_texts.domain.exceptions import ProviderError
from daily_texts.infrastructure.providers.dataset import DatasetProvider


@pytest.mark.asyncio
async def test_dataset_provider_resolves_known_chinese_excerpt() -> None:
    raw = await DatasetProvider().fetch(date(2026, 10, 14))
    assert raw.ot.reference == "Psalm 97:11"
    assert raw.nt.reference == "Luke 14:13-14"
    assert raw.ot.text_en == ""
    assert raw.psalm == "Psalm 119:1–8"
    assert raw.readings == ["2 Samuel 3:35–5:16", "John 7:1–13"]
    assert raw.week_watchword is None
    assert raw.metadata["third_text_id"] == "tx-bcp-collect"
    assert raw.metadata["prayer_lang"] == "zh"
    assert raw.metadata["prayer_citation"] == "公禱書：求主眷顧困苦者 (collect)"
    assert raw.prayer_en.startswith("全能的上帝")


@pytest.mark.asyncio
async def test_dataset_provider_keeps_english_excerpt_for_translation() -> None:
    raw = await DatasetProvider().fetch(date(2026, 12, 9))
    assert raw.metadata["third_text_id"] == "dc-murray-abide"
    assert raw.metadata["prayer_lang"] == "en"
    assert raw.metadata["prayer_citation"] == "慕安德烈〈住在基督裡 (Abide in Christ)〉"
    assert raw.prayer_en.startswith("Let me listen and believe")


@pytest.mark.asyncio
async def test_dataset_provider_names_missing_excerpt_without_inventing_one() -> None:
    raw = await DatasetProvider().fetch(date(2026, 11, 15))
    assert raw.metadata["third_text_id"] == "tx-foundation"
    assert raw.metadata["prayer_lang"] == "zh"
    assert raw.prayer_en == "（第三段待補原文：tx-foundation）"
    assert "教會唯一的根基" in raw.metadata["prayer_citation"]


@pytest.mark.asyncio
async def test_dataset_provider_uses_lectionary_on_a_sunday() -> None:
    raw = await DatasetProvider().fetch(date(2026, 10, 18))
    assert raw.psalm == "Psalm 96:1-9, 10-13"
    assert raw.readings == [
        "Isaiah 45:1-7",
        "1 Thessalonians 1:1-10",
        "Matthew 22:15-22",
    ]


@pytest.mark.asyncio
async def test_dataset_provider_rejects_unknown_date() -> None:
    with pytest.raises(ProviderError, match="2025-01-01"):
        await DatasetProvider().fetch(date(2025, 1, 1))
