from __future__ import annotations

from daily_texts.domain.exceptions import TranslationError


class NoopTranslator:
    """Pass-through translator for tests and offline runs."""

    async def translate(
        self,
        text: str,
        *,
        source_lang: str = "en",
        target_lang: str = "zh-TW",
    ) -> str:
        if not text.strip():
            raise TranslationError("Cannot translate empty text")
        return text
