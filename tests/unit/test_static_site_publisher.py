from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path

from daily_texts.domain.models import LocalizedDailyText, LocalizedWatchword
from daily_texts.infrastructure.publishers.static_site import StaticSitePublisher


def _sample(day: date) -> LocalizedDailyText:
    return LocalizedDailyText(
        date=day,
        date_display=day.isoformat(),
        psalm="Psalm 90",
        readings=["Joshua 8:1–29"],
        ot=LocalizedWatchword(
            reference="Jeremiah 9:7",
            reference_zh="耶利米書 9:7",
            text_en="I will refine them.",
            text_zh="我要熬煉他們。",
        ),
        nt=LocalizedWatchword(
            reference="Luke 22:40",
            reference_zh="路加福音 22:40",
            text_en="Pray.",
            text_zh="你們要禱告。",
        ),
        prayer_en="Amen.",
        prayer_zh="阿們。",
        source_url="https://www.moravian.org/the-daily-texts/",
    )


def test_static_site_publisher_writes_day_and_index(tmp_path: Path) -> None:
    publisher = StaticSitePublisher(tmp_path)
    day = date(2026, 8, 1)
    result = asyncio.run(publisher.publish([], _sample(day)))

    assert result.success
    assert result.channel == "static_site"
    day_page = tmp_path / "2026-08-01.html"
    assert day_page.is_file()
    html = day_page.read_text(encoding="utf-8")
    assert "我要熬煉他們。" in html
    assert "經文選讀" in html

    index = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "2026-08-01.html" in index
    assert "每日經文" in index


def test_static_site_publisher_index_lists_newest_first(tmp_path: Path) -> None:
    publisher = StaticSitePublisher(tmp_path)
    asyncio.run(publisher.publish([], _sample(date(2026, 7, 31))))
    asyncio.run(publisher.publish([], _sample(date(2026, 8, 1))))

    index = (tmp_path / "index.html").read_text(encoding="utf-8")
    pos_aug = index.index("2026-08-01.html")
    pos_jul = index.index("2026-07-31.html")
    assert pos_aug < pos_jul
    assert 'class="latest"' in index
    assert index.index("最新") < pos_aug


def test_static_site_publisher_overwrites_same_day(tmp_path: Path) -> None:
    publisher = StaticSitePublisher(tmp_path)
    day = date(2026, 8, 1)
    asyncio.run(publisher.publish([], _sample(day)))
    first = (tmp_path / "2026-08-01.html").read_text(encoding="utf-8")

    updated = _sample(day)
    updated.ot.text_zh = "更新後的舊約。"
    asyncio.run(publisher.publish([], updated))
    second = (tmp_path / "2026-08-01.html").read_text(encoding="utf-8")

    assert "更新後的舊約。" in second
    assert second != first
    # Still a single day page
    day_pages = list(tmp_path.glob("????-??-??.html"))
    assert len(day_pages) == 1
