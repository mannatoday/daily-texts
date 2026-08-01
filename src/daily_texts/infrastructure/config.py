from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

ProviderName = Literal["moravian_html", "email"]
TranslatorName = Literal["openai", "noop"]
FormatName = Literal["markdown", "html", "text"]


def _split_csv(value: object) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value]
    raise TypeError(f"Expected str or list, got {type(value)!r}")


def _split_csv_ints(value: object) -> list[int]:
    if isinstance(value, str):
        return [int(item.strip()) for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [int(item) for item in value]
    raise TypeError(f"Expected str or list, got {type(value)!r}")


CsvFormats = Annotated[list[FormatName], NoDecode, BeforeValidator(_split_csv)]
CsvStrings = Annotated[list[str], NoDecode, BeforeValidator(_split_csv)]
CsvInts = Annotated[list[int], NoDecode, BeforeValidator(_split_csv_ints)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    provider: ProviderName = "moravian_html"
    moravian_url: str = "https://www.moravian.org/the-daily-texts/"
    moravian_widget_selector: str = "#text-2 .textwidget"

    output_dir: Path = Path("./output")
    formats: CsvFormats = Field(default_factory=lambda: ["markdown", "html", "text"])
    include_source_link: bool = True

    bible_version: str = "rcuv"
    fhl_api_base: str = "https://bible.fhl.net/json"

    translator: TranslatorName = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    schedule_timezone: str = "Asia/Taipei"
    schedule_hour: int = 0
    schedule_retry_hours: CsvInts = Field(default_factory=lambda: [0, 6])

    publishers: CsvStrings = Field(default_factory=lambda: ["null"])
    http_user_agent: str = "daily-texts-bot/1.0"
    http_timeout: float = 30.0
