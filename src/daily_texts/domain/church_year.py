from __future__ import annotations

import re

# German Losungen Sunday names → the Chinese label shown after the date.
# Numbered Sundays after Trinity are one behind the "after Pentecost" count
# used on the older English pages (19. Sonntag nach Trinitatis = 聖靈降臨後第二十個主日).
_NAMED_DAYS = {
    "erntedankfest": "收穫感恩節",
    "reformationstag": "宗教改革紀念日",
    "drittletzter sonntag des kirchenjahres": "教會年倒數第三主日",
    "vorletzter sonntag des kirchenjahres": "教會年倒數第二主日",
    "letzter sonntag des kirchenjahres - ewigkeitssonntag": "教會年最後主日（永生主日）",
    "buss- und bettag": "懺悔祈禱日",
    "heiliger abend": "聖誕夜",
    "weihnachtsfest": "聖誕節",
    "2. weihnachtstag": "聖誕節次日",
    "altjahresabend": "除夕",
}

_TRINITY = re.compile(r"^(\d+)\. sonntag nach trinitatis$")
_ADVENT = re.compile(r"^(\d+)\. sonntag im advent$")
_AFTER_CHRISTMAS = re.compile(r"^(\d+)\. sonntag nach weihnachten$")

_NAMED_DAYS_EN = {
    "erntedankfest": "Harvest Thanksgiving",
    "reformationstag": "Reformation Day",
    "drittletzter sonntag des kirchenjahres": "Third Last Sunday of the Church Year",
    "vorletzter sonntag des kirchenjahres": "Second Last Sunday of the Church Year",
    "letzter sonntag des kirchenjahres - ewigkeitssonntag": (
        "Last Sunday of the Church Year (Eternity Sunday)"
    ),
    "buss- und bettag": "Day of Repentance and Prayer",
    "heiliger abend": "Christmas Eve",
    "weihnachtsfest": "Christmas Day",
    "2. weihnachtstag": "Second Day of Christmas",
    "altjahresabend": "New Year's Eve",
}

_EN_ORDINALS = (
    "",
    "First",
    "Second",
    "Third",
    "Fourth",
    "Fifth",
    "Sixth",
    "Seventh",
    "Eighth",
    "Ninth",
    "Tenth",
    "Eleventh",
    "Twelfth",
    "Thirteenth",
    "Fourteenth",
    "Fifteenth",
    "Sixteenth",
    "Seventeenth",
    "Eighteenth",
    "Nineteenth",
)


def church_day_label_zh(church_day: str) -> str:
    """Chinese church-year name for a German Losungen ``church_day`` value."""
    cleaned = _normalize(church_day)
    if not cleaned:
        return ""

    named = _NAMED_DAYS.get(cleaned)
    if named:
        return named

    trinity = _TRINITY.match(cleaned)
    if trinity:
        return f"聖靈降臨後第{_ordinal(int(trinity.group(1)) + 1)}個主日"

    advent = _ADVENT.match(cleaned)
    if advent:
        return f"將臨期第{_ordinal(int(advent.group(1)))}主日"

    after_christmas = _AFTER_CHRISTMAS.match(cleaned)
    if after_christmas:
        return f"聖誕後第{_ordinal(int(after_christmas.group(1)))}主日"

    return church_day.strip()


def church_day_label_en(church_day: str) -> str:
    """English church-year name for a German Losungen ``church_day`` value.

    Numbered Sundays after Trinity use the same Pentecost count as the Chinese
    label (19. Sonntag nach Trinitatis = Twentieth Sunday after Pentecost).
    """
    cleaned = _normalize(church_day)
    if not cleaned:
        return ""

    named = _NAMED_DAYS_EN.get(cleaned)
    if named:
        return named

    trinity = _TRINITY.match(cleaned)
    if trinity:
        return f"{_en_ordinal(int(trinity.group(1)) + 1)} Sunday after Pentecost"

    advent = _ADVENT.match(cleaned)
    if advent:
        return f"{_en_ordinal(int(advent.group(1)))} Sunday of Advent"

    after_christmas = _AFTER_CHRISTMAS.match(cleaned)
    if after_christmas:
        return f"{_en_ordinal(int(after_christmas.group(1)))} Sunday after Christmas"

    return church_day.strip()


def _en_ordinal(number: int) -> str:
    if 0 < number < len(_EN_ORDINALS):
        return _EN_ORDINALS[number]
    tens, ones = divmod(number, 10)
    stems = {2: "Twenty", 3: "Thirty"}
    stem = stems.get(tens, str(number))
    if ones == 0:
        return stem + "ieth"
    return f"{stem}-{_EN_ORDINALS[ones].lower()}"


def _normalize(value: str) -> str:
    text = value.strip().lower()
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"\s+", " ", text)
    return text


def _ordinal(number: int) -> str:
    digits = "零一二三四五六七八九"
    if number <= 0:
        return str(number)
    if number < 10:
        return digits[number]
    if number == 10:
        return "十"
    if number < 20:
        return "十" + digits[number - 10]
    tens, ones = divmod(number, 10)
    head = digits[tens] + "十"
    return head if ones == 0 else head + digits[ones]
