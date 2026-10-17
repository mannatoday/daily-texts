"""Build the Oct–Dec 2026 lectionary table.

Weekday readings continue the published site (through 2026-10-16): psalm, then
one Old Testament unit, then one New Testament unit. Sunday and church-year
special days use the Revised Common Lectionary complementary track and do not
move those three cursors. Year A runs through Christ the King; Year B starts
on Advent 1.
"""
from __future__ import annotations

import csv
import json
import re
from datetime import date
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_DAYS = _HERE / "days_2026_q4.csv"
_OUT = _HERE / "lectionary_2026_q4.csv"
_SITE = _HERE.parents[3] / "site"

# Complementary track, matching the published Moravian Sundays.
# (psalm, ot, epistle, gospel)
_FESTIVAL: dict[str, tuple[str, str, str, str]] = {
    "2026-10-18": (
        "Psalm 96:1-9, 10-13",
        "Isaiah 45:1-7",
        "1 Thessalonians 1:1-10",
        "Matthew 22:15-22",
    ),
    "2026-10-25": (
        "Psalm 1",
        "Leviticus 19:1-2, 15-18",
        "1 Thessalonians 2:1-8",
        "Matthew 22:34-46",
    ),
    "2026-10-31": (
        "Psalm 46",
        "Jeremiah 31:31-34",
        "Romans 3:19-28",
        "John 8:31-36",
    ),
    "2026-11-01": (
        "Psalm 43",
        "Micah 3:5-12",
        "1 Thessalonians 2:9-13",
        "Matthew 23:1-12",
    ),
    "2026-11-08": (
        "Psalm 70",
        "Amos 5:18-24",
        "1 Thessalonians 4:13-18",
        "Matthew 25:1-13",
    ),
    "2026-11-15": (
        "Psalm 90:1-8, 9-11, 12",
        "Zephaniah 1:7, 12-18",
        "1 Thessalonians 5:1-11",
        "Matthew 25:14-30",
    ),
    "2026-11-18": (
        "Psalm 130",
        "Joel 2:12-13, 18-19",
        "Romans 2:1-11",
        "Luke 15:11-32",
    ),
    "2026-11-22": (
        "Psalm 95:1-7a",
        "Ezekiel 34:11-16, 20-24",
        "Ephesians 1:15-23",
        "Matthew 25:31-46",
    ),
    "2026-11-29": (
        "Psalm 80:1-7, 17-19",
        "Isaiah 64:1-9",
        "1 Corinthians 1:3-9",
        "Mark 13:24-37",
    ),
    "2026-12-06": (
        "Psalm 85:1-2, 8-13",
        "Isaiah 40:1-11",
        "2 Peter 3:8-15a",
        "Mark 1:1-8",
    ),
    "2026-12-13": (
        "Psalm 126",
        "Isaiah 61:1-4, 8-11",
        "1 Thessalonians 5:16-24",
        "John 1:6-8, 19-28",
    ),
    "2026-12-20": (
        "Psalm 89:1-4, 19-26",
        "2 Samuel 7:1-11, 16",
        "Romans 16:25-27",
        "Luke 1:26-38",
    ),
    "2026-12-24": (
        "Psalm 96",
        "Isaiah 9:2-7",
        "Titus 2:11-14",
        "Luke 2:1-14, 15-20",
    ),
    "2026-12-25": (
        "Psalm 98",
        "Isaiah 52:7-10",
        "Hebrews 1:1-4, 5-12",
        "John 1:1-14",
    ),
    "2026-12-26": (
        "Psalm 31:1-5, 15-16",
        "2 Chronicles 24:17-22",
        "Acts 6:8-7:2a, 51-60",
        "Matthew 23:34-39",
    ),
    "2026-12-27": (
        "Psalm 148",
        "Isaiah 61:10-62:3",
        "Galatians 4:4-7",
        "Luke 2:22-40",
    ),
    "2026-12-31": (
        "Psalm 8",
        "Ecclesiastes 3:1-13",
        "Revelation 21:1-6a",
        "Matthew 25:31-46",
    ),
}


def _psalm_queue() -> list[str]:
    chunks = [f"Psalm 119:{start}-{start + 7}" for start in range(25, 177, 8)]
    halves = {
        132: ("1-9", "10-18"),
        135: ("1-11", "12-21"),
        136: ("1-13", "14-26"),
        139: ("1-12", "13-24"),
        140: ("1-7", "8-13"),
        143: ("1-6", "7-12"),
        144: ("1-8", "9-15"),
        145: ("1-11", "12-21"),
        147: ("1-11", "12-20"),
        148: ("1-7", "8-14"),
    }
    for number in range(120, 151):
        if number in halves:
            first, second = halves[number]
            chunks.append(f"Psalm {number}:{first}")
            chunks.append(f"Psalm {number}:{second}")
        else:
            chunks.append(f"Psalm {number}")
    return chunks


def _ot_queue() -> list[str]:
    books = [("2 Samuel", range(8, 25)), ("1 Kings", range(1, 23)), ("2 Kings", range(1, 22))]
    return [f"{name} {chapter}" for name, chapters in books for chapter in chapters]


def _nt_queue() -> list[str]:
    john = [
        "John 7:45-8:11",
        "John 8:12-30",
        "John 8:31-59",
        "John 9:1-41",
        "John 10:1-21",
        "John 10:22-42",
        "John 11:1-27",
        "John 11:28-44",
        "John 11:45-57",
        "John 12:1-19",
        "John 12:20-36",
        "John 12:37-50",
        "John 13:1-30",
        "John 13:31-38",
        "John 14:1-14",
        "John 14:15-31",
        "John 15:1-17",
        "John 15:18-27",
        "John 16:1-15",
        "John 16:16-33",
        "John 17:1-26",
        "John 18:1-27",
        "John 18:28-40",
        "John 19:1-16",
        "John 19:17-37",
        "John 19:38-42",
        "John 20:1-18",
        "John 20:19-31",
        "John 21:1-14",
        "John 21:15-25",
    ]
    acts: list[str] = []
    for chapter in range(1, 29):
        if chapter == 2:
            acts.extend(["Acts 2:1-21", "Acts 2:22-47"])
        elif chapter == 7:
            acts.extend(["Acts 7:1-34", "Acts 7:35-60"])
        else:
            acts.append(f"Acts {chapter}")
    return john + acts


def _from_site(day: date) -> tuple[str, str, str, str] | None:
    path = _SITE / f"{day.isoformat()}.html"
    if not path.exists():
        return None
    match = re.search(r'<script type="application/json" id="day-data">(.*?)</script>', path.read_text(), re.S)
    if not match:
        return None
    readings = json.loads(match.group(1))["readings"]
    refs = [item["reference"] for item in readings]
    if len(refs) == 3:
        return refs[0], refs[1], "", refs[2]
    if len(refs) == 4:
        return refs[0], refs[1], refs[2], refs[3]
    raise SystemExit(f"{day.isoformat()} has {len(refs)} readings")


def main() -> None:
    psalms, ots, nts = _psalm_queue(), _ot_queue(), _nt_queue()
    pi = oi = ni = 0
    rows: list[dict[str, str]] = []
    with _DAYS.open(newline="", encoding="utf-8") as handle:
        days = list(csv.DictReader(handle))
    for day_row in days:
        day = date.fromisoformat(day_row["date"])
        published = _from_site(day) if day <= date(2026, 10, 16) else None
        if published:
            psalm, ot, epistle, gospel = published
            plan = "moravian-2yr"
        elif day_row["track"] == "sunday":
            psalm, ot, epistle, gospel = _FESTIVAL[day.isoformat()]
            plan = "rcl"
        else:
            psalm, ot, gospel = psalms[pi], ots[oi], nts[ni]
            epistle = ""
            plan = "moravian-2yr"
            pi, oi, ni = pi + 1, oi + 1, ni + 1
        rows.append(
            {
                "date": day.isoformat(),
                "track": day_row["track"],
                "psalm": psalm,
                "ot_reading": ot,
                "nt_reading": gospel,
                "epistle": epistle,
                "plan_id": plan,
            }
        )
    if pi > len(psalms) or oi > len(ots) or ni > len(nts):
        raise SystemExit("lectionary cursor ran past the prepared readings")
    with _OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["date", "track", "psalm", "ot_reading", "nt_reading", "epistle", "plan_id"],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows; weekday cursors used psalm {pi}, ot {oi}, nt {ni}")


if __name__ == "__main__":
    main()
