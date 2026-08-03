from __future__ import annotations

# Site-facing version codes (URL ?version=, picker values, JSON keys).
DEFAULT_VERSION = "RCUV"

# (site_code, Chinese label)
SITE_VERSIONS: list[tuple[str, str]] = [
    ("CUV", "和合本"),
    ("RCUV", "和合本修訂版"),
    ("CNVT", "新譯本"),
    ("CCBT", "當代譯本"),
    ("CSBT", "中文標準譯本"),
]

SITE_VERSION_LABELS: dict[str, str] = dict(SITE_VERSIONS)

# Site code → FHL qb.php version parameter (None = not available via FHL).
FHL_VERSION_CODES: dict[str, str | None] = {
    "CUV": "unv",
    "RCUV": "rcuv",
    "CNVT": "ncv",
    "CCBT": None,  # not on FHL; on-page text falls back to English
    "CSBT": "csb",
}

# Site code → Bible Gateway version query parameter.
GATEWAY_VERSION_CODES: dict[str, str] = {
    "CUV": "CUV",
    "RCUV": "RCU17TS",
    "CNVT": "CNVT",
    "CCBT": "CCBT",
    "CSBT": "CSBT",
}


def gateway_version(site_code: str) -> str:
    return GATEWAY_VERSION_CODES.get(site_code, GATEWAY_VERSION_CODES[DEFAULT_VERSION])


def fhl_version(site_code: str) -> str | None:
    return FHL_VERSION_CODES.get(site_code)
