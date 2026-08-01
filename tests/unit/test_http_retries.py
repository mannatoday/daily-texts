from __future__ import annotations

import httpx
import pytest
import respx

from daily_texts.infrastructure.http import request_with_retries


@pytest.mark.asyncio
@respx.mock
async def test_request_retries_on_503_then_succeeds() -> None:
    route = respx.get("https://example.test/daily").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(503),
            httpx.Response(200, text="ok"),
        ]
    )

    async with httpx.AsyncClient() as client:
        response = await request_with_retries(
            client,
            "GET",
            "https://example.test/daily",
            max_retries=3,
            backoff_seconds=0.01,
        )

    assert response.status_code == 200
    assert response.text == "ok"
    assert route.call_count == 3


@pytest.mark.asyncio
@respx.mock
async def test_request_retries_on_transport_error_then_succeeds() -> None:
    route = respx.get("https://example.test/daily").mock(
        side_effect=[
            httpx.ConnectError("boom"),
            httpx.Response(200, text="ok"),
        ]
    )

    async with httpx.AsyncClient() as client:
        response = await request_with_retries(
            client,
            "GET",
            "https://example.test/daily",
            max_retries=2,
            backoff_seconds=0.01,
        )

    assert response.status_code == 200
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_request_gives_up_after_retries() -> None:
    respx.get("https://example.test/daily").mock(return_value=httpx.Response(502))

    async with httpx.AsyncClient() as client:
        response = await request_with_retries(
            client,
            "GET",
            "https://example.test/daily",
            max_retries=2,
            backoff_seconds=0.01,
        )

    # Exhausted retries still returns the last response for the caller to raise_for_status.
    assert response.status_code == 502
