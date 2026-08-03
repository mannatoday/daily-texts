from __future__ import annotations

# Site-facing version codes (URL ?version=, picker values, JSON keys).
DEFAULT_VERSION = "RCUV"

# (site_code, Chinese label)
SITE_VERSIONS: list[tuple[str, str]] = [
    ("CUV", "和合本"),
    ("RCUV", "和合本修訂版"),
    ("CNVT", "新譯本"),
    ("CSBT", "中文標準譯本"),
]

SITE_VERSION_LABELS: dict[str, str] = dict(SITE_VERSIONS)

# Site code → FHL qb.php version parameter.
FHL_VERSION_CODES: dict[str, str | None] = {
    "CUV": "unv",
    "RCUV": "rcuv",
    "CNVT": "ncv",
    "CSBT": "csb",
}

# Site code → Bible Gateway version query parameter (for optional external links).
GATEWAY_VERSION_CODES: dict[str, str] = {
    "CUV": "CUV",
    "RCUV": "RCU17TS",
    "CNVT": "CNVT",
    "CSBT": "CSBT",
}


def gateway_version(site_code: str) -> str:
    return GATEWAY_VERSION_CODES.get(site_code, GATEWAY_VERSION_CODES[DEFAULT_VERSION])


def fhl_version(site_code: str) -> str | None:
    return FHL_VERSION_CODES.get(site_code)
