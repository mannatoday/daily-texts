from __future__ import annotations

from daily_texts.application.dto import FormattedOutput, PublishResult
from daily_texts.domain.models import LocalizedDailyText


class EmailPublisher:
    """Stub for future email publishing."""

    channel = "email"

    async def publish(
        self,
        outputs: list[FormattedOutput],
        content: LocalizedDailyText,
    ) -> PublishResult:
        raise NotImplementedError("EmailPublisher is reserved for Milestone 3")
