# Deployment Guide

## Domoticz Luxembourg River Levels (inondations.lu)

This document describes how to install, configure, update, and remove the **Luxembourg River Levels (inondations.lu)** plugin for Domoticz.

The plugin reads the official Luxembourg water-level feed and exposes one read-only Custom sensor per gauging station as a Domoticz device.

---

## 1. Requirements

Before installing the plugin, make sure the following requirements are met:

* A working Domoticz installation
* Python 3
* Internet connectivity from the Domoticz host to `inondations.public.lu` (CSV source) and/or `heichwaasser.lu` (API source)
* Permission to write to the Domoticz plugins directory, and the Domoticz user must be able to write inside the plugin directory itself
* No account, API key or credentials are needed

The plugin is designed for the Domoticz Python plugin architecture.

---

## 2. Installation

### 2.1 Locate the Domoticz plugins directory

The plugin must be installed inside the Domoticz `plugins` directory.

Typical locations include:

```text
/opt/domoticz/plugins
/srv/domoticz/plugins
/home/pi/domoticz/plugins
```

For a Docker-based Domoticz installation, use the directory that is mapped to the container's Domoticz plugins directory (see section 16).

You can determine the active Domoticz installation directory from the Domoticz service/container configuration.

---

### 2.2 Clone the repository

Change to the Domoticz plugins directory:

```bash
cd /opt/domoticz/plugins
```

Clone the repository:

```bash
git clone https://github.com/janreimen/Domoticz-Inondations-Lux.git Domoticz-Inondations-Lux
```

The resulting directory should look similar to:

```text
plugins/
└── Domoticz-Inondations-Lux/
    ├── plugin.py
    ├── .env.sample
    ├── README.md
    ├── DEPLOY.md
    ├── SECURITY.md
    ├── LICENSE
    └── ...
```

All the `.py` files (`plugin.py`, `csv_client.py`, `api_client.py`, `errors.py`, `env_config.py`, `stations.py`, `rivers.py`, `registry.py`, `devices.py`, `constants.py`, `utils.py`, `tests.py`) and `station_rivers.json` must stay siblings in the same directory. Domoticz adds that directory to `sys.path` when it loads `plugin.py`, which is how the local imports resolve.

---

## 3. Python Dependencies

The plugin uses Python 3 and the standard library only.

Check the Python version:

```bash
python3 --version
```

`requirements.txt` documents that no third-party package is required. There is nothing to install with `pip`, and `.env` support is built in (no `python-dotenv`).

### Docker

Because nothing has to be installed, no change to the Domoticz container image is needed.

---

## 4. File Permissions

The Domoticz process must be able to **read** the plugin files and **write** inside the plugin directory, because the plugin creates `station_units.json` there.

For example:

```bash
sudo chown -R domoticz:domoticz /opt/domoticz/plugins/Domoticz-Inondations-Lux
```

Adjust the user and group if Domoticz runs under a different account.

Verify:

```bash
ls -la /opt/domoticz/plugins/Domoticz-Inondations-Lux
```

If the directory is not writable, the plugin cannot save its station-unit map and every poll will fail with an error in the Domoticz log.

---

## 5. Configure the Plugin

### 5.1 The `.env` file (optional)

`.env` is not part of the repository (see `.gitignore`), so a fresh `git clone` only contains `.env.sample`. You can skip this step entirely: the built-in defaults are the same URLs.

To override them:

```bash
cd /opt/domoticz/plugins/Domoticz-Inondations-Lux
cp .env.sample .env
nano .env
```

Keys:

```text
INONDATIONS_CSV_URL=https://inondations.public.lu/dam-assets/ctie/datas/Water-Levels-LocalTime.csv
HEICHWAASSER_API_URL=https://heichwaasser.lu/api/v1/rivers
```

Precedence: a real environment variable of the same name in the Domoticz service environment, then `.env`, then the built-in default. A malformed line is ignored and that key falls back to its default.

**Do not put credentials in `.env`.** The plugin has no use for them.

### 5.2 The hardware instance

Start or restart Domoticz after installing the plugin.

Open the Domoticz web interface and navigate to:

```text
Setup → Hardware
```

Select:

```text
Luxembourg River Levels (inondations.lu)
```

Create a new hardware instance and set:

* **Data source** — `Official CSV (recommended)` or `heichwaasser.lu API`
* **Device names (CSV source)** — `River - Station (where known)` (default) or the feed's own names. Applied when a device is created; it does not rename existing devices
* **Update interval (minutes)** — default 15
* **Station name filter** — optional, empty means all stations
* **Debug** — bitwise debug mask; `0` disables plugin-specific debug output

---

## 6. Choosing the Data Source

Use the official CSV unless it is unreachable from your network. The API is an alternative for that case.

Two things to know before switching the source on an existing hardware instance:

* The two feeds name stations differently, so switching creates the other feed's devices next to the old ones. Remove the old devices under **Setup → Devices** if you switch permanently.
* In API mode the `Esch-Sure` reservoir level (metres) is labelled `cm` by the upstream data. See `README.md`, "Known limitations".

---

## 7. Restart Domoticz

After changing plugin files or `.env`, restart Domoticz. The `.env` file is read only at plugin start.

For a systemd installation:

```bash
sudo systemctl restart domoticz
```

Check the service:

```bash
sudo systemctl status domoticz
```

For Docker:

```bash
docker restart domoticz
```

Replace `domoticz` with the actual container name if necessary.

---

## 8. Verify the Installation

After restarting Domoticz:

1. Open the Domoticz web interface.
2. Go to **Setup → Hardware**.
3. Verify that **Luxembourg River Levels (inondations.lu)** is present and enabled.
4. Open **Setup → Devices**.
5. Verify that one Custom device per matched station and a **Last successful update** text device are present.
6. Check the Domoticz log. At startup it should contain lines like:

```text
Starting Luxembourg River Levels (inondations.lu) 0.1.2
Data source: csv (https://inondations.public.lu/dam-assets/ctie/datas/Water-Levels-LocalTime.csv)
```

7. Verify that `station_units.json` now exists in the plugin directory. Leave it in place.
8. After a successful poll, verify that the station device's **LastUpdate** timestamp advances even when its measured value is unchanged. For example, a station remaining at `91.0 cm` is still written to Domoticz at each successful poll.
9. Verify that **Last successful update** also advances after a successful poll.

A successful installation should show the plugin starting without Python import or configuration errors.

---

## 9. Updating the Plugin

Before updating, check the release notes (`CHANGELOG.md`) for the target version.

### Recommended Git update

Change to the plugin directory:

```bash
cd /opt/domoticz/plugins/Domoticz-Inondations-Lux
```

Check the current state:

```bash
git status
```

`.env` and `station_units.json` are untracked and ignored, so they are not touched by updates: existing devices keep their Units and your URL overrides survive. If the release notes mention a new `.env` key, compare your `.env` with `.env.sample`.

If the working tree is clean, fetch the latest version:

```bash
git fetch --tags
```

List available releases:

```bash
git tag
```

Check out the desired release:

```bash
git checkout <VERSION>
```

For example:

```bash
git checkout 0.1.2
```

Restart Domoticz:

```bash
sudo systemctl restart domoticz
```

### Important

Do not overwrite a working installation blindly with files from another release.

Always keep the deployed version identifiable so that the installation can be rolled back if necessary. Never delete `station_units.json` as part of an update.

---

## 10. Updating From GitHub

To update to the latest repository state:

```bash
cd /opt/domoticz/plugins/Domoticz-Inondations-Lux
git fetch origin
git pull --ff-only
```

Then restart Domoticz:

```bash
sudo systemctl restart domoticz
```

Using `--ff-only` prevents Git from silently creating an unexpected merge commit on the deployment host.

---

## 11. Release Deployment

Production installations should preferably use a tagged release rather than an arbitrary development commit.

Example:

```bash
git fetch --tags
git checkout <VERSION>
```

Then verify:

```bash
git describe --tags --always
git status
```

The deployment should report the intended release/version.

### Release workflow

When preparing a new GitHub release, use the project's version progression consistently, and do not skip an intermediate release when the repository workflow requires it. See `checklist.md` for the development-to-master workflow.

---

## 12. Rollback

If a new release causes problems, return to the previously working release.

First inspect available tags:

```bash
cd /opt/domoticz/plugins/Domoticz-Inondations-Lux
git tag
```

Check out the previous version:

```bash
git checkout <PREVIOUS_VERSION>
```

Restart Domoticz:

```bash
sudo systemctl restart domoticz
```

Then verify the Domoticz log. `station_units.json` and the existing devices are unaffected by a rollback.

---

## 13. Troubleshooting

### Plugin does not appear in Domoticz

Check that the directory is located directly below the Domoticz plugins directory:

```text
plugins/Domoticz-Inondations-Lux/plugin.py
```

Check the file:

```bash
ls -l /opt/domoticz/plugins/Domoticz-Inondations-Lux/plugin.py
```

Restart Domoticz after correcting the installation.

---

### Python error during startup

Check the Domoticz log.

Look for messages containing:

```text
Inondations
Traceback
ImportError
ModuleNotFoundError
SyntaxError
```

(`grep -i inondations` also catches it regardless of case.)

Run a basic syntax check of the whole source tree:

```bash
cd /opt/domoticz/plugins/Domoticz-Inondations-Lux
python3 -m py_compile *.py
```

A successful command produces no output. An `ImportError` for a sibling module (`csv_client`, `stations`, ...) usually means a file is missing from the plugin directory.

---

### Offline self-test

To rule out a local installation problem, run the bundled test suite from inside the plugin directory:

```bash
python3 tests.py
```

It needs no Domoticz installation and no network access.

---

### No devices appear / "Fetch from 'csv' source failed"

Confirm the host can reach the URL the plugin logged at startup, for example:

```bash
curl -I https://inondations.public.lu/dam-assets/ctie/datas/Water-Levels-LocalTime.csv
```

A firewall or DMZ egress rule is the usual cause. If only the CSV host is blocked, switch **Data source** to the API and mind section 6.

---

### Wrong URL is being used

The startup log line shows exactly which URL is active. Remember the precedence: real environment variable, then `.env`, then built-in default. `.env` is read only when the plugin starts, so restart Domoticz after editing it.

---

### "No stations matched"

The station name filter does not match any station name from the selected source. Matching is a case-insensitive substring test but is otherwise literal, including accents (`Sûre`, not `Sure`). Clear the filter to confirm the plugin works unfiltered, then narrow it down. Remember that CSV and API names differ.

---

### "Could not load station unit map"

`station_units.json` exists but is not valid. The plugin refuses to guess, because silently discarding the map could give a station's Unit to a different station. Fix the JSON, or, as a last resort, delete the file and also remove the affected devices under **Setup → Devices** before restarting.

---

### Some CSV stations have no river prefix

Expected for stations the bundled `station_rivers.json` cannot resolve, or resolves ambiguously (a locality with gauges on two rivers). The Domoticz log lists them once at start-up: `No river known for N station(s)...`. Compare with the names in your real CSV:

```bash
curl -s https://inondations.public.lu/dam-assets/ctie/datas/Water-Levels-LocalTime.csv \
  | python3 -c "import csv,sys; [print(r[0], '|', r[2]) for r in list(csv.reader(sys.stdin))[1:]]"
```

Then add the missing stations (or their spelling, as an `aliases` entry) to `station_rivers.json` and restart Domoticz. Existing devices keep their names; only newly created devices get the new one. If `station_rivers.json` is missing or invalid, the log says so and every station simply keeps its feed name.

---

### Duplicate devices after switching source or a station rename

Expected: identity is name-based and the two feeds name stations differently. Remove the stale devices under **Setup → Devices**.

---

### `Esch-Sure` shows `cm` instead of `m`

You are using the API source, and the upstream data mislabels it. Use the CSV source.

---

### A station reads an implausible value

That is the raw upstream feed, not a plugin bug. See `README.md`.

---

### A station's value has not changed but `LastUpdate` should be current

This is expected behavior in 0.1.2.

The plugin deliberately calls Domoticz `Update()` for every usable station reading on every successful poll. A repeated value such as `91.0 cm` is still a successful new observation, so the station device's `LastUpdate` timestamp advances.

If it does not:

1. Check that the poll itself completed successfully.
2. Check the station has a usable current value.
3. Check the Domoticz log for the station's processing message.
4. Check that the plugin directory contains the expected 0.1.2 code.
5. Run:

```bash
python3 tests.py
```

---

## 14. Logging and Diagnostics

When diagnosing problems, collect the relevant Domoticz log entries, together with the active data source.

The plugin handles no credentials, so logs contain none. Still avoid posting internal hostnames or URLs of private mirrors/proxies configured in `.env` or the environment. Replace such values with:

```text
<REDACTED>
```

before sharing logs.

The plugin's Debug hardware field is a bitwise mask:

```text
Basic       1
Python      2
Connection  4
Messages    8
Queue      16
Operational 32
All        63
```

For example:

```text
Python + Connection + Messages = 14
```

Operational logging is intended to describe normal plugin lifecycle events. Detailed category-specific diagnostic output is controlled by the selected debug bits.

---

## 15. Removing the Plugin

Before removing the plugin, disable the hardware instance in Domoticz.

Then stop or restart Domoticz as appropriate.

Remove the plugin directory (this also removes `.env` and `station_units.json`):

```bash
sudo rm -rf /opt/domoticz/plugins/Domoticz-Inondations-Lux
```

Restart Domoticz:

```bash
sudo systemctl restart domoticz
```

Plugin-created Domoticz devices may need to be removed separately through the Domoticz web interface.

---

## 16. Docker Deployment

For a Docker-based Domoticz installation, the plugin must be available inside the Domoticz container.

A typical setup uses a persistent volume for the Domoticz data directory.

Example concept:

```text
Host
└── domoticz/
    └── plugins/
        └── Domoticz-Inondations-Lux/
```

mapped into the container's Domoticz data/plugins directory.

**The plugin directory must be persistent and writable.** `station_units.json` lives there. If it is lost while the Domoticz database (and therefore the devices) survives, the plugin starts a new map and assigns Units in the order it sees the stations, which can attach new readings to the wrong existing devices. Do not run the plugin from a container layer that is discarded on recreation.

After installing or updating the plugin on the host-mounted directory:

```bash
docker restart domoticz
```

Verify the plugin from inside the container if required:

```bash
docker exec -it domoticz ls -la /opt/domoticz/plugins/Domoticz-Inondations-Lux
```

The exact container path depends on the Domoticz Docker image and volume configuration. Outbound HTTPS must be allowed from the container. Environment variables (`INONDATIONS_CSV_URL`, `HEICHWAASSER_API_URL`) can be passed to the container as an alternative to `.env`.

---

## 17. Production Deployment Checklist

Before considering a deployment complete:

* [ ] Domoticz is running correctly.
* [ ] Python 3 is available.
* [ ] Plugin files are in the correct `plugins` directory.
* [ ] File permissions allow Domoticz to read the plugin and write inside its directory.
* [ ] The plugin appears under **Setup → Hardware**.
* [ ] The intended data source is selected.
* [ ] `.env` (if used) contains only the intended URLs.
* [ ] `station_rivers.json` is present (CSV river names) and the log lists no unexpected "No river known" stations.
* [ ] Domoticz has been restarted.
* [ ] Station devices and **Last successful update** appear under **Setup → Devices**.
* [ ] A station's `LastUpdate` advances on each successful poll even when its value remains unchanged.
* [ ] `station_units.json` exists in the plugin directory and the directory is persistent.
* [ ] The startup log shows the expected version and source.
* [ ] No fetch errors or Python exceptions are present in the Domoticz log.
* [ ] The deployed Git version/tag has been recorded.

---

## 18. Security

Security-related information and vulnerability reporting are documented separately in:

```text
SECURITY.md
```

Never commit `.env`, `station_units.json`, or logs containing private information to this repository.

---

## 19. Support

For problems with the plugin, provide:

* plugin version
* Domoticz version
* Python version
* operating system
* installation type (native/Docker)
* active data source (`csv` or `api`)
* relevant Domoticz log entries

Remove private information before submitting logs.

Project repository:

https://github.com/janreimen/Domoticz-Inondations-Lux

