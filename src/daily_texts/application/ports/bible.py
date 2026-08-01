from __future__ import annotations

from typing import Protocol


class BibleService(Protocol):
    async def lookup(self, reference: str, *, version: str = "rcuv") -> str:
        """Look up scripture by English reference and return Traditional Chinese text."""
