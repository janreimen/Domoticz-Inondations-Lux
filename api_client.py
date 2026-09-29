"""
Thin HTTP client for the heichwaasser.lu JSON API - an open-data reuse of the same official measurements, kept as an alternative data source (e.g. if the government CSV is unreachable from your network).

Known limitation: at least one station (Esch-Sure, a reservoir level in metres) is labelled "cm" in this feed, unlike the official CSV. That's why the CSV is the plugin's default source - see README.md,
"Known limitations".

Standard library only; the URL is passed in (from the .env file).
"""

import json
import urllib.error
import urllib.request

from constants import REQUEST_TIMEOUT_SECONDS, USER_AGENT
from errors import SourceFetchError


def fetch_api(url: str) -> list:
    """GET the /rivers endpoint at `url` and return the parsed JSON
    (a list of rivers, each with a nested list of stations).

    Raises SourceFetchError on failure, with the original exception
    preserved as __cause__ for debugging.
    """
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
    except (urllib.error.URLError, OSError, UnicodeDecodeError) as ex:
        raise SourceFetchError(f"API request failed: {ex}") from ex

    try:
        return json.loads(raw)
    except json.JSONDecodeError as ex:
        raise SourceFetchError(f"invalid JSON from API: {ex}") from ex
