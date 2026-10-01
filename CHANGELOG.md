# Changelog

All notable changes to **Domoticz-Inondations-Lux** are documented in this file.

The project follows [Semantic Versioning](https://semver.org/) where practical.

* **Alpha** releases are development releases and may contain architectural or device-model changes.
* **Beta** releases are intended for real-world use but may still introduce changes before `1.0.0`.
* **`1.0.0`** will mark the first production-stable release with a frozen device model and a strong commitment to upgrade compatibility.

---

# Release History

## [0.1.2] - 2026-10-01

Maintenance release focused on live Domoticz operation, device update semantics, and operational diagnostics.

### Changed

* Station devices are now updated on every successful poll, even when the measured value has not changed.
* A station device's Domoticz `LastUpdate` timestamp therefore represents the latest successful observation of that station, rather than the last time its value changed.
* Unit 255 (`Last successful update`) now documents its role explicitly as the timestamp of the latest successful poll.
* Updated the documentation to describe the current bitwise Debug mask and operational logging categories.
* Release documentation and examples were updated from `0.1.1` to `0.1.2`.

### Notes

* This change does not alter station values, units, station identity, or the persisted station-to-Unit registry.
* A repeated value such as `91.0 cm` is still a new successful observation and is therefore written to Domoticz again.
* Failed source fetches still leave existing station values untouched.
* Stations without a usable current value are still skipped.

---

## [0.1.1] - 2026-09-29

Initial release. Reads the Luxembourg river water levels behind [www.inondations.lu](http://www.inondations.lu) and exposes one read-only Custom sensor per gauging station. Developed as 0.1.0-alpha; released as 0.1.1 with no alpha version ever made public - see "Changed" below.

### Changed

* Repository renamed to `Domoticz-Inondations-Lux`; plugin `key` renamed `InondationsLu` -> `InondationsLux` to match. This is a one-time rename done before any real install exists - per the Domoticz plugin `key` needing to stay stable once installs exist, it will not change again.
* Version scheme dropped the `-alpha` suffix for the public release; `0.1.1` (not `0.1.0`) because the development version string was already `0.1.0-alpha` when this was cut.

### Added

* Two selectable data sources, chosen with the **Data source** hardware field: the official `Water-Levels-LocalTime.csv` published by the Administration de la gestion de l'eau / CTIE (default), and the heichwaasser.lu JSON API as a fallback. Both feed one shared `Station` model, so devices, registry and filtering are source-agnostic.
* `.env` support for both source URLs (`INONDATIONS_CSV_URL`, `HEICHWAASSER_API_URL`) through a small built-in reader (`env_config.py`), with `.env.sample` as the tracked template. Precedence: real environment variable, then `.env`, then the built-in default in `constants.py`; a missing `.env` works.
* One Custom sensor per station. The unit (cm or m) is read from the feed per station.
* **River names for CSV devices.** The CSV has no river column, so `rivers.py` resolves a feed name to a river using a bundled table (`station_rivers.json`, river to stations, with `aliases` for CSV spellings) and names the device `<River> - <Station>`, matching API mode. Matching ignores case, accents and punctuation; the feed's `SN_` prefix and ` / <River>` / `_<River>` suffixes are read as hints; an ambiguous locality (Ettelbrück) is left alone unless the feed says which river. New hardware field **Device names (CSV source)** switches it off; unresolved stations are logged once and keep their feed name.
* The station name filter now matches the feed name or the device name, so a river name such as `Moselle` works as a filter.
* CSV parsing takes the last non-blank cell of a row as the current value, since a station that stopped reporting trails off with blank cells.
* `registry.py`: persisted station-name to Domoticz-Unit map (`station_units.json`), assigned once per station name and kept stable across restarts. Units 1-254 are used for stations.
* **Unit 255 - Last successful update**: Text sensor, updated only when a successful poll completes.
* Optional station name filter (case-insensitive substring match against the device name).
* Configurable update interval (default 15 minutes).
* Startup log lines with the plugin version and the active source and URL.
* Offline test suite (`tests.py`) with a Domoticz stub and two fixtures; it also checks that the version is consistent across the code and the documentation.
* Documentation set: `README.md`, `DEPLOY.md`, `SECURITY.md`, `CHANGELOG.md`, `ROADMAP.md`, `checklist.md`, `LICENSE`, `requirements.txt`.
* Python standard library only; no third-party runtime dependencies.

### Notes

* **Esch-Sure unit mismatch (root cause upstream).** The CSV lists `Esch-Sure` with unit `m` (a reservoir level, about 314), while the heichwaasser.lu API labels the same reading `cm`. The plugin reads the unit from the feed, so in API mode that device shows `cm`. It is deliberately not patched with a hardcoded special case; a test pins the behaviour and will flag it if upstream fixes it. This is why the CSV is the default source.
* **No station id or river in the CSV.** Rows are identified only by name (the `Number` column was blank on every row observed), which is why identity is name-based through the registry. Names carry irregular disambiguation (` / Alzette`, `_Our`, `SN_` prefix, `-Village`); see `README.md`.
* **Identity is the feed name, the river prefix is display only.** The registry key stays the raw name the source publishes, so correcting `station_rivers.json` later never creates duplicate devices, and the naming option can be changed freely (it applies to newly created devices only).
* **Switching source still creates a second set of devices**, because identity differs between the feeds even though CSV river naming now produces the same display names as API mode. Documented under Known limitations, not yet automated (see `ROADMAP.md`).
* **River table is partly unconfirmed.** It was built from the API's river and station list plus the CSV names captured during development. Ten stations were not captured from the CSV (Hesperange, Mersch, Troisvierges, Larochette, Mondorf-les-bains, Vianden, Bigonville, Michelau, Roodt-Syre, and the second Ettelbrück gauge), so their CSV spelling is unconfirmed; anything that does not resolve safely keeps its feed name.
* **Not yet run on a live Domoticz instance, and not yet installable through a Domoticz plugin manager.** The version number reflects development maturity, not live verification - those are tracked separately in README.md, "Supported data sources". The parsers are verified offline against fixtures in the feeds' real format; the fixtures are condensed excerpts, not full copies of the live files.
* **Station list completeness is unconfirmed.** Only part of the live CSV was captured during development, so the full list of station names (for example the name of a second Ettelbrück gauge) has not been confirmed. The plugin reads the list from the feed on every poll and hardcodes none of it.

