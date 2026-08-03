from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

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
        self.last_report: dict[str, Any] = {}

    def _chain_status(self) -> list[str]:
        statuses: list[str] = []
        for translator in self._translators:
            name = getattr(translator, "name", translator.__class__.__name__)
            available = getattr(translator, "available", None)
            if callable(available) and not available():
                statuses.append(f"{name}=skipped")
            else:
                statuses.append(f"{name}=ready")
        return statuses

    async def translate(
        self,
        text: str,
        *,
        source_lang: str = "en",
        target_lang: str = "zh-TW",
    ) -> str:
        if not text.strip():
            raise TranslationError("Cannot translate empty text")

        chain_status = self._chain_status()
        logger.info(
            "Prayer translation chain (%s→%s, %d chars): %s",
            source_lang,
            target_lang,
            len(text),
            ", ".join(chain_status),
        )

        skipped: list[str] = []
        failed: list[dict[str, str]] = []
        errors: list[str] = []

        for translator in self._translators:
            name = getattr(translator, "name", translator.__class__.__name__)
            available = getattr(translator, "available", None)
            if callable(available) and not available():
                logger.info("Skipping translator %s (not configured)", name)
                skipped.append(name)
                continue
            try:
                logger.info("Trying translator %s", name)
                result = await translator.translate(
                    text,
                    source_lang=source_lang,
                    target_lang=target_lang,
                )
                kept_english = result.strip() == text.strip()
                status = "fallback_english" if name == "fallback" or kept_english else "ok"
                self.last_report = {
                    "provider": name,
                    "status": status,
                    "chain": [
                        getattr(t, "name", t.__class__.__name__) for t in self._translators
                    ],
                    "skipped": skipped,
                    "failed": failed,
                    "source_chars": len(text),
                    "result_chars": len(result),
                    "kept_english": kept_english,
                }
                logger.info(
                    "Translation succeeded via %s (status=%s, %d→%d chars, kept_english=%s)",
                    name,
                    status,
                    len(text),
                    len(result),
                    kept_english,
                )
                return result
            except TranslationError as exc:
                logger.warning("Translator %s failed: %s", name, exc)
                failed.append({"name": name, "error": str(exc)})
                errors.append(f"{name}: {exc}")

        self.last_report = {
            "provider": None,
            "status": "all_failed",
            "chain": [getattr(t, "name", t.__class__.__name__) for t in self._translators],
            "skipped": skipped,
            "failed": failed,
            "source_chars": len(text),
            "result_chars": 0,
            "kept_english": True,
        }
        raise TranslationError(
            "All translators failed: " + ("; ".join(errors) if errors else "none available")
        )
