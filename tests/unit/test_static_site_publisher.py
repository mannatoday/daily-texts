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
    assert (tmp_path / "styles.css").is_file()
    day_page = tmp_path / "2026-08-01.html"
    assert day_page.is_file()
    html = day_page.read_text(encoding="utf-8")
    assert "我要熬煉他們。" in html
    assert "經文選讀" in html
    assert 'href="styles.css"' in html
    assert "day-nav" in html
    assert "index.html" in html
    assert "原文連結" not in html
    assert "Moravian Daily Texts</a>" not in html

    index = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "2026-08-01.html" in index
    assert "摩拉維亞每日經文" in index
    assert "Moravian Daily Texts • 中文版" in index
    assert "以神的話開始每一天" in index
    brand_idx = index.index("摩拉維亞每日經文")
    subtitle_idx = index.index("Moravian Daily Texts • 中文版")
    lede_idx = index.index("以神的話開始每一天")
    assert brand_idx < subtitle_idx < lede_idx
    assert 'href="styles.css"' in index
    assert (tmp_path / "version.js").is_file()
    assert (tmp_path / "archive.html").is_file()
    assert 'id="bible-version"' in html
    assert "version.js" in html
    assert 'id="day-data"' in html
    assert 'data-verse="ot"' in html
    assert "[閱讀 ·" not in html
    assert "[閱讀]" in html
    assert 'data-ref=' in html
    assert ">首頁</a>" in html
    assert "archive.html" in html
    js = (tmp_path / "version.js").read_text(encoding="utf-8")
    assert "localStorage" in js
    assert "data-verse" in js
    assert "URLSearchParams" in js
    assert "reading__open" in js
    assert "CCBT" not in js
    assert (tmp_path / "about.html").is_file()
    about = (tmp_path / "about.html").read_text(encoding="utf-8")
    assert "1731" in about
    assert "非官方出版物" in about
    assert "losungen.de" in about
    assert "herrnhuter.de" in about
    assert "了解更多" in html
    assert "about.html" in html
    assert "跳至內容" in html
    assert "首頁" in html
    assert "歷日檔案" in html
    assert "today-card" in index or "今日經文" in index
    assert 'href="today.html"' in index
    assert "最近三天" in index
    assert 'href="archive.html"' in index
    assert "了解更多" not in index
    assert "losungen.de" in html
    assert "Herrnhuter Brüdergemeine" in html
    assert (tmp_path / "today.html").is_file()
    today = (tmp_path / "today.html").read_text(encoding="utf-8")
    assert "America/Los_Angeles" in today
    assert "location.replace" in today
    assert "losungen.de" in today

    archive = (tmp_path / "archive.html").read_text(encoding="utf-8")
    assert "歷日檔案" in archive
    assert "2026-08-01.html" in archive
    assert "首頁" in archive
    assert "losungen.de" in archive
    assert "today.html" in archive


def test_static_site_publisher_prev_next_navigation(tmp_path: Path) -> None:
    publisher = StaticSitePublisher(tmp_path)
    asyncio.run(publisher.publish([], _sample(date(2026, 7, 31))))
    asyncio.run(publisher.publish([], _sample(date(2026, 8, 1))))

    aug = (tmp_path / "2026-08-01.html").read_text(encoding="utf-8")
    jul = (tmp_path / "2026-07-31.html").read_text(encoding="utf-8")
    assert 'href="2026-07-31.html"' in aug
    assert 'href="2026-08-01.html"' in jul


def test_static_site_publisher_index_lists_newest_first(tmp_path: Path) -> None:
    publisher = StaticSitePublisher(tmp_path)
    asyncio.run(publisher.publish([], _sample(date(2026, 7, 31))))
    asyncio.run(publisher.publish([], _sample(date(2026, 8, 1))))

    index = (tmp_path / "index.html").read_text(encoding="utf-8")
    pos_aug = index.index("2026-08-01.html")
    pos_jul = index.index("2026-07-31.html")
    assert pos_aug < pos_jul
    assert "今日經文" in index
    assert "最近三天" in index
    assert 'class="today-card"' in index
    assert 'href="archive.html"' in index
    # Index only lists up to 3 recent days in the main list section title
    assert index.count("2026-08-01.html") >= 1
    assert index.count("2026-07-31.html") >= 1
    archive = (tmp_path / "archive.html").read_text(encoding="utf-8")
    assert "2026-08-01.html" in archive
    assert "2026-07-31.html" in archive


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
