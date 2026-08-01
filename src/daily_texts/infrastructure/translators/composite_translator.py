from __future__ import annotations

import logging
from collections.abc import Sequence

from daily_texts.application.ports.translator import TextTranslator
from daily_texts.domain.exceptions import TranslationError

logger = logging.getLogger(__name__)


class CompositeTranslator:
    """Try translators in order; first successful result wins."""

    name = "composite"

    def __init__(self, translators: Sequence[TextTranslator]) -> None:
        if not translators:
            raise ValueError("CompositeTranslator requires at least one translator")
        self._translators = list(translators)

    async def translate(
        self,
        text: str,
        *,
        source_lang: str = "en",
        target_lang: str = "zh-TW",
    ) -> str:
        if not text.strip():
            raise TranslationError("Cannot translate empty text")

        errors: list[str] = []
        for translator in self._translators:
            name = getattr(translator, "name", translator.__class__.__name__)
            available = getattr(translator, "available", None)
            if callable(available) and not available():
                logger.info("Skipping translator %s (not configured)", name)
                continue
            try:
                result = await translator.translate(
                    text,
                    source_lang=source_lang,
                    target_lang=target_lang,
                )
                logger.info("Translation succeeded via %s", name)
                return result
            except TranslationError as exc:
                logger.warning("Translator %s failed: %s", name, exc)
                errors.append(f"{name}: {exc}")

        raise TranslationError(
            "All translators failed: " + ("; ".join(errors) if errors else "none available")
        )
