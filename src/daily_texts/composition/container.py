from __future__ import annotations

import logging
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
from daily_texts.infrastructure.formatters.json_formatter import JsonFormatter
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
from daily_texts.infrastructure.publishers.static_site import StaticSitePublisher
from daily_texts.infrastructure.publishers.telegram import TelegramPublisher
from daily_texts.infrastructure.publishers.website import WebsitePublisher
from daily_texts.infrastructure.translators.anthropic_translator import AnthropicTranslator
from daily_texts.infrastructure.translators.composite_translator import CompositeTranslator
from daily_texts.infrastructure.translators.fallback_translator import FallbackTranslator
from daily_texts.infrastructure.translators.google_translator import GoogleTranslator
from daily_texts.infrastructure.translators.local_translator import LocalTranslator
from daily_texts.infrastructure.translators.openai_translator import OpenAITranslator

logger = logging.getLogger(__name__)

_FORMATTERS: dict[FormatName, type] = {
    "markdown": MarkdownFormatter,
    "html": HtmlFormatter,
    "text": PlainTextFormatter,
    "json": JsonFormatter,
}

_PUBLISHERS: dict[str, type[Publisher]] = {
    "null": NullPublisher,
    "line": LinePublisher,
    "email": EmailPublisher,
    "telegram": TelegramPublisher,
    "website": WebsitePublisher,
    "static_site": StaticSitePublisher,
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
    if settings.translator in {"noop", "fallback"}:
        return FallbackTranslator()
    if settings.translator == "openai":
        return OpenAITranslator(settings)
    if settings.translator == "anthropic":
        return AnthropicTranslator(settings)
    if settings.translator == "google":
        return GoogleTranslator(settings)
    if settings.translator == "local":
        return LocalTranslator(settings)
    if settings.translator == "composite":
        return CompositeTranslator(_build_translator_chain(settings))
    raise ValueError(f"Unknown translator: {settings.translator}")


def _build_translator_chain(settings: Settings) -> list[TextTranslator]:
    chain: list[TextTranslator] = []
    for name in settings.translators:
        key = "fallback" if name == "noop" else name
        if key == "openai":
            chain.append(OpenAITranslator(settings))
        elif key == "anthropic":
            chain.append(AnthropicTranslator(settings))
        elif key == "google":
            chain.append(GoogleTranslator(settings))
        elif key == "local":
            chain.append(LocalTranslator(settings))
        elif key == "fallback":
            chain.append(FallbackTranslator())
        else:
            raise ValueError(f"Unknown translator in TRANSLATORS chain: {name}")
    if not chain:
        chain.append(FallbackTranslator())
    elif not any(isinstance(t, FallbackTranslator) for t in chain):
        chain.append(FallbackTranslator())
    return chain


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
        if name == "static_site":
            result.append(
                StaticSitePublisher(
                    settings.site_dir,
                    include_source_link=settings.include_source_link,
                )
            )
        else:
            result.append(cls())
    if not result:
        result.append(NullPublisher())
    return result
