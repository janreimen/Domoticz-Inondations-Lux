# Security Policy

## Supported versions

Security fixes are intended for the current development/release version.

The following versions of this project are actively supported with security updates:

* **0.1.x**: ✅ Supported

The current release is **0.1.2**. Only the latest 0.1.x release is supported; please update before reporting an issue.

## Reporting a vulnerability

Please do **not** publish private configuration, internal hostnames or URLs, or exploitable security details in a public GitHub issue.

Use GitHub's private security reporting mechanism for the repository where available, or contact the maintainer privately.

Provide enough information to reproduce the issue without exposing private information.

## Credentials and private data

The plugin needs **no credentials, API keys or secrets**. Both data sources are public and unauthenticated.

The `.env` file holds only the two source URLs. It is excluded from Git so that local overrides stay local, not because it contains secrets. Do not put credentials in it; the plugin has no use for them.

Because the URLs are configurable, whoever can edit `.env` or the Domoticz service environment controls where the plugin fetches from. Keep the plugin directory writable only by the Domoticz user and administrators. Prefer `https://` URLs; the plugin does not restrict the scheme.

Protect the following as sensitive configuration/data if you use private mirrors or proxies:

* `.env` and the Domoticz service environment.
* The Domoticz hardware configuration and database backups.
* The plugin directory and host filesystem.
* Logs and diagnostic exports.

## Untrusted input

The only untrusted input is the CSV or JSON returned by the selected source.

* CSV is parsed with Python's standard `csv` module, JSON with `json.loads`. Nothing is passed to `eval`, `exec` or `pickle`.
* Every field is read defensively: an unexpected value becomes "no reading" rather than an exception, and a malformed or blank row is skipped without aborting the poll.
* Station names from the feed are used as Domoticz device names and as keys in `station_units.json`; they are never used as file paths or executed.
* `station_rivers.json` is static data shipped with the plugin and read with `json.load`. It only influences device display names; if it is missing or malformed the plugin logs an error and keeps the feed's own names.

## Repository hygiene

The following files/directories are runtime or local-development material and must not be committed:

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

The repository `.gitignore` is configured to prevent accidental publication of these files.

Never commit private configuration, internal URLs, or logs containing such information.

If a secret is accidentally committed, deleting the file in a later commit is insufficient. Rotate/revoke the exposed credential first, then remove the secret from the Git history.

## Runtime state

The plugin writes one file of its own, `station_units.json`, inside its own plugin directory. It maps station names to Domoticz Unit numbers and contains nothing else.

* Writes are atomic (temporary file plus rename), so a crash cannot leave a truncated file.
* A file that exists but is invalid is treated as a hard error, not silently discarded, because discarding it could reassign a station's Unit to a different device.
* A malformed `.env` line, by contrast, is ignored and falls back to the default URL. That is safe: a bad URL cannot silently re-identify devices.

## Read-only design

The plugin is intentionally read-only. It makes outbound HTTPS `GET` requests, does not listen on any port, and does not implement any control operations. Commands sent to its devices from Domoticz are ignored.

## Transport and dependencies

Communication with the data sources uses HTTPS with the default certificate verification of the Python standard library. Do not disable TLS certificate verification as a workaround for connectivity problems.

The plugin itself uses the Python standard library and does not require third-party Python packages.

