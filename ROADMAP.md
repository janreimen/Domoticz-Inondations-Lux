# Roadmap

The roadmap describes the intended future development of **Domoticz-Inondations-Lux**.

The project is currently at **0.1.1 — Initial release**.

The roadmap deliberately separates:

* **Planned** — intended development target.
* **Potential** — useful future functionality, but not yet committed.
* **Source-dependent** — dependent on what the CSV feed or the heichwaasser.lu API exposes.
* **Deferred** — deliberately postponed until the architecture or data is ready.

Features are **not considered implemented** until they are released in a version of the plugin.

---

# Current State — 0.1.1

The current release is a **read-only** integration.

* Official CSV source (default) and heichwaasser.lu API source (fallback), selected per hardware instance.
* Source URLs in `.env` / `.env.sample`, with environment-variable override and built-in defaults.
* One Custom sensor per station, unit read from the feed.
* Last-non-blank-cell current value for CSV rows.
* River names for CSV devices from the bundled `station_rivers.json` (display name only; identity stays the feed name).
* Persisted name-to-Unit registry (`station_units.json`), Units 1-254.
* Unit 255: Last successful update.
* Optional station name filter and configurable poll interval.
* Offline test suite and the full documentation set.

Not yet confirmed on a live Domoticz instance.

---

# 0.1.x — Live Verification

## Status

Planned.

## Objective

Move both sources from "In development" to "Checked" (see `README.md`, Supported data sources).

## Work

* Run against a live Domoticz instance on both sources and record the result.
* Capture the complete CSV and confirm the full station list, including how a second gauge in the same locality (for example Ettelbrück on the Alzette and on the Wark) is named.
* Complete and confirm `station_rivers.json` against that list: ten stations' CSV spelling is unconfirmed (see `CHANGELOG.md`), and any "No river known" lines in the log point at gaps.
* Confirm whether the `Number` column is ever populated; if it is, evaluate it as a stable station id in place of name-based identity.
* Add a standalone helper in the spirit of MySkodaAPI's `verify_charging_fields.py`: fetch the selected source once and print what the parser makes of it (station count, units, stations without a current value), without needing Domoticz.
* Confirm behaviour when a station's whole row is blank for a long time.

## Acceptance criteria

* Both sources run for several days on a live instance without errors in the Domoticz log.
* `station_units.json` survives restarts and updates with no duplicated or shifted devices.
* Any parsing differences found are covered by new regression tests using real excerpts.

---

# Potential

## Staleness indicator

The CSV header carries a local-time timestamp for every column (`DD.MM.YYYY HH:MM`), and the plugin currently ignores it. The timestamp of each station's last non-blank cell would show how old its reading is. Possible outputs: a per-station reading time, or one plugin-wide "stale stations" sensor. A station silent for hours currently keeps showing its last value with no visual hint.

## Alert level and trend (Source-dependent)

Only the API exposes a `trend` (`up` / `rest` / `down`) and an `alert_levels` list per station (the "vigilance" and "alert" thresholds, in the feed's unit). The CSV has neither. Possible devices: a native Domoticz Alert sensor per station and a trend indicator, available in API mode only. Would need a decision on how to behave in CSV mode.

## Source switching without duplicate devices

Because identity is name-based and the two feeds name stations differently, switching source creates a second device set. River naming already gives CSV and API stations the same display name, but their identity (registry key) still differs. A migration step that maps a CSV name to its API equivalent would remove the limitation. The river table is the natural basis for it, once it is confirmed against the full station list from 0.1.x.

## Automatic failover

Fall back from CSV to API after repeated fetch failures. Depends on the previous item; without it, a failover would create duplicate devices and, in API mode, the `Esch-Sure` unit mislabel would appear.

## Self-updating river table

`station_rivers.json` is maintained by hand. If new gauges appear in the feed they keep their feed name until someone adds them. Possible improvement: join against the API's river and station list at run time. Deferred for now, because it would make the CSV path depend on a second host, and the two feeds spell names differently.

## Outlier flagging

The raw feed occasionally contains implausible readings (for example a deeply negative value). Optional detection could mark such a reading instead of showing it. Needs a defensible rule per station type first.

---

# Deferred

## Retry and backoff

There is currently no retry within a poll; the next attempt happens after the configured interval. Bounded retry with backoff, as in MySkodaAPI, is deferred until live testing shows whether transient failures are common enough to matter.

## Additional per-station data

The API also publishes historical minimum and maximum records per station. Not planned until there is a concrete use for them.

---

# 1.0.0 — Production Stable

## Status

Deferred.

## Requirements

* Both sources "Checked" on live instances.
* A frozen device model: Unit allocation rules and the `station_units.json` format documented as stable.
* Documented upgrade compatibility, including how existing devices are preserved.
* No unresolved known limitations that cause duplicate or shifted devices.

