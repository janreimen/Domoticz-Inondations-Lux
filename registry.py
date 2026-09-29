"""
Persists a station name -> Domoticz Unit mapping to a small JSON file.

The raw CSV has no stable id for a station, only its name, so a Unit
number can't be derived the way it could from the old heichwaasser.lu
API (which had a numeric id per station). Instead, the first time a
station name is seen it's assigned the next free Unit and that
assignment is written to disk immediately, so it survives Domoticz
restarts and stays stable even if the CSV's row order changes or
stations are temporarily missing.

Kept free of any Domoticz import so it's testable with a plain
temporary file path (see tests.py).
"""

import json
import os
from typing import Dict

from constants import MAX_UNIT, MIN_UNIT


class RegistryError(Exception):
    """Raised when the on-disk unit map can't be read, or is exhausted."""


class StationUnitRegistry:
    def __init__(self, path: str):
        self.path = path
        self._map: Dict[str, int] = self._load()
        self._used = set(self._map.values())

    def unit_for(self, name: str) -> int:
        if name in self._map:
            return self._map[name]
        unit = self._allocate()
        self._map[name] = unit
        self._used.add(unit)
        self._save()
        return unit

    def _load(self) -> Dict[str, int]:
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as ex:
            raise RegistryError(f"could not read unit map at {self.path}: {ex}") from ex

        if not isinstance(data, dict):
            raise RegistryError(f"unit map at {self.path} is not a JSON object")

        result: Dict[str, int] = {}
        for name, unit in data.items():
            if not isinstance(unit, int):
                raise RegistryError(f"unit map at {self.path} has a non-integer unit for '{name}'")
            result[name] = unit
        return result

    def _allocate(self) -> int:
        for candidate in range(MIN_UNIT, MAX_UNIT + 1):
            if candidate not in self._used:
                return candidate
        raise RegistryError(f"no free Domoticz Unit left in {MIN_UNIT}-{MAX_UNIT} for a new station")

    def _save(self) -> None:
        # Write to a temp file and rename over the original so a crash
        # mid-write never leaves a truncated/corrupt map on disk.
        tmp_path = f"{self.path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self._map, f, indent=2, sort_keys=True)
        os.replace(tmp_path, self.path)
