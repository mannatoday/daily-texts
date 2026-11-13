from __future__ import annotations

from pathlib import Path

import pytest

from daily_texts.domain.exceptions import BibleLookupError
from daily_texts.infrastructure.bible.cache import CachingBibleService


class FakeInner:
    """Records calls so tests can assert the network path was or wasn't taken."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self._fums: dict[tuple[str, str], str] = {}

    async def lookup(self, reference: str, *, version: str = "rcuv") -> str:
        self.calls.append((version, reference))
        self._fums[(version.lower(), reference.strip())] = f"tok:{version}:{reference}"
        return f"TEXT:{version}:{reference}"

    def fums_token(self, version: str, reference: str) -> str:
        return self._fums.get((version.lower(), reference.strip()), "")


@pytest.mark.asyncio
async def test_miss_calls_inner_and_persists(tmp_path: Path) -> None:
    path = tmp_path / "cache.json"
    inner = FakeInner()
    service = CachingBibleService(inner, path)

    text = await service.lookup("John 3:16", version="niv")

    assert text == "TEXT:niv:John 3:16"
    assert inner.calls == [("niv", "John 3:16")]
    assert service.fums_token("niv", "John 3:16") == "tok:niv:John 3:16"

    service.save()
    assert path.is_file()

    # A fresh service backed by the same file serves from disk, no inner call.
    inner2 = FakeInner()
    reloaded = CachingBibleService(inner2, path)
    text2 = await reloaded.lookup("John 3:16", version="niv")
    assert text2 == "TEXT:niv:John 3:16"
    assert inner2.calls == []
    assert reloaded.fums_token("niv", "John 3:16") == "tok:niv:John 3:16"


@pytest.mark.asyncio
async def test_hit_does_not_call_inner(tmp_path: Path) -> None:
    path = tmp_path / "cache.json"
    inner = FakeInner()
    service = CachingBibleService(inner, path)

    await service.lookup("Acts 13:52", version="kjv")
    assert len(inner.calls) == 1

    await service.lookup("Acts 13:52", version="kjv")
    assert len(inner.calls) == 1  # second lookup hit the cache


@pytest.mark.asyncio
async def test_offline_miss_raises(tmp_path: Path) -> None:
    path = tmp_path / "cache.json"
    inner = FakeInner()
    service = CachingBibleService(inner, path, offline=True)

    with pytest.raises(BibleLookupError, match="Offline"):
        await service.lookup("Psalm 23:1", version="niv")
    assert inner.calls == []  # never touched the network


@pytest.mark.asyncio
async def test_offline_hit_serves_from_cache(tmp_path: Path) -> None:
    path = tmp_path / "cache.json"
    # Prime the cache online, then replay offline.
    primer = CachingBibleService(FakeInner(), path)
    await primer.lookup("Psalm 31:24", version="niv")
    primer.save()

    offline = CachingBibleService(FakeInner(), path, offline=True)
    text = await offline.lookup("Psalm 31:24", version="niv")
    assert text == "TEXT:niv:Psalm 31:24"


def test_has_text_reports_presence(tmp_path: Path) -> None:
    path = tmp_path / "cache.json"
    service = CachingBibleService(FakeInner(), path)
    assert service.has_text("niv", "John 1:1") is False
