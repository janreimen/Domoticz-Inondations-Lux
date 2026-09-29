"""
Turns raw source data into a flat list of Station objects, kept free
of any Domoticz import so it's testable on its own (see tests.py).

Two independent parsers share one Station model, so devices.py and
plugin.py never care which data source is active:

parse_csv  - the official Water-Levels-LocalTime.csv (default source).
    One row per station:
        "Name","Number","Unit",<timestamp 1>,...,<timestamp N>
    "Number" is unused (blank on every row observed). "Unit" is "cm"
    for most gauges but "m" for at least one (Esch-Sure, a reservoir
    level), so the unit is read per station rather than assumed.

parse_api  - the heichwaasser.lu JSON reuse (alternative source):
    a list of rivers, each with nested stations. Device names are
    built as "<River> - <City>" (plus " (<supplement>)" if present).
"""

import csv
import io
from dataclasses import dataclass
from typing import List, Optional, Set

from rivers import RiverIndex
from utils import last_non_empty, name_matches_filter, safe_float

DEFAULT_UNIT_LABEL = "cm"


@dataclass
class Station:
    name: str  # identity: exactly as the source names it (registry key)
    unit_label: str
    current_value: Optional[float]
    river: Optional[str] = None  # display only, see apply_rivers()
    locality: Optional[str] = None

    @property
    def display_name(self) -> str:
        if self.river and self.locality:
            return f"{self.river} - {self.locality}"
        return self.name


def parse_csv(raw_text: str) -> List[Station]:
    # Strip a UTF-8 BOM if one survived decoding, so the first header
    # cell reads "Name" rather than "\ufeffName".
    if raw_text.startswith("\ufeff"):
        raw_text = raw_text[1:]

    rows = iter(csv.reader(io.StringIO(raw_text)))
    try:
        next(rows)  # header row - not needed further
    except StopIteration:
        return []

    stations: List[Station] = []
    for row in rows:
        if len(row) < 3:
            continue  # blank/malformed line: skip rather than fail the whole poll

        name = row[0].strip()
        if not name:
            continue

        unit_label = row[2].strip() or DEFAULT_UNIT_LABEL
        # A station that stopped reporting recently trails off with blank
        # cells, so "current" is the last non-blank cell, not the last column.
        current_value = safe_float(last_non_empty(row[3:]))

        stations.append(Station(name=name, unit_label=unit_label, current_value=current_value))

    return stations


def parse_api(payload: list) -> List[Station]:
    if not isinstance(payload, list):
        return []

    stations: List[Station] = []
    for river in payload:
        if not isinstance(river, dict):
            continue
        river_name = (river.get("name") or "").strip()

        for raw in river.get("stations") or []:
            if not isinstance(raw, dict):
                continue

            city = (raw.get("city") or "Unknown").strip()
            name = f"{river_name} - {city}"
            supplement = raw.get("supplement")
            if supplement:
                name += f" ({supplement})"

            current = raw.get("current") or {}
            unit_label = (current.get("unit") or "").strip() or DEFAULT_UNIT_LABEL

            stations.append(
                Station(name=name, unit_label=unit_label, current_value=safe_float(current.get("value")))
            )

    return stations


def apply_rivers(stations: List[Station], index: RiverIndex) -> List[str]:
    """Fill in river/locality (display only) for stations the table knows.
    Returns the feed names it could not resolve, which keep their feed name.
    """
    unresolved: List[str] = []
    for station in stations:
        resolved = index.resolve(station.name)
        if resolved is None:
            unresolved.append(station.name)
        else:
            station.river, station.locality = resolved
    return unresolved


def filter_stations(stations: List[Station], name_filter: Optional[Set[str]]) -> List[Station]:
    """A station matches if the filter hits its feed name or its display
    name, so both "Alzette" and "Ettelbrück" work in either naming mode."""
    if name_filter is None:
        return stations
    return [
        s for s in stations
        if name_matches_filter(s.name, name_filter) or name_matches_filter(s.display_name, name_filter)
    ]
