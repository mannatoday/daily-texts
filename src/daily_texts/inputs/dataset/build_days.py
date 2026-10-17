#!/usr/bin/env python3
"""Build the offline "days skeleton" dataset from the German Losungen Free CSV.

Produces one row per day with the two watchword references (Losung/Lehrtext) in
English canonical form, the church-year day label, a weekday/sunday track hint,
and the華語 third-text id when a pairing already exists.

This dataset is meant to let the site stop crawling the English Moravian page for
the two daily *watchword* verses. It deliberately does NOT include:
  - 經文選讀 (lectionary readings): a separate system, still sourced elsewhere.
  - 本週守望經文 / 主日週歌: not in the Free CSV (decided: later).

Reproducible for other years: point LOSUNGEN at that year's file and set YEAR.
"""
from __future__ import annotations

import csv
import re
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LOSUNGEN = REPO / "src/daily_texts/inputs/Losung_2026_CSV/Losungen Free 2026.csv"
PAIRINGS = REPO / "src/daily_texts/inputs/third_text/pairings_2026.csv"

# German book name -> English canonical (matches domain/data/book_names_zh.json keys).
GERMAN_TO_EN = {
    "1. Mose": "Genesis",
    "2. Mose": "Exodus",
    "3. Mose": "Leviticus",
    "4. Mose": "Numbers",
    "5. Mose": "Deuteronomy",
    "Josua": "Joshua",
    "Richter": "Judges",
    "Rut": "Ruth",
    "1. Samuel": "1 Samuel",
    "2. Samuel": "2 Samuel",
    "1. Könige": "1 Kings",
    "2. Könige": "2 Kings",
    "1. Chronik": "1 Chronicles",
    "2. Chronik": "2 Chronicles",
    "Esra": "Ezra",
    "Nehemia": "Nehemiah",
    "Ester": "Esther",
    "Hiob": "Job",
    "Psalm": "Psalm",
    "Sprüche": "Proverbs",
    "Prediger": "Ecclesiastes",
    "Hoheslied": "Song of Songs",
    "Jesaja": "Isaiah",
    "Jeremia": "Jeremiah",
    "Klagelieder": "Lamentations",
    "Hesekiel": "Ezekiel",
    "Daniel": "Daniel",
    "Hosea": "Hosea",
    "Joel": "Joel",
    "Amos": "Amos",
    "Obadja": "Obadiah",
    "Jona": "Jonah",
    "Micha": "Micah",
    "Nahum": "Nahum",
    "Habakuk": "Habakkuk",
    "Zefanja": "Zephaniah",
    "Haggai": "Haggai",
    "Sacharja": "Zechariah",
    "Maleachi": "Malachi",
    "Matthäus": "Matthew",
    "Markus": "Mark",
    "Lukas": "Luke",
    "Johannes": "John",
    "Apostelgeschichte": "Acts",
    "Römer": "Romans",
    "1. Korinther": "1 Corinthians",
    "2. Korinther": "2 Corinthians",
    "Galater": "Galatians",
    "Epheser": "Ephesians",
    "Philipper": "Philippians",
    "Kolosser": "Colossians",
    "1. Thessalonicher": "1 Thessalonians",
    "2. Thessalonicher": "2 Thessalonians",
    "1. Timotheus": "1 Timothy",
    "2. Timotheus": "2 Timothy",
    "Titus": "Titus",
    "Philemon": "Philemon",
    "Hebräer": "Hebrews",
    "Jakobus": "James",
    "1. Petrus": "1 Peter",
    "2. Petrus": "2 Peter",
    "1. Johannes": "1 John",
    "2. Johannes": "2 John",
    "3. Johannes": "3 John",
    "Judas": "Jude",
    "Offenbarung": "Revelation",
}

WEEKDAY_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# A German reference field looks like "<book> <chapter>,<verses>".
_REF_FIELD = re.compile(r"^(?P<book>[1-5]\.\s)?[A-Za-zÄÖÜäöüß]+\s+\d+[\d,.\-–]*$")


def convert_ref(de: str) -> str | None:
    """'2. Petrus 2,9' -> '2 Peter 2:9'; 'Psalm 85,10.11' -> 'Psalm 85:10,11'."""
    de = de.strip()
    m = re.match(r"^(?P<book>(?:[1-5]\.\s)?[A-Za-zÄÖÜäöüß]+)\s+(?P<rest>\d.*)$", de)
    if not m:
        return None
    book = re.sub(r"\s+", " ", m.group("book").strip())
    en = GERMAN_TO_EN.get(book)
    if en is None:
        return None
    rest = m.group("rest").strip().replace("–", "-")
    # chapter,verse -> chapter:verse ; remaining dots (verse separators) -> commas
    if "," in rest:
        chap, verses = rest.split(",", 1)
        verses = verses.replace(".", ",")
        rest = f"{chap}:{verses}"
    return f"{en} {rest}"


def find_nt_ref(fields: list[str]) -> str | None:
    """Scan fields after the OT ref/text for the first that is a reference."""
    for f in fields:
        if _REF_FIELD.match(f.strip()):
            return f.strip()
    return None


def load_pairings() -> dict[str, str]:
    out: dict[str, str] = {}
    if PAIRINGS.exists():
        with PAIRINGS.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if row.get("date") and row.get("third_text_id"):
                    out[row["date"]] = row["third_text_id"]
    return out


def main() -> int:
    year = 2026
    start = date(year, 10, 1)
    end = date(year, 12, 31)
    pairings = load_pairings()

    rows: list[dict[str, str]] = []
    warnings: list[str] = []

    raw = LOSUNGEN.read_text(encoding="cp1252").splitlines()
    by_date: dict[str, list[str]] = {}
    for line in raw[1:]:
        if not line.strip():
            continue
        fields = line.split(";")
        by_date[fields[0]] = fields

    d = start
    while d <= end:
        key = d.strftime("%d.%m.%Y")
        fields = by_date.get(key)
        if fields is None:
            warnings.append(f"{d.isoformat()}: no row in Losungen CSV")
            d += timedelta(days=1)
            continue
        church_day = re.sub(r"\s+", " ", fields[2].strip())
        ot_de = fields[3].strip()
        ot_ref = convert_ref(ot_de)
        nt_de = find_nt_ref(fields[5:]) or ""
        nt_ref = convert_ref(nt_de) if nt_de else None
        if ot_ref is None:
            warnings.append(f"{d.isoformat()}: OT ref unparsed: {ot_de!r}")
        if nt_ref is None:
            warnings.append(f"{d.isoformat()}: NT ref unparsed from {fields[5:]!r}")
        track = "sunday" if church_day else "weekday"
        rows.append(
            {
                "date": d.isoformat(),
                "weekday": WEEKDAY_EN[d.weekday()],
                "track": track,
                "church_day": church_day,
                "ot_ref": ot_ref or f"?? {ot_de}",
                "nt_ref": nt_ref or f"?? {nt_de}",
                "third_text_id": pairings.get(d.isoformat(), ""),
                "plan_year": str(year),
            }
        )
        d += timedelta(days=1)

    out_path = HERE / "days_2026_q4.csv"
    cols = [
        "date",
        "weekday",
        "track",
        "church_day",
        "ot_ref",
        "nt_ref",
        "third_text_id",
        "plan_year",
    ]
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {len(rows)} rows -> {out_path.relative_to(REPO)}")
    print(f"third_text_id filled: {sum(1 for r in rows if r['third_text_id'])}")
    if warnings:
        print(f"\n{len(warnings)} warning(s):")
        for wline in warnings:
            print("  -", wline)
    return 0


if __name__ == "__main__":
    sys.exit(main())
