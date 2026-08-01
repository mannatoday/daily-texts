from __future__ import annotations

import httpx

from daily_texts.infrastructure.config import Settings


def create_http_client(settings: Settings) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=settings.http_timeout,
        headers={"User-Agent": settings.http_user_agent},
        follow_redirects=True,
    )
