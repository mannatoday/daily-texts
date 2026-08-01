"""Backward-compatible re-export."""

from daily_texts.infrastructure.translators.fallback_translator import (
    FallbackTranslator,
    NoopTranslator,
)

__all__ = ["FallbackTranslator", "NoopTranslator"]
