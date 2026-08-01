from __future__ import annotations

from daily_texts.domain.exceptions import TranslationError


class FallbackTranslator:
    """Last-resort translator: keep the original text (usually English prayer)."""

    name = "fallback"

    def available(self) -> bool:
        return True

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


# Backward-compatible alias used by older tests/config.
NoopTranslator = FallbackTranslator
