from __future__ import annotations

import httpx
import pytest

from daily_texts.domain.exceptions import BibleLookupError
from daily_texts.infrastructure.bible.english import (
    ApiBibleService,
    EsvBibleService,
    KjvBibleService,
    passage_ids,
)
from daily_texts.infrastructure.config import Settings


def _settings(**overrides: str) -> Settings:
    base = {
        "esv_api_key": "secret",
        "esv_api_base": "https://api.esv.org/v3",
        "kjv_api_base": "https://bible-api.com",
    }
    base.update(overrides)
    return Settings(**base)


@pytest.mark.asyncio
async def test_esv_lookup_returns_passage_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Token secret"
        assert request.url.params["include-verse-numbers"] == "false"
        assert request.url.params["q"] == "Haggai 2:9"
        return httpx.Response(200, json={"passages": ["  The latter glory \n of this house.  "]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    text = await EsvBibleService(client, _settings()).lookup("Haggai 2:9")
    assert text == "The latter glory of this house."
    await client.aclose()


@pytest.mark.asyncio
async def test_esv_lookup_requires_a_key() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(500)))
    with pytest.raises(BibleLookupError, match="ESV_API_KEY"):
        await EsvBibleService(client, _settings(esv_api_key="")).lookup("John 3:16")
    await client.aclose()


@pytest.mark.asyncio
async def test_kjv_lookup_returns_public_domain_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "bible-api.com" in str(request.url)
        assert request.url.params["translation"] == "kjv"
        return httpx.Response(
            200,
            json={"text": "For God so loved the world.\n", "translation_id": "kjv"},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    text = await KjvBibleService(client, _settings()).lookup("John 3:16")
    assert text == "For God so loved the world."
    await client.aclose()


def test_passage_ids_cover_ranges_and_skipped_verses() -> None:
    assert passage_ids("Haggai 2:9") == ["HAG.2.9"]
    assert passage_ids("John 4:25-26") == ["JHN.4.25-JHN.4.26"]
    assert passage_ids("Psalm 85:9,10") == ["PSA.85.9-PSA.85.10"]
    assert passage_ids("Psalm 103:2,4") == ["PSA.103.2", "PSA.103.4"]
    assert passage_ids("1 Samuel 3:9") == ["1SA.3.9"]


@pytest.mark.asyncio
async def test_api_bible_lookup_uses_the_licensed_bible() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["api-key"] == "bible-secret"
        path = request.url.path
        if path.endswith("/bibles"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "niv-id", "abbreviation": "NIV", "name": "New International Version"},
                        {"id": "nlt-id", "abbreviation": "NLT", "name": "New Living Translation"},
                        {
                            "id": "nirv-id",
                            "abbreviation": "NIrV",
                            "name": "New International Reader's Version",
                        },
                    ]
                },
            )
        assert path.endswith("/bibles/niv-id/passages/JHN.3.16")
        return httpx.Response(
            200,
            json={
                "data": {"content": " For God so loved the world. "},
                "meta": {"fumsToken": "token-1"},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = ApiBibleService(
        client,
        _settings(
            api_bible_api_key="bible-secret",
            api_bible_api_base="https://api.scripture.api.bible/v1",
        ),
    )
    text = await service.lookup("John 3:16", version="niv")
    assert text == "For God so loved the world."
    assert service.fums_token("niv", "John 3:16") == "token-1"
    await client.aclose()


@pytest.mark.asyncio
async def test_api_bible_lookup_requires_a_key() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(500)))
    service = ApiBibleService(client, _settings(api_bible_api_key=""))
    with pytest.raises(BibleLookupError, match="API_BIBLE_API_KEY"):
        await service.lookup("John 3:16", version="niv")
    await client.aclose()
