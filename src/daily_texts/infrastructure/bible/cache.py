from __future__ import annotations

import json
import logging
from pathlib import Path

from daily_texts.application.ports.bible import BibleService
from daily_texts.domain.exceptions import BibleLookupError

logger = logging.getLogger(__name__)


def _key(version: str, reference: str) -> tuple[str, str]:
    return version.lower().strip(), reference.strip()


class CachingBibleService:
    """Persist looked-up verse text so daily publishing can replay offline.

    Wraps an inner :class:`BibleService`. Every lookup is keyed by the input
    reference and the site version code. In offline mode a cache miss raises
    ``BibleLookupError`` so the caller leaves that version blank and the page
    falls back to the Bible Gateway link, instead of hitting the network.
    """

    def __init__(
        self,
        inner: BibleService,
        cache_path: Path,
        *,
        offline: bool = False,
    ) -> None:
        self._inner = inner
        self._cache_path = Path(cache_path)
        self._offline = offline
        self._dirty = False
        # version -> reference -> {"text": str, "fums": str}
        self._cache: dict[str, dict[str, dict[str, str]]] = self._load()

    def _load(self) -> dict[str, dict[str, dict[str, str]]]:
        if not self._cache_path.is_file():
            return {}
        try:
            raw = json.loads(self._cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("Could not read verse cache %s: %s", self._cache_path, exc)
            return {}
        if not isinstance(raw, dict):
            return {}
        cache: dict[str, dict[str, dict[str, str]]] = {}
        for version, refs in raw.items():
            if not isinstance(refs, dict):
                continue
            version_key = str(version).lower().strip()
            bucket = cache.setdefault(version_key, {})
            for reference, entry in refs.items():
                if isinstance(entry, dict):
                    text = str(entry.get("text") or "")
                    fums = str(entry.get("fums") or "")
                elif isinstance(entry, str):
                    text, fums = entry, ""
                else:
                    continue
                bucket[str(reference).strip()] = {"text": text, "fums": fums}
        return cache

    def _lookup_cached(self, version: str, reference: str) -> dict[str, str] | None:
        version_key, reference_key = _key(version, reference)
        return self._cache.get(version_key, {}).get(reference_key)

    def has_text(self, version: str, reference: str) -> bool:
        cached = self._lookup_cached(version, reference)
        return bool(cached and cached.get("text"))

    def _store(self, version: str, reference: str, text: str, fums: str) -> None:
        version_key, reference_key = _key(version, reference)
        bucket = self._cache.setdefault(version_key, {})
        bucket[reference_key] = {"text": text, "fums": fums}
        self._dirty = True

    async def lookup(self, reference: str, *, version: str = "rcuv") -> str:
        cached = self._lookup_cached(version, reference)
        if cached is not None and cached.get("text"):
            return cached["text"]

        if self._offline:
            raise BibleLookupError(
                f"Offline: no cached {version} text for {reference!r}"
            )

        text = await self._inner.lookup(reference, version=version)
        fums = ""
        getter = getattr(self._inner, "fums_token", None)
        if getter is not None:
            fums = getter(version, reference) or ""
        self._store(version, reference, text, fums)
        return text

    def fums_token(self, version: str, reference: str) -> str:
        cached = self._lookup_cached(version, reference)
        if cached is not None and cached.get("fums"):
            return cached["fums"]
        getter = getattr(self._inner, "fums_token", None)
        if getter is not None:
            return getter(version, reference) or ""
        return ""

    def save(self) -> None:
        """Write the cache to disk if anything new was looked up."""
        if not self._dirty:
            return
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        ordered = {
            version: {
                reference: self._cache[version][reference]
                for reference in sorted(self._cache[version])
            }
            for version in sorted(self._cache)
        }
        self._cache_path.write_text(
            json.dumps(ordered, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self._dirty = False
        logger.info("Wrote verse cache %s", self._cache_path)
