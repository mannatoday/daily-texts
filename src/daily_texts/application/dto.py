from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from daily_texts.domain.models import LocalizedDailyText, RawDailyText

FormatName = Literal["markdown", "html", "text", "json"]


class FormattedOutput(BaseModel):
    format: FormatName
    content: str
    filename: str


class PublishResult(BaseModel):
    channel: str
    success: bool
    message: str = ""


class PipelineResult(BaseModel):
    raw: RawDailyText
    localized: LocalizedDailyText
    outputs: list[FormattedOutput] = Field(default_factory=list)
    publish_results: list[PublishResult] = Field(default_factory=list)
    skipped: bool = False
    skip_reason: str = ""
