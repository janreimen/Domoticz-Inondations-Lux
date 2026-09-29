"""
Small stateless helpers, kept free of any Domoticz import so they're
trivially unit-testable on their own.
"""

from typing import List, Optional, Set


def safe_float(value, ndigits: int = 2) -> Optional[float]:
    """Best-effort float conversion, rounded.

    Returns None on failure or for a blank string, rather than raising -
    a single malformed or missing reading should not take down the
    whole poll cycle.
    """
    if value is None:
        return None
    value = value.strip() if isinstance(value, str) else value
    if value == "":
        return None
    try:
        return round(float(value), ndigits)
    except (TypeError, ValueError):
        return None


def last_non_empty(values: List[str]) -> Optional[str]:
    """The last non-blank entry in a list of raw CSV cell strings, or
    None if every cell is blank.

    The source CSV pads every row out to the same width, but a station
    that stopped reporting recently trails off with several empty
    cells before the row ends - the true "current" reading is the last
    one actually present, not literally the last column.
    """
    for value in reversed(values):
        if value is not None and value.strip() != "":
            return value
    return None


def parse_name_filter(raw: str) -> Optional[Set[str]]:
    """Turn the plugin's 'station name filter' parameter into a set of
    lowercase substrings, or None to mean 'no filter, include every
    station'. A station matches if any filter term is a substring of
    its name (case-insensitive) - there's no river field in the raw
    CSV to filter on, only the station's own name.
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def name_matches_filter(name: str, name_filter: Optional[Set[str]]) -> bool:
    if name_filter is None:
        return True
    lowered = name.lower()
    return any(term in lowered for term in name_filter)
