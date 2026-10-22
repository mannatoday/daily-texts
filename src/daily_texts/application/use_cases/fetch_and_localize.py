from __future__ import annotations

import asyncio
import logging
from datetime import date
from pathlib import Path

from daily_texts.application.dto import FormattedOutput, PipelineResult
from daily_texts.application.ports.bible import BibleService
from daily_texts.application.ports.formatter import ContentFormatter
from daily_texts.application.ports.provider import DailyTextProvider
from daily_texts.application.ports.publisher import Publisher
from daily_texts.application.ports.translator import TextTranslator
from daily_texts.domain.bible_versions import (
    DEFAULT_ENGLISH_VERSION,
    DEFAULT_VERSION,
    ENGLISH_LOOKUP_VERSIONS,
    ENGLISH_VERSIONS,
    FHL_VERSION_CODES,
    SITE_VERSIONS,
)
from daily_texts.domain.exceptions import BibleLookupError, TranslationError
from daily_texts.domain.models import LocalizedDailyText, LocalizedWatchword, RawDailyText
from daily_texts.domain.references import localize_reference


logger = logging.getLogger(__name__)


class FetchAndLocalizeDailyText:
    def __init__(
        self,
        provider: DailyTextProvider,
        bible: BibleService,
        translator: TextTranslator,
        formatters: list[ContentFormatter],
        publishers: list[Publisher],
        *,
        output_dir: Path,
        bible_version: str = "rcuv",
        include_source_link: bool = True,
    ) -> None:
        self._provider = provider
        self._bible = bible
        self._translator = translator
        self._formatters = formatters
        self._publishers = publishers
        self._output_dir = output_dir
        self._bible_version = bible_version
        self._include_source_link = include_source_link
        self._site_version_codes = [code for code, _label in SITE_VERSIONS] + [
            code for code, _label in ENGLISH_VERSIONS
        ]

    async def run(
        self,
        target_date: date | None = None,
        *,
        force: bool = False,
        expect_date: date | None = None,
        write_files: bool = True,
    ) -> PipelineResult:
        """Fetch, localize, format, optionally write files, and publish.

        expect_date: if set, skip when fetched date does not match (retry window).
        """
        if target_date is not None and not force and self._output_exists(target_date):
            return PipelineResult(
                raw=_placeholder_raw(target_date),
                localized=_placeholder_localized(target_date),
                skipped=True,
                skip_reason=f"Output already exists for {target_date}; use --force to overwrite",
            )

        raw = await self._provider.fetch(target_date)

        check_date = expect_date or target_date
        if check_date is not None and raw.date != check_date:
            return PipelineResult(
                raw=raw,
                localized=_placeholder_localized(raw.date),
                skipped=True,
                skip_reason=(
                    f"Fetched date {raw.date} does not match expected {check_date}; "
                    "will retry later"
                ),
            )

        if not force and self._output_exists(raw.date):
            return PipelineResult(
                raw=raw,
                localized=_placeholder_localized(raw.date),
                skipped=True,
                skip_reason=f"Output already exists for {raw.date}; use --force to overwrite",
            )

        localized = await self._localize(raw)
        _require_default_english(localized)
        outputs = [
            formatter.format(localized, include_source_link=self._include_source_link)
            for formatter in self._formatters
        ]

        if write_files:
            self._write_outputs(raw.date, outputs)

        publish_results = await asyncio.gather(
            *(publisher.publish(outputs, localized) for publisher in self._publishers)
        )

        return PipelineResult(
            raw=raw,
            localized=localized,
            outputs=outputs,
            publish_results=list(publish_results),
        )

    async def _localize(self, raw: RawDailyText) -> LocalizedDailyText:
        if raw.metadata.get("prayer_lang") == "zh":
            prayer_zh = raw.prayer_en
            translation_report = {
                "provider": raw.metadata.get("provider") or "dataset",
                "status": "already_zh",
                "source_chars": len(raw.prayer_en),
                "result_chars": len(prayer_zh),
                "kept_english": False,
            }
        else:
            prayer_zh, translation_report = await self._translate_or_fallback(raw.prayer_en)
        ot = await self._localize_watchword(raw.ot)
        nt = await self._localize_watchword(raw.nt)
        week = None
        if raw.week_watchword is not None:
            week = await self._localize_watchword(raw.week_watchword)

        metadata = dict(raw.metadata)
        metadata["translation"] = translation_report

        return LocalizedDailyText(
            date=raw.date,
            date_display=raw.date_display,
            psalm=raw.psalm,
            readings=list(raw.readings),
            ot=ot,
            nt=nt,
            week_watchword=week,
            prayer_en=raw.prayer_en,
            prayer_zh=prayer_zh,
            source_url=raw.source_url,
            metadata=metadata,
        )

    async def _localize_watchword(self, watchword) -> LocalizedWatchword:
        translations, fums = await self._lookup_all_versions(
            watchword.reference, watchword.text_en
        )
        text_zh = _chinese_text(translations, watchword.text_en)
        return LocalizedWatchword(
            reference=watchword.reference,
            reference_zh=localize_reference(watchword.reference),
            text_en=watchword.text_en,
            text_zh=text_zh,
            translations=translations,
            fums_tokens=fums,
            bible_url=watchword.bible_url,
        )

    async def _lookup_all_versions(
        self, reference: str, english: str
    ) -> tuple[dict[str, str], dict[str, str]]:
        fums: dict[str, str] = {}

        async def one(site_code: str) -> tuple[str, str]:
            english_version = ENGLISH_LOOKUP_VERSIONS.get(site_code)
            if english_version:
                try:
                    text = await self._bible.lookup(reference, version=english_version)
                    token = ""
                    getter = getattr(self._bible, "fums_token", None)
                    if getter is not None:
                        token = getter(english_version, reference) or ""
                    if token:
                        fums[site_code] = token
                    return site_code, text
                except BibleLookupError as exc:
                    logger.warning(
                        "Bible lookup failed for %s (%s): %s",
                        reference,
                        site_code,
                        exc,
                    )
                    return site_code, None
            fhl = FHL_VERSION_CODES.get(site_code)
            if not fhl:
                logger.info(
                    "No FHL mapping for %s; using English for %s", site_code, reference
                )
                return site_code, english
            try:
                text = await self._bible.lookup(reference, version=fhl)
                return site_code, text
            except BibleLookupError as exc:
                logger.warning(
                    "Bible lookup failed for %s (%s/%s): %s; using English",
                    reference,
                    site_code,
                    fhl,
                    exc,
                )
                return site_code, english

        pairs = await asyncio.gather(*(one(code) for code in self._site_version_codes))
        translations = {
            code: text for code, text in pairs if text and text.strip()
        }
        return translations, fums

    async def _lookup_or_fallback(self, reference: str, english: str) -> str:
        try:
            return await self._bible.lookup(reference, version=self._bible_version)
        except BibleLookupError as exc:
            logger.warning("Bible lookup failed for %s: %s; using English fallback", reference, exc)
            return english

    async def _translate_or_fallback(self, prayer_en: str) -> tuple[str, dict]:
        provider_name = getattr(self._translator, "name", self._translator.__class__.__name__)
        try:
            prayer_zh = await self._translator.translate(
                prayer_en,
                source_lang="en",
                target_lang="zh-TW",
            )
            report = getattr(self._translator, "last_report", None)
            if not isinstance(report, dict) or not report:
                kept_english = prayer_zh.strip() == prayer_en.strip()
                report = {
                    "provider": provider_name,
                    "status": (
                        "fallback_english"
                        if provider_name in {"fallback", "noop"} or kept_english
                        else "ok"
                    ),
                    "source_chars": len(prayer_en),
                    "result_chars": len(prayer_zh),
                    "kept_english": kept_english,
                }
            else:
                report = dict(report)
            logger.info(
                "Prayer translation report: provider=%s status=%s kept_english=%s",
                report.get("provider"),
                report.get("status"),
                report.get("kept_english"),
            )
            return prayer_zh, report
        except TranslationError as exc:
            logger.warning("Prayer translation failed: %s; keeping English", exc)
            report = {
                "provider": None,
                "status": "failed_kept_english",
                "error": str(exc),
                "source_chars": len(prayer_en),
                "result_chars": len(prayer_en),
                "kept_english": True,
            }
            prior = getattr(self._translator, "last_report", None)
            if isinstance(prior, dict) and prior:
                report = {**prior, **report}
            return prayer_en, report

    def _day_dir(self, day: date) -> Path:
        return self._output_dir / day.isoformat()

    def _output_exists(self, day: date) -> bool:
        day_dir = self._day_dir(day)
        if not day_dir.is_dir():
            return False
        return any(day_dir.glob("daily-text.*"))

    def _write_outputs(self, day: date, outputs: list[FormattedOutput]) -> None:
        day_dir = self._day_dir(day)
        day_dir.mkdir(parents=True, exist_ok=True)
        for item in outputs:
            path = day_dir / item.filename
            path.write_text(item.content, encoding="utf-8")
            logger.info("Wrote %s", path)


def _chinese_text(translations: dict[str, str], fallback: str) -> str:
    preferred = (translations.get(DEFAULT_VERSION) or "").strip()
    if preferred:
        return preferred
    for code, _label in SITE_VERSIONS:
        text = (translations.get(code) or "").strip()
        if text:
            return text
    return fallback


def _require_default_english(content: LocalizedDailyText) -> None:
    """Fail the publish when the default English text is missing.

    A blank NIV used to be saved as a finished page, and the next scheduled
    run then skipped because the file already existed.
    """
    missing: list[str] = []
    watchwords = [("舊約", content.ot), ("新約", content.nt)]
    if content.week_watchword is not None and content.week_watchword.reference.strip():
        watchwords.append(("本週", content.week_watchword))
    for label, watchword in watchwords:
        if not watchword.reference.strip():
            continue
        text = (watchword.translations.get(DEFAULT_ENGLISH_VERSION) or "").strip()
        if not text:
            missing.append(f"{label} {watchword.reference}")
    if missing:
        raise BibleLookupError(
            "Missing "
            + DEFAULT_ENGLISH_VERSION
            + " text for "
            + ", ".join(missing)
            + "; will retry later"
        )


def _placeholder_raw(day: date) -> RawDailyText:
    from daily_texts.domain.models import Watchword

    empty = Watchword(reference="", text_en="")
    return RawDailyText(
        date=day,
        date_display=day.isoformat(),
        ot=empty,
        nt=empty,
        prayer_en="",
        source_url="",
    )


def _placeholder_localized(day: date) -> LocalizedDailyText:
    empty = LocalizedWatchword(reference="", reference_zh="", text_en="", text_zh="")
    return LocalizedDailyText(
        date=day,
        date_display=day.isoformat(),
        ot=empty,
        nt=empty,
        prayer_en="",
        prayer_zh="",
        source_url="",
    )
