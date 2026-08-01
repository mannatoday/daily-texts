from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone

import httpx
from bs4 import BeautifulSoup, Tag

from daily_texts.domain.exceptions import ProviderError
from daily_texts.domain.models import RawDailyText, Watchword
from daily_texts.infrastructure.config import Settings

logger = logging.getLogger(__name__)

_DATE_PATTERN = re.compile(
    r"(?P<weekday>[A-Za-z]+),\s*(?P<month>[A-Za-z]+)\s*(?P<day>\d{1,2}),\s*(?P<year>\d{4})"
)
_READING_LINE = re.compile(r"^(?P<label>.+?)\s*—\s*(?P<rest>.+)$", re.DOTALL)
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
    paragraphs = [p for p in widget.find_all("p") if _is_content_paragraph(p)]
    if len(paragraphs) < 5:
        raise ProviderError(f"Expected at least 5 content paragraphs, found {len(paragraphs)}")

    date_display = _extract_date_display(paragraphs[0])
    parsed_date = _parse_date(date_display)
    if target_date is not None and parsed_date != target_date:
        raise ProviderError(
            f"Fetched date {parsed_date} does not match target date {target_date}"
        )

    psalm, readings, metadata = _parse_readings_block(paragraphs[1])
    ot = _parse_watchword_paragraph(paragraphs[2])
    nt = _parse_watchword_paragraph(paragraphs[3])
    prayer_en = _extract_prayer(paragraphs[4])

    return RawDailyText(
        date=parsed_date,
        date_display=date_display,
        psalm=psalm,
        readings=readings,
        ot=ot,
        nt=nt,
        prayer_en=prayer_en,
        source_url=source_url,
        fetched_at=datetime.now(timezone.utc),
        metadata=metadata,
    )


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
    if match and "psalm" in match.group("rest").lower():
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
                psalm, _ = _extract_psalm_and_inline_readings(label_match.group("rest"))
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
            psalm, _ = _extract_psalm_and_inline_readings(label_match.group("rest"))
            remaining = remaining[1:]
        else:
            metadata["day_label"] = first_line

    for line in remaining:
        if "—" in line and "psalm" in line.lower():
            continue
        parts = [part.strip() for part in re.split(r"[;]", line) if part.strip()]
        readings.extend(parts)

    return psalm, readings, metadata


def _extract_psalm_and_inline_readings(rest: str) -> tuple[str | None, list[str]]:
    psalm_match = _PSALM_REF.search(rest)
    if not psalm_match:
        return None, []
    psalm = psalm_match.group(1)
    after_psalm = rest[psalm_match.end() :].lstrip("; ").strip()
    inline = [part.strip() for part in after_psalm.split(";") if part.strip()]
    return psalm, inline


def _merge_dash_continuations(lines: list[str]) -> list[str]:
    merged: list[str] = []
    for line in lines:
        if merged and (line.startswith("—") or line.startswith("–") or line.startswith("- ")):
            merged[-1] = f"{merged[-1]} {line}"
        else:
            merged.append(line)
    return merged


def _parse_watchword_paragraph(paragraph: Tag) -> Watchword:
    link = paragraph.find("a", href=True)
    if link is None:
        raise ProviderError("Watchword paragraph missing BibleGateway link")

    reference = link.get_text(" ", strip=True)
    bible_url = link["href"]
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
            response = await self._client.get(self._settings.moravian_url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Failed to fetch Moravian page: {exc}") from exc

        return parse_moravian_sidebar_html(
            response.text,
            source_url=self._settings.moravian_url,
            target_date=target_date,
        )
