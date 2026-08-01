from __future__ import annotations

from daily_texts.application.dto import FormattedOutput, PublishResult
from daily_texts.domain.models import LocalizedDailyText


class TelegramPublisher:
    """Stub for future Telegram Bot publishing."""

    channel = "telegram"

    async def publish(
        self,
        outputs: list[FormattedOutput],
        content: LocalizedDailyText,
    ) -> PublishResult:
        raise NotImplementedError("TelegramPublisher is reserved for Milestone 3")
