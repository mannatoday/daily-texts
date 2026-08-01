from __future__ import annotations

from datetime import date
from typing import Protocol

from daily_texts.domain.models import RawDailyText


class DailyTextProvider(Protocol):
    @property
    def source_name(self) -> str: ...

    async def fetch(self, target_date: date | None = None) -> RawDailyText:
        """Fetch daily text. target_date=None means today for the provider."""
