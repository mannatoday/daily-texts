from __future__ import annotations

import logging

from daily_texts.application.dto import FormattedOutput, PublishResult
from daily_texts.domain.models import LocalizedDailyText

logger = logging.getLogger(__name__)


class NullPublisher:
    """Phase 1 default: log and succeed without sending anywhere."""

    channel = "null"

    async def publish(
        self,
        outputs: list[FormattedOutput],
        content: LocalizedDailyText,
    ) -> PublishResult:
        formats = ", ".join(o.format for o in outputs) or "(none)"
        message = f"Skipped publish for {content.date}: formats={formats}"
        logger.info(message)
        return PublishResult(channel=self.channel, success=True, message=message)
