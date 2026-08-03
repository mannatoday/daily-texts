from __future__ import annotations

import json
from datetime import date

from daily_texts.domain.models import LocalizedDailyText, LocalizedWatchword
from daily_texts.infrastructure.formatters.json_formatter import JsonFormatter


def _sample() -> LocalizedDailyText:
    return LocalizedDailyText(
        date=date(2026, 8, 1),
        date_display="Saturday, August 1, 2026",
        psalm="Psalm 91:1–8",
        readings=["Joshua 8:30–9:27", "Luke 12:49–59"],
        ot=LocalizedWatchword(
            reference="Deuteronomy 5:21",
            reference_zh="申命記 5:21",
            text_en="You shall not covet.",
            text_zh="不可貪戀。",
            translations={
                "CUV": "不可貪戀（和合）。",
                "RCUV": "不可貪戀。",
                "CNVT": "不可貪心。",
            },
        ),
        nt=LocalizedWatchword(
            reference="Galatians 5:16,17",
            reference_zh="加拉太書 5:16–17",
            text_en="Live by the Spirit.",
            text_zh="你們要順着聖靈而行。",
            translations={"RCUV": "你們要順着聖靈而行。"},
        ),
        prayer_en="Amen.",
        prayer_zh="阿們。",
        source_url="https://www.moravian.org/the-daily-texts/",
        metadata={
            "translation": {
                "provider": "google",
                "status": "ok",
                "kept_english": False,
                "source_chars": 5,
                "result_chars": 3,
            }
        },
    )


def test_json_formatter_shape() -> None:
    out = JsonFormatter().format(_sample(), include_source_link=True)
    assert out.filename == "daily-text.json"
    assert out.format == "json"
    payload = json.loads(out.content)
    assert payload["date"] == "2026-08-01"
    assert payload["default_version"] == "RCUV"
    assert payload["ot"]["reference"] == "Deuteronomy 5:21"
    assert payload["ot"]["reference_zh"] == "申命記 5:21"
    assert payload["ot"]["translations"]["RCUV"] == "不可貪戀。"
    assert payload["ot"]["translations"]["CUV"] == "不可貪戀（和合）。"
    assert payload["nt"]["reference_zh"] == "加拉太書 5:16–17"
    assert payload["prayer"] == "阿們。"
    assert payload["readings"][0]["reference_zh"] == "詩篇 91:1–8"
    assert payload["source_url"] == "https://www.moravian.org/the-daily-texts/"
    assert payload["translation"]["provider"] == "google"
    assert payload["translation"]["status"] == "ok"


def test_json_formatter_omits_source_when_disabled() -> None:
    out = JsonFormatter().format(_sample(), include_source_link=False)
    payload = json.loads(out.content)
    assert "source_url" not in payload
