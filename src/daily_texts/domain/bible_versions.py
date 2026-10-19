from __future__ import annotations

# Site-facing version codes (URL ?version=, picker values, JSON keys).
DEFAULT_VERSION = "RCUV"
DEFAULT_ENGLISH_VERSION = "NIV"

# (site_code, label shown in the picker)
SITE_VERSIONS: list[tuple[str, str]] = [
    ("CUV", "和合本"),
    ("RCUV", "和合本修訂版"),
    ("CNVT", "新譯本"),
    ("CSBT", "中文標準譯本"),
    ("WCB", "環球聖經譯本"),
]

# ESV stays out of this list until an ESV API key is available.
ENGLISH_VERSIONS: list[tuple[str, str]] = [
    ("NIV", "NIV"),
    ("NLT", "NLT"),
    ("NIRV", "NIrV"),
    ("KJV", "KJV"),
]

SITE_VERSION_LABELS: dict[str, str] = dict(SITE_VERSIONS)
ENGLISH_VERSION_LABELS: dict[str, str] = dict(ENGLISH_VERSIONS)

# Site code → FHL qb.php version parameter.
FHL_VERSION_CODES: dict[str, str | None] = {
    "CUV": "unv",
    "RCUV": "rcuv",
    "CNVT": "ncv",
    "CSBT": "csb",
    "WCB": "wcb",
}

# Site code → lookup version passed to BibleService.lookup.
# Chinese codes use the FHL parameter. English codes name the English source.
ENGLISH_LOOKUP_VERSIONS: dict[str, str] = {
    "KJV": "kjv",
    "NIV": "niv",
    "NLT": "nlt",
    "NIRV": "nirv",
}

# Site code → Bible Gateway version query parameter (for optional external links).
GATEWAY_VERSION_CODES: dict[str, str] = {
    "CUV": "CUV",
    "RCUV": "RCU17TS",
    "CNVT": "CNVT",
    "CSBT": "CSBT",
    "KJV": "KJV",
    "NIV": "NIV",
    "NLT": "NLT",
    "NIRV": "NIRV",
}

# Shown in the footer while that version is selected.
VERSION_NOTICES: dict[str, str] = {
    "WCB": "經文引自《環球聖經譯本》，版權屬於環球聖經公會。",
    "NIV": (
        "Scripture quotations taken from The Holy Bible, New International Version®, "
        "NIV®. Copyright © 1973, 1978, 1984, 2011 by Biblica, Inc.™ "
        "Used by permission. All rights reserved worldwide."
    ),
    "NLT": (
        "Scripture quotations are taken from the Holy Bible, New Living Translation, "
        "copyright © 1996, 2004, 2015 by Tyndale House Foundation. "
        "Used by permission of Tyndale House Publishers, Carol Stream, Illinois 60188. "
        "All rights reserved."
    ),
    "NIRV": (
        "Scripture quotations are taken from the Holy Bible, "
        "New International Reader’s Version®, NIrV®. "
        "Copyright © 1995, 1996, 1998, 2014 by Biblica, Inc.™ "
        "Used by permission. All rights reserved worldwide."
    ),
}


def gateway_version(site_code: str) -> str:
    return GATEWAY_VERSION_CODES.get(site_code, GATEWAY_VERSION_CODES[DEFAULT_VERSION])


def fhl_version(site_code: str) -> str | None:
    return FHL_VERSION_CODES.get(site_code)
