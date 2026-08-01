from __future__ import annotations

import html
import logging

import httpx

from daily_texts.domain.exceptions import TranslationError
from daily_texts.infrastructure.config import Settings
from daily_texts.infrastructure.http import request_with_retries

logger = logging.getLogger(__name__)

_TRANSLATE_URL = "https://translation.googleapis.com/language/translate/v2"


class GoogleTranslator:
    """Google Cloud Translation API v2 (free tier: 500k characters/month)."""

    name = "google"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client
        self._owns_client = client is None

    def available(self) -> bool:
        return bool(self._settings.google_translate_api_key.strip())

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._settings.http_timeout,
                headers={"User-Agent": self._settings.http_user_agent},
            )
        return self._client

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def translate(
        self,
        text: str,
        *,
        source_lang: str = "en",
        target_lang: str = "zh-TW",
    ) -> str:
        if not text.strip():
            raise TranslationError("Cannot translate empty text")
        if not self.available():
            raise TranslationError("GOOGLE_TRANSLATE_API_KEY is not configured")

        # Cloud Translation uses BCP-47-ish codes; zh-TW is supported.
        source = "en" if source_lang.lower().startswith("en") else source_lang
        target = "zh-TW" if target_lang.lower() in {"zh-tw", "zh-hant", "zh"} else target_lang

        client = await self._get_client()
        try:
            response = await request_with_retries(
                client,
                "POST",
                _TRANSLATE_URL,
                max_retries=self._settings.http_max_retries,
                backoff_seconds=self._settings.http_retry_backoff_seconds,
                params={"key": self._settings.google_translate_api_key},
                json={
                    "q": text,
                    "source": source,
                    "target": target,
                    "format": "text",
                },
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise TranslationError(f"Google Translate request failed: {exc}") from exc
        except ValueError as exc:
            raise TranslationError(f"Google Translate returned invalid JSON: {exc}") from exc

        try:
            translated = payload["data"]["translations"][0]["translatedText"]
        except (KeyError, IndexError, TypeError) as exc:
            raise TranslationError(f"Unexpected Google Translate response: {payload!r}") from exc

        result = html.unescape(str(translated)).strip()
        if not result:
            raise TranslationError("Google Translate returned empty translation")
        return result
