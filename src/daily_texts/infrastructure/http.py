from __future__ import annotations

import asyncio
import logging

import httpx

from daily_texts.infrastructure.config import Settings

logger = logging.getLogger(__name__)

# Transient failures worth retrying before giving up.
_RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})


def create_http_client(settings: Settings) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=settings.http_timeout,
        headers={"User-Agent": settings.http_user_agent},
        follow_redirects=True,
    )


async def request_with_retries(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    max_retries: int = 3,
    backoff_seconds: float = 1.0,
    **kwargs: object,
) -> httpx.Response:
    """GET/POST with exponential backoff on transport errors and retryable statuses.

    ``max_retries`` is the number of retries after the first attempt
    (total attempts = max_retries + 1).
    """
    retries = max(0, max_retries)
    last_error: BaseException | None = None

    for attempt in range(retries + 1):
        try:
            response = await client.request(method, url, **kwargs)  # type: ignore[arg-type]
        except httpx.TransportError as exc:
            last_error = exc
            if attempt >= retries:
                raise
            delay = backoff_seconds * (2**attempt)
            logger.warning(
                "HTTP %s %s transport error (attempt %d/%d): %s; retrying in %.1fs",
                method.upper(),
                url,
                attempt + 1,
                retries + 1,
                exc,
                delay,
            )
            await asyncio.sleep(delay)
            continue

        if response.status_code in _RETRYABLE_STATUS and attempt < retries:
            delay = backoff_seconds * (2**attempt)
            logger.warning(
                "HTTP %s %s returned %s (attempt %d/%d); retrying in %.1fs",
                method.upper(),
                url,
                response.status_code,
                attempt + 1,
                retries + 1,
                delay,
            )
            await asyncio.sleep(delay)
            continue

        return response

    if last_error is not None:
        raise last_error
    raise RuntimeError("request_with_retries exhausted without response or error")
