from __future__ import annotations

from datetime import date

from daily_texts.domain.exceptions import ProviderError
from daily_texts.domain.models import RawDailyText


class EmailInboxProvider:
    """Stub for future email-based provider."""

    source_name = "email"

    async def fetch(self, target_date: date | None = None) -> RawDailyText:
        raise NotImplementedError(
            "EmailInboxProvider is not implemented yet. "
            "Use PROVIDER=moravian_html for Phase 1."
        )
