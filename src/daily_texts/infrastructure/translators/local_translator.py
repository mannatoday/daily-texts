from __future__ import annotations

import logging

from openai import AsyncOpenAI

from daily_texts.domain.exceptions import TranslationError
from daily_texts.infrastructure.config import Settings
from daily_texts.infrastructure.translators.prompt import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class LocalTranslator:
    """OpenAI-compatible local endpoint (e.g. Ollama / LM Studio)."""

    name = "local"

    def __init__(self, settings: Settings, client: AsyncOpenAI | None = None) -> None:
        self._settings = settings
        self._client = client

    def available(self) -> bool:
        return bool(self._settings.local_translator_base_url.strip())

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            if not self.available():
                raise TranslationError("LOCAL_TRANSLATOR_BASE_URL is not configured")
            self._client = AsyncOpenAI(
                api_key=self._settings.local_translator_api_key or "local",
                base_url=self._settings.local_translator_base_url,
            )
        return self._client

    async def translate(
        self,
        text: str,
        *,
        source_lang: str = "en",
        target_lang: str = "zh-TW",
    ) -> str:
        if not text.strip():
            raise TranslationError("Cannot translate empty text")

        client = self._get_client()
        try:
            response = await client.chat.completions.create(
                model=self._settings.local_translator_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Source language: {source_lang}\n"
                            f"Target language: {target_lang}\n\n"
                            f"{text}"
                        ),
                    },
                ],
                temperature=0.2,
            )
        except TranslationError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise TranslationError(f"Local translation failed: {exc}") from exc

        content = response.choices[0].message.content
        if not content or not content.strip():
            raise TranslationError("Local translator returned empty translation")
        return content.strip()
