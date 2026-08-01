from __future__ import annotations

from typing import Protocol

from daily_texts.application.dto import FormatName, FormattedOutput
from daily_texts.domain.models import LocalizedDailyText


class ContentFormatter(Protocol):
    @property
    def format_name(self) -> FormatName: ...

    def format(
        self,
        content: LocalizedDailyText,
        *,
        include_source_link: bool = True,
    ) -> FormattedOutput:
        """Render localized content to a specific output format."""
