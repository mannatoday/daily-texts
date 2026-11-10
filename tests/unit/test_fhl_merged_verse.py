from __future__ import annotations

import httpx
import pytest

from daily_texts.domain.exceptions import BibleLookupError
from daily_texts.infrastructure.bible.fhl_rcuv import FhlRcuvBibleService
from daily_texts.infrastructure.config import Settings

_MERGED = (
    "<h3>在　神面前可以坦然無懼</h3>"
    "這樣，我們就知道我們是屬於真理的。"
    "即使我們的心責備我們，在　神面前我們也可以心安理得，"
    "因為他比我們的心大，他知道一切。"
)
_FOLLOWING = "親愛的，我們的心若不責備我們，在　神面前我們就可以坦然無懼了。"
_EXPECTED = (
    "這樣，我們就知道我們是屬於真理的。"
    "即使我們的心責備我們，在 神面前我們也可以心安理得，"
    "因為他比我們的心大，他知道一切。"
)


def _settings() -> Settings:
    return Settings(
        fhl_api_base="https://bible.example/json",
        http_max_retries=0,
        http_retry_backoff_seconds=0,
    )


def _row(sec: int, text: str) -> dict[str, object]:
    return {"chap": 3, "sec": sec, "bible_text": text}


@pytest.mark.asyncio
async def test_lookup_uses_previous_verse_when_number_is_missing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        sec = request.url.params["sec"]
        if sec == "20":
            return httpx.Response(
                200,
                json={"status": "success", "record": []},
            )
        assert sec == "19-21"
        return httpx.Response(
            200,
            json={
                "status": "success",
                "record": [_row(19, _MERGED), _row(21, _FOLLOWING)],
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    text = await FhlRcuvBibleService(client, _settings()).lookup(
        "1 John 3:20", version="ncv"
    )
    assert text == _EXPECTED
    await client.aclose()


@pytest.mark.asyncio
async def test_lookup_ignores_footnote_letter_and_uses_merged_verse() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        sec = request.url.params["sec"]
        if sec == "20":
            return httpx.Response(
                200,
                json={"status": "success", "record": [_row(20, "a")]},
            )
        assert sec == "19-21"
        return httpx.Response(
            200,
            json={
                "status": "success",
                "record": [_row(19, _MERGED), _row(20, "a"), _row(21, _FOLLOWING)],
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    text = await FhlRcuvBibleService(client, _settings()).lookup(
        "1 John 3:20", version="wcb"
    )
    assert text == _EXPECTED
    await client.aclose()


@pytest.mark.asyncio
async def test_lookup_uses_previous_verse_for_hebrew_numbering_offset() -> None:
    # Moravian/German versification counts a Psalm superscription, so
    # "Psalm 31:25" runs one past the Chinese numbering (chapter ends at 24).
    # FHL returns nothing for v25 and no following v26 exists; the text lives
    # in the previous verse.
    last_verse = "凡仰望耶和華的人，你們都要壯膽，堅固你們的心！"

    def handler(request: httpx.Request) -> httpx.Response:
        sec = request.url.params["sec"]
        if sec == "25":
            return httpx.Response(200, json={"status": "success", "record": []})
        assert sec == "24-26"
        return httpx.Response(
            200,
            json={"status": "success", "record": [{"chap": 31, "sec": 24, "bible_text": last_verse}]},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    text = await FhlRcuvBibleService(client, _settings()).lookup(
        "Psalm 31:25", version="rcuv"
    )
    assert text == last_verse
    await client.aclose()


@pytest.mark.asyncio
async def test_lookup_keeps_a_verse_that_is_present() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.params["sec"])
        return httpx.Response(
            200,
            json={
                "status": "success",
                "record": [_row(8, "你將我們的罪孽擺在你面前。")],
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    text = await FhlRcuvBibleService(client, _settings()).lookup(
        "Psalm 90:8", version="rcuv"
    )
    assert text == "你將我們的罪孽擺在你面前。"
    assert calls == ["8"]
    await client.aclose()


@pytest.mark.asyncio
async def test_lookup_still_fails_when_neighbors_are_missing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "success", "record": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(BibleLookupError, match="no verses"):
        await FhlRcuvBibleService(client, _settings()).lookup("1 John 3:20", version="ncv")
    await client.aclose()
