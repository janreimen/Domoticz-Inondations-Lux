"""
Best-effort river lookup for the CSV source.

The official CSV has no river column, only a station name. This module
resolves a feed name such as "Ettelbrück / Alzette" or "SN_Wasserbillig"
to ("Alzette", "Ettelbrück") / ("Moselle", "Wasserbillig") using a small
table shipped with the plugin (station_rivers.json: river -> stations).

It only affects the *display* name of a device. Device identity stays
the raw feed name (see registry.py), so correcting this table later can
never create duplicate devices. Anything that cannot be resolved
unambiguously simply keeps its feed name.

Kept free of any Domoticz import so it is testable on its own.
"""

import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

_SN_PREFIX = re.compile(r"^SN_", re.IGNORECASE)


class RiverTableError(Exception):
    """Raised when the river table can't be read or is malformed."""


def normalize(text: str) -> str:
    """Case-, accent- and punctuation-insensitive form used for matching
    ("Sûre" == "Sure", "Mondorf-les-Bains" == "mondorf les bains")."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^0-9a-zA-Z]+", " ", stripped).strip().casefold()


@dataclass(frozen=True)
class _Entry:
    river: str
    label: str


class RiverIndex:
    def __init__(self, table: Dict[str, list]):
        self._by_key: Dict[str, List[_Entry]] = {}
        for river, entries in table.items():
            if not isinstance(river, str) or not isinstance(entries, list):
                raise RiverTableError(f"river '{river}' must map to a list of stations")
            for entry in entries:
                if isinstance(entry, str):
                    label, aliases = entry, []
                elif isinstance(entry, dict) and isinstance(entry.get("name"), str):
                    label = entry["name"]
                    aliases = [a for a in entry.get("aliases", []) if isinstance(a, str)]
                else:
                    raise RiverTableError(f"bad station entry under '{river}': {entry!r}")

                item = _Entry(river=river, label=label)
                for spelling in [label, *aliases]:
                    bucket = self._by_key.setdefault(normalize(spelling), [])
                    if item not in bucket:
                        bucket.append(item)

    def __len__(self) -> int:
        return len({e for bucket in self._by_key.values() for e in bucket})

    def resolve(self, feed_name: str) -> Optional[Tuple[str, str]]:
        """(river, station label) for a CSV station name, or None if it
        is unknown or ambiguous.

        The feed disambiguates some names itself, so those decorations
        are read first: an "SN_" prefix is dropped, and a trailing
        " / <River>" or "_<River>" is used as a hint for localities that
        have a gauge on two rivers (Ettelbrück: Alzette and Wark).
        """
        name = _SN_PREFIX.sub("", feed_name.strip())
        hint = None
        if "/" in name:
            name, hint = (part.strip() for part in name.split("/", 1))
        elif "_" in name:
            name, hint = (part.strip() for part in name.rsplit("_", 1))

        candidates = self._by_key.get(normalize(name))
        if not candidates:
            return None
        if hint:
            wanted = normalize(hint)
            candidates = [c for c in candidates if normalize(c.river) == wanted]
        if len(candidates) != 1:
            return None
        return candidates[0].river, candidates[0].label


def load_river_index(path: str) -> RiverIndex:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as ex:
        raise RiverTableError(f"could not read river table at {path}: {ex}") from ex
    if not isinstance(data, dict):
        raise RiverTableError(f"river table at {path} is not a JSON object")
    return RiverIndex(data)
