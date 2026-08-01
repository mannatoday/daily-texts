from __future__ import annotations

from typing import Protocol

from daily_texts.application.dto import FormattedOutput, PublishResult
from daily_texts.domain.models import LocalizedDailyText


class Publisher(Protocol):
    @property
    def channel(self) -> str: ...

    async def publish(
        self,
        outputs: list[FormattedOutput],
        content: LocalizedDailyText,
    ) -> PublishResult:
        """Publish formatted outputs to a channel."""
