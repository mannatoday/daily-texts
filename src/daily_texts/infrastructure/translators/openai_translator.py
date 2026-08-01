from __future__ import annotations

import logging

from openai import AsyncOpenAI

from daily_texts.domain.exceptions import TranslationError
from daily_texts.infrastructure.config import Settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "你是一位精通基督教靈修用語的翻譯者。"
    "請將英文禱告翻譯成繁體中文，語氣恭敬、自然。"
    "保留「Amen」為「阿們」。"
    "只輸出譯文，不要加說明或標題。"
)


class OpenAITranslator:
    def __init__(self, settings: Settings, client: AsyncOpenAI | None = None) -> None:
        self._settings = settings
        self._client = client or AsyncOpenAI(api_key=settings.openai_api_key or None)

    async def translate(
        self,
        text: str,
        *,
        source_lang: str = "en",
        target_lang: str = "zh-TW",
    ) -> str:
        if not text.strip():
            raise TranslationError("Cannot translate empty text")
        if not self._settings.openai_api_key:
            raise TranslationError("OPENAI_API_KEY is not configured")

        try:
            response = await self._client.chat.completions.create(
                model=self._settings.openai_model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
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
        except Exception as exc:  # noqa: BLE001 — surface as domain error
            raise TranslationError(f"OpenAI translation failed: {exc}") from exc

        content = response.choices[0].message.content
        if not content or not content.strip():
            raise TranslationError("OpenAI returned empty translation")
        return content.strip()
