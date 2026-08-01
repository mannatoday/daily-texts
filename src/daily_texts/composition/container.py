from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from daily_texts.application.dto import FormatName
from daily_texts.application.ports.bible import BibleService
from daily_texts.application.ports.formatter import ContentFormatter
from daily_texts.application.ports.provider import DailyTextProvider
from daily_texts.application.ports.publisher import Publisher
from daily_texts.application.ports.translator import TextTranslator
from daily_texts.application.use_cases.fetch_and_localize import FetchAndLocalizeDailyText
from daily_texts.infrastructure.bible.fhl_rcuv import FhlRcuvBibleService
from daily_texts.infrastructure.config import Settings
from daily_texts.infrastructure.formatters.html import HtmlFormatter
from daily_texts.infrastructure.formatters.markdown import MarkdownFormatter
from daily_texts.infrastructure.formatters.plain_text import PlainTextFormatter
from daily_texts.infrastructure.http import create_http_client
from daily_texts.infrastructure.providers.email import EmailInboxProvider
from daily_texts.infrastructure.providers.moravian_html_sidebar import (
    MoravianHtmlSidebarProvider,
)
from daily_texts.infrastructure.publishers.email import EmailPublisher
from daily_texts.infrastructure.publishers.line import LinePublisher
from daily_texts.infrastructure.publishers.null_publisher import NullPublisher
from daily_texts.infrastructure.publishers.telegram import TelegramPublisher
from daily_texts.infrastructure.publishers.website import WebsitePublisher
from daily_texts.infrastructure.translators.noop_translator import NoopTranslator
from daily_texts.infrastructure.translators.openai_translator import OpenAITranslator

_FORMATTERS: dict[FormatName, type] = {
    "markdown": MarkdownFormatter,
    "html": HtmlFormatter,
    "text": PlainTextFormatter,
}

_PUBLISHERS: dict[str, type[Publisher]] = {
    "null": NullPublisher,
    "line": LinePublisher,
    "email": EmailPublisher,
    "telegram": TelegramPublisher,
    "website": WebsitePublisher,
}


@dataclass
class Container:
    settings: Settings
    http_client: httpx.AsyncClient
    provider: DailyTextProvider
    bible: BibleService
    translator: TextTranslator
    formatters: list[ContentFormatter]
    publishers: list[Publisher]
    use_case: FetchAndLocalizeDailyText

    async def aclose(self) -> None:
        await self.http_client.aclose()


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or Settings()
    http_client = create_http_client(settings)
    provider = _build_provider(settings, http_client)
    bible = FhlRcuvBibleService(http_client, settings)
    translator = _build_translator(settings)
    formatters = _build_formatters(settings)
    publishers = _build_publishers(settings)
    use_case = FetchAndLocalizeDailyText(
        provider=provider,
        bible=bible,
        translator=translator,
        formatters=formatters,
        publishers=publishers,
        output_dir=settings.output_dir,
        bible_version=settings.bible_version,
        include_source_link=settings.include_source_link,
    )
    return Container(
        settings=settings,
        http_client=http_client,
        provider=provider,
        bible=bible,
        translator=translator,
        formatters=formatters,
        publishers=publishers,
        use_case=use_case,
    )


def _build_provider(settings: Settings, client: httpx.AsyncClient) -> DailyTextProvider:
    if settings.provider == "moravian_html":
        return MoravianHtmlSidebarProvider(client, settings)
    if settings.provider == "email":
        return EmailInboxProvider()
    raise ValueError(f"Unknown provider: {settings.provider}")


def _build_translator(settings: Settings) -> TextTranslator:
    if settings.translator == "openai":
        return OpenAITranslator(settings)
    if settings.translator == "noop":
        return NoopTranslator()
    raise ValueError(f"Unknown translator: {settings.translator}")


def _build_formatters(settings: Settings) -> list[ContentFormatter]:
    result: list[ContentFormatter] = []
    for name in settings.formats:
        cls: Any = _FORMATTERS.get(name)
        if cls is None:
            raise ValueError(f"Unknown format: {name}")
        result.append(cls())
    return result


def _build_publishers(settings: Settings) -> list[Publisher]:
    result: list[Publisher] = []
    for name in settings.publishers:
        cls = _PUBLISHERS.get(name)
        if cls is None:
            raise ValueError(f"Unknown publisher: {name}")
        result.append(cls())
    if not result:
        result.append(NullPublisher())
    return result
