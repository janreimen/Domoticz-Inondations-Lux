"""
Thin HTTP client for the official Water-Levels-LocalTime.csv feed, published directly by the Administration de la gestion de l'eau / CTIE and used by www.inondations.lu itself.

Uses only the standard library (urllib), deliberately avoiding a `requests` dependency - nothing to pip-install on a Domoticz host. The URL is passed in (it comes from the plugin's .env file), not
hardcoded here.
"""

import urllib.error
import urllib.request

from constants import REQUEST_TIMEOUT_SECONDS, USER_AGENT
from errors import SourceFetchError


def fetch_csv(url: str) -> str:
    """GET the CSV at `url` and return it decoded as text.

    Raises SourceFetchError on failure, with the original exception
    preserved as __cause__ for debugging.
    """
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            raw = response.read()
    except (urllib.error.URLError, OSError) as ex:
        raise SourceFetchError(f"CSV request failed: {ex}") from ex

    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as ex:
        raise SourceFetchError(f"could not decode CSV response as UTF-8: {ex}") from ex
