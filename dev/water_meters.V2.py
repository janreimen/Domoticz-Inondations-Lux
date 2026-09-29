#!/usr/bin/env python3

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


DATE_FORMAT = "%d.%m.%Y %H:%M"


def download_csv() -> str:
    request = Request(
        URL,
        headers={
            "User-Agent": "Mozilla/5.0 water-level-monitor/1.0",
            "Accept": "text/csv,*/*",
        },
    )

    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8-sig")


def parse_timestamp(value: str) -> datetime:
    return datetime.strptime(value, DATE_FORMAT)


def main() -> int:
    try:
        csv_text = download_csv()
    except Exception as exc:
        print(f"ERROR downloading CSV: {exc}", file=sys.stderr)
        return 1

    reader = csv.reader(io.StringIO(csv_text))

    try:
        header = next(reader)
    except StopIteration:
        print("ERROR: CSV is empty", file=sys.stderr)
        return 1

    if len(header) < 5:
        print("ERROR: Unexpected CSV format", file=sys.stderr)
        return 1

    # First three columns are:
    #
    #   Name
    #   Number
    #   Unit
    #
    # Everything after that is a timestamp.
    timestamp_columns = []

    for index, column in enumerate(header[3:], start=3):
        try:
            timestamp = parse_timestamp(column.strip())
        except ValueError:
            print(
                f"WARNING: ignoring invalid timestamp column: {column!r}",
                file=sys.stderr,
            )
            continue

        timestamp_columns.append((index, timestamp))

    if not timestamp_columns:
        print("ERROR: No timestamp columns found", file=sys.stderr)
        return 1

    latest_timestamp = max(
        timestamp for _, timestamp in timestamp_columns
    )

    latest = []

    for row in reader:
        if not row:
            continue

        # Protect against malformed/incomplete rows.
        if len(row) < 3:
            continue

        name = row[0].strip()
        number = row[1].strip()
        unit = row[2].strip()

        if not name and not number:
            continue

        # Search backwards from the newest timestamp.
        value = None
        timestamp = None

        for index, ts in reversed(timestamp_columns):
            if index >= len(row):
                continue

            candidate = row[index].strip()

            if candidate == "":
                continue

            # Ignore common missing-value markers.
            if candidate.lower() in {
                "nan",
                "null",
                "none",
                "-",
                "n/a",
                "na",
            }:
                continue

            value = candidate
            timestamp = ts
            break

        latest.append(
            {
                "name": name,
                "number": number,
                "unit": unit,
                "timestamp": timestamp,
                "value": value,
            }
        )

    print()
    print(
        f"Latest water level per station "
        f"(dataset through {latest_timestamp:%d.%m.%Y %H:%M})"
    )
    print("=" * 100)

    print(
        f"{'Number':<10} "
        f"{'Station':<45} "
        f"{'Value':>12} "
        f"{'Unit':<8} "
        f"{'Timestamp'}"
    )

    print("-" * 100)

    for station in sorted(
        latest,
        key=lambda x: (
            x["name"].casefold(),
            x["number"],
        ),
    ):
        timestamp = (
            station["timestamp"].strftime(DATE_FORMAT)
            if station["timestamp"]
            else "NO DATA"
        )

        value = station["value"] or "NO DATA"

        print(
            f"{station['number']:<10} "
            f"{station['name']:<45.45} "
            f"{value:>12} "
            f"{station['unit']:<8} "
            f"{timestamp}"
        )

    print()
    print(f"Stations: {len(latest)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
