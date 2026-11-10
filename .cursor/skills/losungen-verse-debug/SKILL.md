---
name: losungen-verse-debug
description: >-
  Diagnose Moravian Daily Texts (Losungen) watchword verses that render blank
  or show the wrong verse. Use when a daily page is missing its Old or New
  Testament verse, a Psalm reference looks off by one, a Chinese Bible version
  returns an empty or single-letter verse, or when building a new year's
  dataset from the German Losungen CSV.
---

# Losungen verse debugging

Two separate causes make a watchword verse render blank or wrong. Tell them
apart before changing anything.

## 1. Psalm versification offset (wrong verse, sometimes blank)

The German Losungen number the Psalms the Hebrew way: a psalm's superscription
is its own verse 1. For every psalm that has a superscription, the German verse
count is exactly one higher than the Chinese and English count, and every verse
is shifted by +1. `build_days.py` (`convert_ref`) copies the German number
unchanged, so the stored reference points one verse too high.

- One past the chapter end (e.g. German `Psalm 31:25`, Chinese has 24) → the
  lookup returns nothing → the verse renders **blank**.
- Anywhere earlier (e.g. German `Psalm 63:4`) → it renders the **next** verse,
  so it looks fine but is the wrong text.

Psalms without a superscription are numbered the same and need no change.

### Detect

```bash
python .cursor/skills/losungen-verse-debug/scripts/scan_psalm_offset.py \
  src/daily_texts/inputs/Losung_2026_CSV/Losungen\ Free\ 2026.csv \
  --days src/daily_texts/inputs/dataset/days_2026_q4.csv
```

It compares verse counts from bolls.life: Menge (MB, counts the superscription,
like the Losungen) minus 和合本 (CUV, does not). The offset is only ever 0 or 1;
anything else is a real anomaly to inspect by hand. The corrected verse is the
German verse minus the offset. `BLANK` marks a reference past the chapter end.

### Confirm before editing

For each flagged date, compare the German `Losungstext` with the Chinese text of
both the stored verse and the corrected verse. The German sentence matches the
corrected verse. The prayer note was written for the correct meaning, so only
the reference number is wrong — update `ot_ref` in the days CSV and the pairing
row, and leave the note.

### Fix the data, not just the code

`fhl_rcuv.lookup` falls back to the previous verse when the requested one is
empty, which rescues only the blank (chapter-end) case and still leaves the
label and the English text on the wrong number. Correct the reference in the
days CSV and the pairings so the label, the Chinese, and the English all agree.
For a new year, run the scan on the new Losungen CSV and correct the references
before publishing.

## 2. Merged verse in one Chinese version (empty or a letter)

新譯本 (ncv) and 環球譯本 (wcb) sometimes fold a verse into the previous one and
return nothing, or a footnote letter such as `a`, for the requested number.
1 John 3:20 is the known case. `fhl_rcuv.lookup` treats an empty string or a
single letter as unusable and returns the previous verse when that one and the
following verse both have text. The logic and its tests live in
`src/daily_texts/infrastructure/bible/fhl_rcuv.py` and
`tests/unit/test_fhl_merged_verse.py`.

## Rebuilding pages

The published site is built from the dataset provider. A local `.env` can
default to `moravian_html`, which reads the live moravian.org page (today's
page, not the dataset) and pulls the wrong readings. Rebuild a corrected date
with the dataset provider, and rebuild the current day last so `today.html`
still points at today:

```bash
PROVIDER=dataset PUBLISHERS=static_site \
  .venv/bin/python -m daily_texts.presentation.cli fetch --date YYYY-MM-DD --force
```
