from __future__ import annotations

import httpx
import pytest
import respx

from daily_texts.domain.exceptions import TranslationError
from daily_texts.infrastructure.config import Settings
from daily_texts.infrastructure.translators.google_translator import GoogleTranslator


@pytest.mark.asyncio
@respx.mock
async def test_google_translator_success() -> None:
    route = respx.post("https://translation.googleapis.com/language/translate/v2").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "translations": [
                        {"translatedText": "偉大的自有永有者，請聽我們的禱告。阿們。"}
                    ]
                }
            },
        )
    )
    settings = Settings(google_translate_api_key="test-key")
    translator = GoogleTranslator(settings)
    result = await translator.translate("Great I Am, hear our prayer. Amen.")
    assert "禱告" in result
    assert route.called


@pytest.mark.asyncio
async def test_google_translator_requires_key() -> None:
    settings = Settings(google_translate_api_key="")
    translator = GoogleTranslator(settings)
    assert translator.available() is False
    with pytest.raises(TranslationError, match="GOOGLE_TRANSLATE_API_KEY"):
        await translator.translate("Amen.")
