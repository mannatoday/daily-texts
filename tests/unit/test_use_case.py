from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from daily_texts.application.use_cases.fetch_and_localize import FetchAndLocalizeDailyText
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
        return f"ZH:{reference}"


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
    assert result.localized.ot.text_zh == "ZH:Jeremiah 9:7"
    assert result.localized.prayer_zh == "Hear our prayer. Amen."
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
