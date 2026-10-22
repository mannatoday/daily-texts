from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from daily_texts.application.use_cases.fetch_and_localize import FetchAndLocalizeDailyText
from daily_texts.domain.exceptions import BibleLookupError, TranslationError
from daily_texts.domain.models import RawDailyText, Watchword
from daily_texts.infrastructure.formatters.markdown import MarkdownFormatter
from daily_texts.infrastructure.publishers.null_publisher import NullPublisher
from daily_texts.infrastructure.translators.noop_translator import NoopTranslator


class FakeProvider:
    source_name = "fake"

    def __init__(self, raw: RawDailyText) -> None:
        self._raw = raw

    async def fetch(self, target_date: date | None = None) -> RawDailyText:
        return self._raw


class FakeBible:
    async def lookup(self, reference: str, *, version: str = "rcuv") -> str:
        return f"ZH:{version}:{reference}"


@pytest.mark.asyncio
async def test_use_case_writes_outputs(tmp_path: Path) -> None:
    raw = RawDailyText(
        date=date(2026, 7, 31),
        date_display="Friday, July 31, 2026",
        ot=Watchword(reference="Jeremiah 9:7", text_en="refine"),
        nt=Watchword(reference="Luke 22:40", text_en="pray"),
        prayer_en="Hear our prayer. Amen.",
        source_url="https://example.com",
    )
    uc = FetchAndLocalizeDailyText(
        provider=FakeProvider(raw),
        bible=FakeBible(),
        translator=NoopTranslator(),
        formatters=[MarkdownFormatter()],
        publishers=[NullPublisher()],
        output_dir=tmp_path,
    )
    result = await uc.run()
    assert not result.skipped
    assert result.localized.ot.text_zh == "ZH:rcuv:Jeremiah 9:7"
    assert result.localized.ot.translations["RCUV"] == "ZH:rcuv:Jeremiah 9:7"
    assert result.localized.ot.translations["CUV"] == "ZH:unv:Jeremiah 9:7"
    assert result.localized.ot.translations["CNVT"] == "ZH:ncv:Jeremiah 9:7"
    assert result.localized.ot.translations["CSBT"] == "ZH:csb:Jeremiah 9:7"
    assert result.localized.ot.translations["WCB"] == "ZH:wcb:Jeremiah 9:7"
    assert result.localized.ot.translations["NIV"] == "ZH:niv:Jeremiah 9:7"
    assert result.localized.ot.translations["KJV"] == "ZH:kjv:Jeremiah 9:7"
    assert "ESV" not in result.localized.ot.translations
    assert "CCBT" not in result.localized.ot.translations
    assert result.localized.prayer_zh == "Hear our prayer. Amen."
    assert result.localized.metadata["translation"]["provider"] == "fallback"
    assert result.localized.metadata["translation"]["kept_english"] is True
    assert (tmp_path / "2026-07-31" / "daily-text.md").is_file()


@pytest.mark.asyncio
async def test_use_case_skips_existing(tmp_path: Path) -> None:
    day = date(2026, 7, 31)
    out = tmp_path / "2026-07-31"
    out.mkdir()
    (out / "daily-text.md").write_text("existing", encoding="utf-8")

    raw = RawDailyText(
        date=day,
        date_display="Friday, July 31, 2026",
        ot=Watchword(reference="Jeremiah 9:7", text_en="refine"),
        nt=Watchword(reference="Luke 22:40", text_en="pray"),
        prayer_en="Amen.",
        source_url="https://example.com",
    )
    uc = FetchAndLocalizeDailyText(
        provider=FakeProvider(raw),
        bible=FakeBible(),
        translator=NoopTranslator(),
        formatters=[MarkdownFormatter()],
        publishers=[NullPublisher()],
        output_dir=tmp_path,
    )
    result = await uc.run(day)
    assert result.skipped


class FailingTranslator:
    async def translate(
        self,
        text: str,
        *,
        source_lang: str = "en",
        target_lang: str = "zh-TW",
    ) -> str:
        raise TranslationError("quota exceeded")


@pytest.mark.asyncio
async def test_use_case_falls_back_when_translation_fails(tmp_path: Path) -> None:
    raw = RawDailyText(
        date=date(2026, 7, 31),
        date_display="Friday, July 31, 2026",
        ot=Watchword(reference="Jeremiah 9:7", text_en="refine"),
        nt=Watchword(reference="Luke 22:40", text_en="pray"),
        prayer_en="Hear our prayer. Amen.",
        source_url="https://example.com",
    )
    uc = FetchAndLocalizeDailyText(
        provider=FakeProvider(raw),
        bible=FakeBible(),
        translator=FailingTranslator(),
        formatters=[MarkdownFormatter()],
        publishers=[NullPublisher()],
        output_dir=tmp_path,
    )
    result = await uc.run(force=True)
    assert not result.skipped
    assert result.localized.prayer_zh == "Hear our prayer. Amen."
    assert result.localized.metadata["translation"]["status"] == "failed_kept_english"
    assert "quota exceeded" in result.localized.metadata["translation"]["error"]


@pytest.mark.asyncio
async def test_use_case_keeps_chinese_prayer_without_translator(tmp_path: Path) -> None:
    prayer = "全能的上帝，求祢眷顧貧窮困苦的人。"
    raw = RawDailyText(
        date=date(2026, 10, 14),
        date_display="Wednesday, October 14, 2026",
        ot=Watchword(reference="Psalm 97:11", text_en=""),
        nt=Watchword(reference="Luke 14:13-14", text_en=""),
        prayer_en=prayer,
        source_url="dataset://days_2026_q4/2026-10-14",
        metadata={"provider": "dataset", "prayer_lang": "zh"},
    )
    uc = FetchAndLocalizeDailyText(
        provider=FakeProvider(raw),
        bible=FakeBible(),
        translator=FailingTranslator(),
        formatters=[MarkdownFormatter()],
        publishers=[NullPublisher()],
        output_dir=tmp_path,
    )
    result = await uc.run(force=True)
    assert result.localized.prayer_zh == prayer
    assert result.localized.metadata["translation"]["status"] == "already_zh"
    assert result.localized.metadata["translation"]["kept_english"] is False


class MissingNivBible(FakeBible):
    async def lookup(self, reference: str, *, version: str = "rcuv") -> str:
        if version == "niv":
            raise BibleLookupError("API_BIBLE_API_KEY is not set")
        return await FakeBible.lookup(self, reference, version=version)


@pytest.mark.asyncio
async def test_use_case_retries_later_when_niv_lookup_fails(tmp_path: Path) -> None:
    raw = RawDailyText(
        date=date(2026, 10, 18),
        date_display="Sunday, October 18, 2026",
        ot=Watchword(reference="Haggai 2:9", text_en=""),
        nt=Watchword(reference="Mark 11:17", text_en=""),
        prayer_en="Amen.",
        source_url="dataset://example",
        metadata={"provider": "dataset", "prayer_lang": "zh"},
    )
    uc = FetchAndLocalizeDailyText(
        provider=FakeProvider(raw),
        bible=MissingNivBible(),
        translator=NoopTranslator(),
        formatters=[MarkdownFormatter()],
        publishers=[NullPublisher()],
        output_dir=tmp_path,
    )
    with pytest.raises(BibleLookupError, match="Missing NIV"):
        await uc.run(force=True)
    assert not (tmp_path / "2026-10-18").exists()
