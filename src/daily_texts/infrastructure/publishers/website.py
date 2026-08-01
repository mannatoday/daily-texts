from __future__ import annotations

from daily_texts.application.dto import FormattedOutput, PublishResult
from daily_texts.domain.models import LocalizedDailyText


class WebsitePublisher:
    """Stub for future website / CMS publishing."""

    channel = "website"

    async def publish(
        self,
        outputs: list[FormattedOutput],
        content: LocalizedDailyText,
    ) -> PublishResult:
        raise NotImplementedError("WebsitePublisher is reserved for Milestone 3")
