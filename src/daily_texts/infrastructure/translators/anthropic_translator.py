from __future__ import annotations

import logging

from anthropic import AsyncAnthropic

from daily_texts.domain.exceptions import TranslationError
from daily_texts.infrastructure.config import Settings
from daily_texts.infrastructure.translators.prompt import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class AnthropicTranslator:
    name = "anthropic"

    def __init__(self, settings: Settings, client: AsyncAnthropic | None = None) -> None:
        self._settings = settings
        self._client = client

    def available(self) -> bool:
        return bool(self._settings.anthropic_api_key.strip())

    def _get_client(self) -> AsyncAnthropic:
        if self._client is None:
            if not self.available():
                raise TranslationError("ANTHROPIC_API_KEY is not configured")
            self._client = AsyncAnthropic(api_key=self._settings.anthropic_api_key)
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
            response = await client.messages.create(
                model=self._settings.anthropic_model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Source language: {source_lang}\n"
                            f"Target language: {target_lang}\n\n"
                            f"{text}"
                        ),
                    }
                ],
            )
        except TranslationError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise TranslationError(f"Anthropic translation failed: {exc}") from exc

        parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
        content = "".join(parts).strip()
        if not content:
            raise TranslationError("Anthropic returned empty translation")
        return content
