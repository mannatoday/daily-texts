from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone

import httpx
from bs4 import BeautifulSoup, Tag

from daily_texts.domain.exceptions import ProviderError
from daily_texts.domain.models import RawDailyText, Watchword
from daily_texts.infrastructure.config import Settings
from daily_texts.infrastructure.http import request_with_retries

logger = logging.getLogger(__name__)

_DATE_PATTERN = re.compile(
    r"(?P<weekday>[A-Za-z]+),\s*(?P<month>[A-Za-z]+)\s*(?P<day>\d{1,2}),\s*(?P<year>\d{4})"
)
_READING_LINE = re.compile(r"^(?P<label>.+?)\s*—\s*(?P<rest>.+)$", re.DOTALL)
# "Watchword for the week — <verse text> <Book C:V>"
_WEEK_WATCHWORD = re.compile(
    r"^watchword for the week\s*[—–-]\s*(?P<text>.+?)\s+"
    r"(?P<ref>\d?\s?[A-Za-z]+(?:\s+(?:of\s+)?[A-Za-z]+)?\s+\d+(?::\d+(?:[-–,]\d+)*)?)"
    r"\s*\.?\s*$",
    re.IGNORECASE | re.DOTALL,
)
# Psalm 90 | Psalm 91:1–8 | Psalm 91:1–92:5 (rare cross-chapter)
_PSALM_REF = re.compile(
    r"(Psalm\s+\d+(?::\d+(?:[–-](?:\d+:\d+|\d+))?)?)",
    re.IGNORECASE,
)


def parse_moravian_sidebar_html(
    html: str,
    *,
    source_url: str,
    target_date: date | None = None,
) -> RawDailyText:
    soup = BeautifulSoup(html, "html.parser")
    widget = soup.select_one("#text-2 .textwidget")
    if widget is None:
        widget = soup.select_one("aside#sidebar .widget_text .textwidget")
    if widget is None:
        raise ProviderError("Daily Text sidebar widget not found in HTML")

    # Date is often a direct child of .textwidget; watchwords live in an inner <div>.
    # Sunday layouts insert church-year / "Watchword for the week" before OT/NT, so
    # locate OT/NT by BibleGateway links instead of fixed paragraph indexes.
    paragraphs = [p for p in widget.find_all("p") if _is_content_paragraph(p)]
    if len(paragraphs) < 4:
        raise ProviderError(f"Expected at least 4 content paragraphs, found {len(paragraphs)}")

    date_display = _extract_date_display(paragraphs[0])
    parsed_date = _parse_date(date_display)
    if target_date is not None and parsed_date != target_date:
        raise ProviderError(
            f"Fetched date {parsed_date} does not match target date {target_date}"
        )

    linked = [p for p in paragraphs[1:] if _biblegateway_link(p) is not None]
    if len(linked) < 2:
        raise ProviderError(
            f"Expected at least 2 BibleGateway watchword links, found {len(linked)}"
        )

    ot_para, nt_para = linked[0], linked[1]
    ot_index = paragraphs.index(ot_para)
    nt_index = paragraphs.index(nt_para)
    if nt_index != ot_index + 1:
        raise ProviderError("OT/NT watchword paragraphs are not consecutive")
    if nt_index + 1 >= len(paragraphs):
        raise ProviderError("Missing prayer paragraph after New Testament watchword")

    preamble = paragraphs[1:ot_index]
    psalm, readings, metadata = _parse_preamble_paragraphs(preamble)
    ot = _parse_watchword_paragraph(ot_para)
    nt = _parse_watchword_paragraph(nt_para)
    prayer_en = _extract_prayer(paragraphs[nt_index + 1])
    week_watchword = _parse_week_watchword(metadata.get("watchword_for_week"))

    return RawDailyText(
        date=parsed_date,
        date_display=date_display,
        psalm=psalm,
        readings=readings,
        ot=ot,
        nt=nt,
        week_watchword=week_watchword,
        prayer_en=prayer_en,
        source_url=source_url,
        fetched_at=datetime.now(timezone.utc),
        metadata=metadata,
    )


def _parse_week_watchword(raw: str | None) -> Watchword | None:
    if not raw:
        return None
    match = _WEEK_WATCHWORD.match(raw.strip())
    if not match:
        logger.warning("Could not parse weekly watchword from: %r", raw)
        return None
    text = re.sub(r"\s+", " ", match.group("text")).strip()
    reference = re.sub(r"\s+", " ", match.group("ref")).strip()
    return Watchword(reference=reference, text_en=text)


def _is_content_paragraph(tag: Tag) -> bool:
    text = tag.get_text(" ", strip=True)
    if not text:
        return False
    lowered = text.lower()
    if lowered.startswith("buy ") or lowered.startswith("subscribe"):
        return False
    return True


def _extract_date_display(paragraph: Tag) -> str:
    strong = paragraph.find("strong")
    if strong and strong.get_text(strip=True):
        return strong.get_text(strip=True)
    text = paragraph.get_text(" ", strip=True)
    if not text:
        raise ProviderError("Missing date display in sidebar widget")
    return text


def _parse_date(date_display: str) -> date:
    match = _DATE_PATTERN.search(date_display)
    if not match:
        raise ProviderError(f"Unable to parse date from: {date_display!r}")
    month_day = f"{match.group('month')} {match.group('day')} {match.group('year')}"
    return datetime.strptime(month_day, "%B %d %Y").date()


def _parse_preamble_paragraphs(
    paragraphs: list[Tag],
) -> tuple[str | None, list[str], dict[str, str]]:
    """Parse optional church-year / weekly watchword / daily readings blocks."""
    if not paragraphs:
        return None, [], {}
    if len(paragraphs) == 1:
        return _parse_readings_block(paragraphs[0])

    metadata: dict[str, str] = {}
    psalm: str | None = None
    readings: list[str] = []
    for paragraph in paragraphs:
        text = paragraph.get_text(" ", strip=True)
        if "watchword for the week" in text.lower():
            metadata["watchword_for_week"] = text
            continue

        block_psalm, block_readings, block_meta = _parse_readings_block(paragraph)
        looks_like_readings = bool(block_psalm or block_readings) or (
            "—" in paragraph.get_text() and bool(block_meta.get("day_label"))
        )
        if looks_like_readings:
            if block_psalm and not psalm:
                psalm = block_psalm
            readings.extend(block_readings)
            for key, value in block_meta.items():
                if key == "day_label" or key not in metadata:
                    metadata[key] = value
            continue

        label = block_meta.get("day_label") or text
        metadata.setdefault("church_year_label", label)

    return psalm, readings, metadata


def _parse_readings_block(paragraph: Tag) -> tuple[str | None, list[str], dict[str, str]]:
    metadata: dict[str, str] = {}
    text = paragraph.get_text("\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None, [], metadata

    # BeautifulSoup may split "<strong>Day</strong> — Psalm N" across lines.
    lines = _merge_dash_continuations(lines)

    first_line = lines[0]
    psalm: str | None = None
    readings: list[str] = []
    remaining = lines[1:]

    match = _READING_LINE.match(first_line)
    if match and (
        "psalm" in match.group("rest").lower() or re.search(r"\d+:\d+", match.group("rest"))
    ):
        metadata["day_label"] = match.group("label")
        psalm, inline_readings = _extract_psalm_and_inline_readings(match.group("rest"))
        readings.extend(inline_readings)
    elif "watchword for the week" in first_line.lower():
        metadata["watchword_for_week"] = first_line
        if remaining:
            second = remaining[0]
            label_match = _READING_LINE.match(second)
            if label_match:
                metadata["day_label"] = label_match.group("label")
                psalm, inline = _extract_psalm_and_inline_readings(label_match.group("rest"))
                readings.extend(inline)
                remaining = remaining[1:]
            else:
                metadata["church_year_label"] = second
                remaining = remaining[1:]
    else:
        if remaining and _READING_LINE.match(remaining[0]):
            metadata["church_year_label"] = first_line
            label_match = _READING_LINE.match(remaining[0])
            assert label_match is not None
            metadata["day_label"] = label_match.group("label")
            psalm, inline = _extract_psalm_and_inline_readings(label_match.group("rest"))
            readings.extend(inline)
            remaining = remaining[1:]
        else:
            metadata["day_label"] = first_line

    for line in remaining:
        if "—" in line and "psalm" in line.lower() and _READING_LINE.match(line):
            continue
        parts = [part.strip() for part in re.split(r"[;]", line) if part.strip()]
        readings.extend(parts)

    return psalm, readings, metadata


def _extract_psalm_and_inline_readings(rest: str) -> tuple[str | None, list[str]]:
    psalm_match = _PSALM_REF.search(rest)
    if not psalm_match:
        return None, [part.strip() for part in rest.split(";") if part.strip()]

    psalm = psalm_match.group(1)
    after = rest[psalm_match.end() :]
    # Keep verse lists like ",14-21" attached to the psalm reference.
    extra = re.match(r"(?:,\d+(?:[–-]\d+)*)+", after)
    if extra:
        psalm += extra.group(0)
        after = after[extra.end() :]

    before = rest[: psalm_match.start()].strip("; ").strip()
    after = after.lstrip("; ").strip()
    inline: list[str] = []
    if before:
        inline.extend(part.strip() for part in before.split(";") if part.strip())
    if after:
        inline.extend(part.strip() for part in after.split(";") if part.strip())
    return psalm, inline


def _merge_dash_continuations(lines: list[str]) -> list[str]:
    merged: list[str] = []
    for line in lines:
        if merged and (line.startswith("—") or line.startswith("–") or line.startswith("- ")):
            merged[-1] = f"{merged[-1]} {line}"
        else:
            merged.append(line)
    return merged


def _biblegateway_link(paragraph: Tag) -> Tag | None:
    for link in paragraph.find_all("a", href=True):
        href = str(link["href"])
        if "biblegateway.com" in href.lower():
            return link
    return None


def _parse_watchword_paragraph(paragraph: Tag) -> Watchword:
    link = _biblegateway_link(paragraph)
    if link is None:
        raise ProviderError("Watchword paragraph missing BibleGateway link")

    reference = link.get_text(" ", strip=True)
    bible_url = str(link["href"])
    full_text = paragraph.get_text(" ", strip=True)
    text_en = full_text.replace(reference, "", 1).strip()
    text_en = re.sub(r"\s+", " ", text_en)

    return Watchword(reference=reference, text_en=text_en, bible_url=bible_url)


def _extract_prayer(paragraph: Tag) -> str:
    prayer = paragraph.get_text(" ", strip=True)
    if not prayer:
        raise ProviderError("Missing prayer paragraph")
    return prayer


class MoravianHtmlSidebarProvider:
    source_name = "moravian_html"

    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    async def fetch(self, target_date: date | None = None) -> RawDailyText:
        try:
            response = await request_with_retries(
                self._client,
                "GET",
                self._settings.moravian_url,
                max_retries=self._settings.http_max_retries,
                backoff_seconds=self._settings.http_retry_backoff_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Failed to fetch Moravian page: {exc}") from exc

        return parse_moravian_sidebar_html(
            response.text,
            source_url=self._settings.moravian_url,
            target_date=target_date,
        )
