#!/usr/bin/env python3
"""
Luxembourg water levels - all stations

Downloads the official Luxembourg AGE water-level dataset and prints
the latest available measurement for every station.

Source:
https://inondations.public.lu/dam-assets/ctie/datas/Water-Levels-LocalTime.csv
"""

from __future__ import annotations

import csv
import io
import sys
from datetime import datetime
from urllib.request import Request, urlopen


URL = (
    "https://inondations.public.lu/"
    "dam-assets/ctie/datas/Water-Levels-LocalTime.csv"
)


def download_csv(url: str) -> str:
    """Download CSV and return it as text."""

    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 water-level-monitor/1.0",
            "Accept": "text/csv,*/*",
        },
    )

    with urlopen(request, timeout=30) as response:
        data = response.read()

    # UTF-8 with BOM is possible with government CSV exports.
    return data.decode("utf-8-sig")


def parse_datetime(value: str) -> datetime | None:
    """Try common datetime formats used by CSV exports."""

    value = value.strip()

    formats = (
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%f%z",
    )

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass

    return None


def find_column(fieldnames: list[str], *names: str) -> str | None:
    """Find a column ignoring case, spaces, underscores and accents."""

    def normalise(value: str) -> str:
        return (
            value.strip()
            .lower()
            .replace(" ", "")
            .replace("_", "")
            .replace("-", "")
        )

    wanted = {normalise(name) for name in names}

    for field in fieldnames:
        if normalise(field) in wanted:
            return field

    return None


def load_latest():
    """Download data and return newest measurement per station."""

    text = download_csv(URL)

    # Detect delimiter instead of assuming comma/semicolon.
    sample = text[:10000]

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(
        io.StringIO(text),
        dialect=dialect,
    )

    if not reader.fieldnames:
        raise RuntimeError("CSV contains no header")

    fields = reader.fieldnames

    print("CSV columns:")
    for field in fields:
        print(f"  {field}")

    print()

    # Try to identify the important fields.
    station_col = find_column(
        fields,
        "station",
        "stationname",
        "nom",
        "nomstation",
        "name",
        "station_id",
        "stationid",
    )

    time_col = find_column(
        fields,
        "timestamp",
        "datetime",
        "date",
        "dateheure",
        "date_time",
        "time",
        "zeit",
    )

    value_col = find_column(
        fields,
        "value",
        "waterlevel",
        "water_level",
        "niveau",
        "niveau_eau",
        "wasserstand",
    )

    if station_col is None:
        raise RuntimeError(
            f"Could not identify station column. "
            f"Available columns: {fields}"
        )

    if time_col is None:
        raise RuntimeError(
            f"Could not identify timestamp column. "
            f"Available columns: {fields}"
        )

    if value_col is None:
        raise RuntimeError(
            f"Could not identify water-level column. "
            f"Available columns: {fields}"
        )

    print(f"Station column : {station_col}")
    print(f"Timestamp column: {time_col}")
    print(f"Value column    : {value_col}")
    print()

    latest = {}

    for row in reader:
        station = (row.get(station_col) or "").strip()
        timestamp_text = (row.get(time_col) or "").strip()
        value = (row.get(value_col) or "").strip()

        if not station or not timestamp_text:
            continue

        timestamp = parse_datetime(timestamp_text)

        if timestamp is None:
            continue

        # Keep only the newest measurement for each station.
        previous = latest.get(station)

        if previous is None or timestamp > previous["timestamp"]:
            latest[station] = {
                "station": station,
                "timestamp": timestamp,
                "timestamp_text": timestamp_text,
                "value": value,
            }

    return latest


def main():
    try:
        latest = load_latest()

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print()
    print("=" * 90)
    print(f"Latest water level - {len(latest)} stations")
    print("=" * 90)

    for station in sorted(latest, key=str.casefold):
        item = latest[station]

        print(
            f"{item['station']:<35} "
            f"{item['value']:>10} "
            f"{item['timestamp_text']}"
        )


if __name__ == "__main__":
    main()
