from __future__ import annotations

from typing import Protocol


class TextTranslator(Protocol):
    async def translate(
        self,
        text: str,
        *,
        source_lang: str = "en",
        target_lang: str = "zh-TW",
    ) -> str:
        """Translate non-scripture text (e.g. daily prayer)."""
