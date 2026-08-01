from __future__ import annotations

from daily_texts.application.dto import FormattedOutput, PublishResult
from daily_texts.domain.models import LocalizedDailyText


class LinePublisher:
    """Stub for future LINE Official Account publishing."""

    channel = "line"

    async def publish(
        self,
        outputs: list[FormattedOutput],
        content: LocalizedDailyText,
    ) -> PublishResult:
        raise NotImplementedError("LinePublisher is reserved for Milestone 3")
