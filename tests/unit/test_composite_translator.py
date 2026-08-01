from __future__ import annotations

import pytest

from daily_texts.domain.exceptions import TranslationError
from daily_texts.infrastructure.translators.composite_translator import CompositeTranslator
from daily_texts.infrastructure.translators.fallback_translator import FallbackTranslator


class FakeTranslator:
    def __init__(self, name: str, *, result: str | None = None, fail: bool = False, available: bool = True) -> None:
        self.name = name
        self._result = result
        self._fail = fail
        self._available = available
        self.calls = 0

    def available(self) -> bool:
        return self._available

    async def translate(
        self,
        text: str,
        *,
        source_lang: str = "en",
        target_lang: str = "zh-TW",
    ) -> str:
        self.calls += 1
        if self._fail:
            raise TranslationError(f"{self.name} failed")
        return self._result or text


@pytest.mark.asyncio
async def test_composite_uses_first_success() -> None:
    first = FakeTranslator("openai", fail=True)
    second = FakeTranslator("anthropic", result="中文禱告")
    third = FakeTranslator("fallback", result="EN")
    composite = CompositeTranslator([first, second, third])

    result = await composite.translate("Hear our prayer. Amen.")
    assert result == "中文禱告"
    assert first.calls == 1
    assert second.calls == 1
    assert third.calls == 0


@pytest.mark.asyncio
async def test_composite_skips_unavailable() -> None:
    skipped = FakeTranslator("openai", available=False, result="should-not-use")
    fallback = FallbackTranslator()
    composite = CompositeTranslator([skipped, fallback])

    result = await composite.translate("Amen.")
    assert result == "Amen."
    assert skipped.calls == 0


@pytest.mark.asyncio
async def test_composite_all_fail_raises() -> None:
    composite = CompositeTranslator(
        [
            FakeTranslator("openai", fail=True),
            FakeTranslator("anthropic", fail=True),
        ]
    )
    with pytest.raises(TranslationError, match="All translators failed"):
        await composite.translate("Amen.")
