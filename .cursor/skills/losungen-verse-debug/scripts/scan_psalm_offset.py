#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Flag Psalm watchwords whose German (Losungen) verse number is one higher
than the Chinese / English number.

The Losungen number the Psalms the Hebrew way: a psalm's superscription is its
own verse 1. For those psalms the German verse count is exactly one higher than
the Chinese / English count, and every verse is shifted by +1. build_days.py
copies the German number unchanged, so the reference points one verse too high:
blank when it falls past the chapter end, the wrong verse otherwise.

Proxy (both from bolls.life): Menge (MB) counts the superscription separately,
like the Losungen; 和合本 (CUV) does not, like the versions the site serves.
offset = MB_count - CUV_count, which is 0 or 1. The corrected verse is the
German verse minus the offset.

Usage:
    python scan_psalm_offset.py LOSUNGEN.csv [--days DAYS.csv]

LOSUNGEN.csv is the year's "Losungen Free" export (cp1252, semicolon, columns
Datum; Wtag; Sonntag; Losungsvers; Losungstext; Lehrtextvers; Lehrtext).
--days, if given, adds the reference currently stored for that date.
"""
import argparse
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

CACHE = Path("/tmp/psalm_scan_cache")
_PSALM = re.compile(r"^Psalm\s+(?P<chap>\d+)[, ](?P<rest>\d.*)$")


def bolls(version: str, chap: int) -> list[dict]:
    CACHE.mkdir(exist_ok=True)
    cached = CACHE / f"{version}_{chap}.json"
    if not cached.exists():
        url = f"https://bolls.life/get-text/{version}/19/{chap}/"
        out = subprocess.run(
            ["curl", "-s", "--max-time", "30", url],
            capture_output=True, text=True, timeout=40,
        ).stdout
        cached.write_text(out, encoding="utf-8")
    return json.loads(cached.read_text(encoding="utf-8"))


def verse_numbers(spec: str) -> list[int]:
    nums = []
    for part in spec.replace(".", ",").split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            nums.extend(range(int(a), int(b) + 1))
        elif part:
            nums.append(int(part))
    return nums


def parse_psalm(field: str):
    match = _PSALM.match(field.strip())
    if not match:
        return None
    return int(match.group("chap")), verse_numbers(match.group("rest"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("losungen", type=Path)
    ap.add_argument("--days", type=Path, default=None)
    args = ap.parse_args()

    stored: dict[str, tuple[str, str]] = {}
    if args.days and args.days.exists():
        with args.days.open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                stored[row["date"]] = (row.get("ot_ref", ""), row.get("nt_ref", ""))

    rows = []
    chapters: set[int] = set()
    for line in args.losungen.read_text(encoding="cp1252").splitlines()[1:]:
        if not line.strip():
            continue
        fields = line.split(";")
        dd, mm, yy = fields[0].split(".")
        iso = f"{yy}-{mm}-{dd}"
        for side, idx in (("OT", 3), ("NT", 5)):
            parsed = parse_psalm(fields[idx] if len(fields) > idx else "")
            if not parsed:
                continue
            chap, verses = parsed
            chapters.add(chap)
            rows.append((iso, side, chap, verses))

    offset: dict[int, int] = {}
    odd = []
    for chap in sorted(chapters):
        diff = len(bolls("MB", chap)) - len(bolls("CUV", chap))
        offset[chap] = diff
        if diff not in (0, 1):
            odd.append((chap, diff))

    print(f"psalm chapters: {len(chapters)}  "
          f"offset 1: {sum(v == 1 for v in offset.values())}  "
          f"offset 0: {sum(v == 0 for v in offset.values())}  "
          f"other: {odd or 'none'}")

    flagged = 0
    for iso, side, chap, verses in rows:
        off = offset[chap]
        if off == 0:
            continue
        corrected = [v - off for v in verses]
        cuv_len = len(bolls("CUV", chap))
        blank = "  BLANK" if max(verses) > cuv_len else ""
        current = stored.get(iso)
        note = ""
        if current:
            got = current[0] if side == "OT" else current[1]
            fixed = f"Psalm {chap}:" + ",".join(str(v) for v in corrected)
            note = "  stored:" + got + ("  OK" if got.replace("-", ",") == fixed.replace("-", ",") else "  NEEDS FIX")
        german = ",".join(str(v) for v in verses)
        right = ",".join(str(v) for v in corrected)
        print(f"{iso} {side}  Psalm {chap}:{german} -> {chap}:{right}{blank}{note}")
        flagged += 1
    print(f"\n{flagged} reference(s) shifted by +1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
