class DailyTextsError(Exception):
    """Base exception for the daily-texts application."""


class ProviderError(DailyTextsError):
    """Failed to fetch or parse daily text from a provider."""


class BibleLookupError(DailyTextsError):
    """Failed to look up scripture from the Bible service."""


class TranslationError(DailyTextsError):
    """Failed to translate non-scripture text."""
