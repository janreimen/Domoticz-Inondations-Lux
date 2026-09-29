# Luxembourg River Levels (inondations.lu) for Domoticz

**Version 0.1.1**

A read-only Domoticz Python plugin that creates one sensor per river-gauging station in Luxembourg, from the official water-level feed behind [www.inondations.lu](https://www.inondations.lu).

## Highlights

- Read-only telemetry; the plugin only makes outbound HTTPS `GET` requests and never sends commands anywhere.
- Two selectable data sources: the **official CSV** published by the Administration de la gestion de l'eau / CTIE (default), or the **heichwaasser.lu JSON API** as a fallback.
- Both source URLs live in a `.env` file (`.env.sample` is the template); built-in defaults apply if it is missing.
- Per-station unit (cm or m) is read from the feed, not assumed.
- CSV devices are named `<River> - <Station>` where the river is known. The CSV has no river column, so the river comes from a small bundled table (`station_rivers.json`); unknown stations keep the feed's own name.
- The current value is the last non-blank reading in a station's row, so a station that stopped reporting recently still shows its newest real value.
- Persisted station-name to Domoticz-Unit registry, so devices stay stable across restarts even though the feed has no station id.
- "Last successful update" text sensor; a failed fetch never overwrites the last known values.
- Optional station name filter.
- Python standard library only; no third-party runtime dependencies (not even `python-dotenv`).
- Offline test suite that needs neither Domoticz nor network access.

## Requirements

- Domoticz with Python plugin support.
- Python 3.
- Network access from Domoticz to `inondations.public.lu` (CSV) or `heichwaasser.lu` (API).
- No account, API key or credentials of any kind.

No third-party Python package is required by the plugin.

Live verification is still pending (see **Supported data sources** below); the version number reflects development maturity of the code, not live-instance confirmation.

## Python Plugin Manager compatibility

There is no single official Domoticz plugin manager; several community ones exist ([Python Plugin Manager](https://wiki.domoticz.com/Python_Plugin_Manager), [domoticz-plugins-manager](https://github.com/stas-demydiuk/domoticz-plugins-manager), [PyPluginStore](https://github.com/adrighem/PyPluginStore)), and each installs a plugin by cloning its Git repository, not through a separate packaging format. This repository is structured to satisfy the requirements shared by all of them:

* `plugin.py` at the repository root, not nested in a subfolder.
* A stable, unique `key` in the `<plugin>` XML header (`InondationsLux`). Chosen once, before any real install exists, specifically so it never has to change - a manager tracks an installed plugin by this key, and changing it later would orphan existing devices.
* A public, credential-free HTTPS repository URL on a named branch (`master`).
* No third-party Python dependencies to install (`requirements.txt` documents this explicitly - most plugin managers do not install pip packages for you).
* `LICENSE` present at the repository root.

None of this makes the plugin appear automatically in any manager's browsable list - each one maintains its own index (typically a `plugins.json` in the manager's own repository) and expects a pull request from the plugin author to add an entry. For example, `domoticz-plugins-manager`'s format is:

```json
"InondationsLux": {
  "name": "Luxembourg River Levels (inondations.lu)",
  "author": "janreimen",
  "description": "Reads Luxembourg river water levels from the official CSV feed or the heichwaasser.lu API, one sensor per gauging station.",
  "repository": "https://github.com/janreimen/Domoticz-Inondations-Lux",
  "branch": "master",
  "folder": "Domoticz-Inondations-Lux"
}
```

This is deliberately not included as a file in this repository - it belongs in a PR against the manager's own repository, not here. `PyPluginStore` documents the same underlying requirements but not a public schema for its own index at the time of writing; check its repository for the current submission process before opening a PR there.

## Supported data sources

Selected per hardware instance with the **Data source** field.

| Source | Value | Status |
|---|---|---|
| Official CSV (`Water-Levels-LocalTime.csv`) | `csv` (default) | In development |
| heichwaasser.lu JSON API | `api` | In development |

- **Checked** — confirmed on a live Domoticz instance against the live feed.
- **In development** — the parser is verified offline against samples in the feed's real format (see `fixtures/`), but not yet confirmed on a live instance. If you hit missing or odd values, please open an issue with the header line and the row of the affected station (CSV) or that station's JSON object (API).

Both feeds refresh roughly every 15 minutes, so polling more often than that gains nothing.

### Which one to use

Use `csv` unless the CSV host is unreachable from your network. It is the primary source, and it states the correct unit per station. The API is an open-data reuse of the same measurements and has one known unit error (see **Known limitations**).

### Station naming in the CSV feed

The CSV identifies a station only by its name. It has no river column and no usable station id (the `Number` column was blank on every row observed). Names are used exactly as published, which means a few patterns:

| Pattern | Example | Meaning |
|---|---|---|
| Plain locality | `Perl`, `Diekirch` | Most stations |
| ` / <River>` suffix | `Ettelbrück / Alzette` | Disambiguates a locality with gauges on two rivers |
| `_<River>` suffix | `Gemünd_Our` | Same idea, different separator |
| `SN_` prefix | `SN_Wasserbillig`, `SN_Remich` | Moselle gauges; the prefix is not explained by the feed, and `Perl` (also Moselle) has none |
| `-Village` suffix | `Welscheid-Village` | Second gauge in the same locality |
| Unit `m` | `Esch-Sure` | Reservoir level in metres, not cm |

The set of stations is read from the feed on every poll; nothing is hardcoded. The list above only documents the naming quirks seen so far, not a complete station list. In API mode devices are named `<River> - <City>`, with ` (<supplement>)` appended where the API has one (`Wark - Welscheid (Village)`).

### River names in CSV mode (`station_rivers.json`)

Because the CSV has no river column, the river is looked up in `station_rivers.json`, a small table shipped with the plugin: river to stations, spelled as the heichwaasser.lu API spells them. An entry can carry `aliases` for the CSV's own spelling:

```json
"Syre": ["Mertert", "Roodt-Syre", {"name": "Uebersyren", "aliases": ["Ubersyren"]}]
```

How a feed name is resolved:

- Matching ignores case, accents and punctuation (`Sûre` equals `Sure`).
- The feed's own decorations are read first: an `SN_` prefix is dropped, and a trailing ` / <River>` or `_<River>` is used as a hint.
- A locality with gauges on two rivers (Ettelbrück: Alzette and Wark) is resolved only if the feed says which. Otherwise it is left alone rather than guessed.
- Anything unknown or ambiguous keeps its feed name.

| Feed name | Device name |
|---|---|
| `Ettelbrück / Alzette` | `Alzette - Ettelbrück` |
| `Gemünd_Our` | `Our - Gemünd` |
| `SN_Wasserbillig` | `Moselle - Wasserbillig` |
| `Ubersyren` | `Syre - Uebersyren` |
| `Welscheid-Village` | `Wark - Welscheid (Village)` |
| `Esch-Sure` | `Sûre - Esch-Sure` |

These are the same names API mode produces, so both modes look alike.

**Only the display name is affected.** Identity stays the raw feed name (it is the registry key), so editing the table can never create duplicate devices. The name is applied when a device is created; changing the table or the **Device names** field later does not rename existing devices (rename them in Domoticz if you want to).

Stations the table cannot resolve are logged once per start-up (`No river known for N station(s)...`). Add them to `station_rivers.json` and restart. Set **Device names** to *Name as published in the feed* to switch the feature off.

**Status: In development.** The table was built from the API's river and station list plus the CSV names captured during development. Ten stations were not captured from the CSV, so their CSV spelling is unconfirmed: Hesperange, Mersch, Troisvierges, Larochette, Mondorf-les-bains, Vianden, Bigonville, Michelau, Roodt-Syre and the second Ettelbrück gauge. Spelling variants and a `/ Wark` or `_Wark` suffix are handled, but check yours against the real file:

```bash
curl -s https://inondations.public.lu/dam-assets/ctie/datas/Water-Levels-LocalTime.csv \
  | python3 -c "import csv,sys; [print(r[0], '|', r[2]) for r in list(csv.reader(sys.stdin))[1:]]"
```

### Known limitations

- **API mode mislabels one unit.** `Esch-Sure` is a reservoir level in metres (about 314). The CSV says `m`; the API says `cm`, so in API mode that device shows `cm`. This is an upstream data error and is deliberately not patched with a hardcoded special case. A test pins the behaviour and will flag it if upstream ever fixes it.
- **Switching source adds devices.** Identity is the name as the source publishes it (`Ettelbrück / Alzette` in the CSV, `Alzette - Ettelbrück` in the API), so changing **Data source** on an existing hardware instance creates the other feed's devices next to the old ones. With river naming they can even carry the same display name on different Units. Remove the old devices under **Setup → Devices** if you switch permanently.
- **A station renamed in the feed appears as a new device**, for the same reason. The old device stops updating.
- The data is **not validated**. It is the raw automatic feed; treat an implausible reading as a data-source quirk, not a plugin bug.

## Installation

Copy the complete plugin directory into the Domoticz `plugins` directory:

```text
<domoticz>/plugins/Domoticz-Inondations-Lux/
```

The directory must contain `plugin.py` and the supporting Python modules shipped with this release. The plugin directory must be writable by the Domoticz user (the plugin writes `station_units.json` there).

Restart Domoticz after installing or replacing the plugin. See [`DEPLOY.md`](DEPLOY.md) for the full procedure.

## Configure the Domoticz hardware

Add a new hardware instance for **Luxembourg River Levels (inondations.lu)**.

The plugin configuration fields are:

| Field | Description |
|---|---|
| Data source | `Official CSV (recommended)` or `heichwaasser.lu API`; default CSV |
| Device names (CSV source) | `River - Station (where known)` (default) or `Name as published in the feed`. Ignored in API mode, which always uses `<River> - <City>` |
| Update interval (minutes) | Polling interval, default 15; minimum 1 |
| Station name filter | Optional comma-separated substrings; a station gets a device if its name contains any of them (case-insensitive). Empty means all stations |
| Debug | Standard Domoticz plugin debug levels; default None |

The filter is matched against both the feed name and the device name, so `Alzette` and `Moselle` work in either naming mode: `Moselle` matches `SN_Wasserbillig` (device `Moselle - Wasserbillig`) but only if the river table knows it.

The plugin is intentionally **read-only**. Its devices are sensors, not controls, and commands from Domoticz are ignored.

### The `.env` file

Both source URLs are read from `.env` in the plugin directory:

```text
INONDATIONS_CSV_URL=https://inondations.public.lu/dam-assets/ctie/datas/Water-Levels-LocalTime.csv
HEICHWAASSER_API_URL=https://heichwaasser.lu/api/v1/rivers
```

- `.env.sample` is the tracked template. `.env` is your local copy and is not committed. A working `.env` with the default URLs ships next to the sample, so nothing needs configuring out of the box.
- Precedence: a real **environment variable** of the same name wins, then the **`.env` file**, then the **built-in default** in `constants.py`. A missing `.env`, or a missing key in it, is fine.
- Use it to point at a mirror, a caching proxy or a test server. Do not put credentials in it; the plugin has no use for them.
- Parsing is a small built-in reader (`KEY=VALUE`, `#` comments, optional quotes). A malformed line is ignored and that key falls back to its default.
- The plugin logs the active source and URL at startup.

## Devices

Unlike a vehicle plugin with a fixed device list, the station list comes from the feed, so Unit numbers are assigned dynamically:

| Unit | Device |
|---:|---|
| 1–254 | One Custom sensor per station, in the order first seen; the assignment is recorded in `station_units.json` |
| 255 | Last successful update — Text sensor |

### Station-unit registry

Neither feed provides a usable stable id, so for **both** sources the first time a station name is seen it is assigned the next free Unit (1–254), and the assignment is written to `station_units.json` in the plugin directory immediately.

Every later poll and every Domoticz restart reads it back, so a device never jumps to a new Unit or gets duplicated because the feed's row order changed or a station went briefly quiet.

- Writes are atomic (temp file plus rename), so a crash cannot leave a truncated file.
- If the file exists but is not valid, the plugin refuses to poll and logs an error, rather than silently reassigning every station's Unit. Fix or remove the file and restart Domoticz.
- It is per-install runtime state: do not commit it or copy it between installs. If the plugin directory is not persistent (for example a Docker container without a volume), the registry is lost and Units may be reassigned to different stations; see `DEPLOY.md`.

### Value and unit

- The device shows the station's newest reading in the unit the feed states for it (`cm` for most stations, `m` for at least one).
- CSV mode: each row is padded to the same width, but a station that stopped reporting trails off with blank cells. The current value is the last non-blank cell, not literally the last column. A station whose whole row is blank gets no update.
- API mode: the `current.value` field of the station object.

### Unit 255 — Last successful update

Set to the local date and time of the last poll that updated at least one station. It is not touched when a fetch fails or when no station matched the filter, so a stalled feed is visible at a glance.

## Data source behavior

The plugin retrieves data using one of:

```text
GET https://inondations.public.lu/dam-assets/ctie/datas/Water-Levels-LocalTime.csv
GET https://heichwaasser.lu/api/v1/rivers
```

No authentication is used. The only header sent besides the defaults is `User-Agent: Domoticz-Inondations-Lux/<version>`. The timeout is 20 seconds.

The CSV contains several days of 15-minute history for every station and is downloaded in full on each poll; only the newest reading of each row is used.

There is no retry within a poll. On any network, HTTP, decoding or JSON failure the error is logged, no device is touched, and the next attempt is made after the configured interval. Malformed or blank rows are skipped without aborting the poll.

## Runtime state and repository hygiene

The plugin creates a local runtime state file. It is a **runtime file, not a release file**, and must not be committed to Git.

The repository `.gitignore` excludes:

```text
station_units.json
station_units.json.tmp
.env
.env.*        (except .env.sample)
__pycache__/
*.py[cod]
.pytest_cache/
*.swp
*.swo
```

Never commit:

- `.env` or any local configuration.
- Runtime JSON state files.
- Local backups or `archives/` material.
- Logs containing internal hostnames or other private information.

## Development and tests

The project contains a test suite in `tests.py`. It installs a minimal Domoticz stub, reads the fixtures in `fixtures/`, and never touches the network, so it runs anywhere with Python 3:

```bash
python3 tests.py
```

For a basic source-tree syntax check:

```bash
python3 -m py_compile *.py
```

The suite also checks that the version written in `plugin.py`, `constants.py`, this README, `CHANGELOG.md` and `ROADMAP.md` agree, and that the shipped `.env` and `.env.sample` carry the built-in default URLs.

### Test fixtures

- `fixtures/water_levels_sample.csv` is a small hand-picked sample in the feed's real format, with the awkward real station names (`Esch-Sure` in metres, `SN_Wasserbillig`, `Ettelbrück / Alzette`, `Welscheid-Village`, and `Ubersyren` with trailing blank cells). It is a condensed excerpt (9 timestamp columns instead of several hundred), not a byte-for-byte copy of the live file.
- `fixtures/rivers_api_sample.json` is a 3-river / 5-station excerpt of the API's real response shape, including a `supplement` case and the mislabelled `Esch-Sure` unit.

## Project layout

```text
plugin.py             Domoticz callback entry points only
csv_client.py         HTTP client for the CSV feed
api_client.py         HTTP client for the heichwaasser.lu API
errors.py             Shared SourceFetchError
env_config.py         .env reader and URL resolution
stations.py           Domoticz-free parsers (CSV and API) into one Station model
rivers.py             River lookup for CSV station names (display names only)
station_rivers.json   River to stations table used by rivers.py
registry.py           Persisted station-name to Domoticz-Unit map
devices.py            All Domoticz device create/update logic
constants.py          Version, default URLs and shared constants
utils.py              Small stateless helpers
tests.py              Offline test suite
fixtures/             Sample CSV and API payload used by tests.py
.env / .env.sample    Data source URLs (local copy / tracked template)
```

## Release checklist

Before publishing a release:

```bash
python3 tests.py
git status --short --ignored
git add .
git status
git commit -m "Release 0.1.1"
git tag -a 0.1.1 -m "Release 0.1.1"
```

Then push the actual repository branch and tag:

```bash
git push origin <branch>
git push origin 0.1.1
```

Do not assume the branch is `master` or `main`; check with:

```bash
git branch --show-current
```

The published source tree must not contain `.env` or `station_units.json`. See [`checklist.md`](checklist.md) for the development-to-master workflow.

## Security

See [`SECURITY.md`](SECURITY.md) for vulnerability reporting and configuration-handling guidance.

## License

MIT License. See [`LICENSE`](LICENSE).

## Data sources

- Official feed: [www.inondations.lu](https://www.inondations.lu) and the CSV at `https://inondations.public.lu/dam-assets/ctie/datas/Water-Levels-LocalTime.csv`
- Open-data JSON reuse: `https://heichwaasser.lu/api/v1`

The measurements belong to their publishers. This plugin only reads them for local home automation and does not redistribute them; check the publishers' terms before republishing the data.

